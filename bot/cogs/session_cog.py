import logging
from typing import Dict, List, Tuple, Union, Optional
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
import asyncio

from bot.checks import is_in_correct_channel, is_session_manager
from config import settings
from database.base import async_session_factory
from database.models import User, Round, Meeting
from database.repository import MeetingRepository
from services.matchmaker import MatchmakerService
from services.voice_service import VoiceService

logger = logging.getLogger(__name__)


class SessionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.matchmaker = MatchmakerService()
        self.current_round_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await is_in_correct_channel().predicate(ctx)

    @commands.command(name="start")
    @is_session_manager()
    async def start_round(self, ctx: commands.Context, duration_minutes: int = 5):
        logger.info(f"Command !start called by {ctx.author} (Guild: {ctx.guild.id}, Duration: {duration_minutes}m)")
        if self.is_running:
            logger.warning(f"User {ctx.author} tried to start a round while one is running.")
            await ctx.reply("A round is already in progress! Use `!stop` to end it first.")
            return

        lobby_channel = await self._validate_start_conditions(ctx, duration_minutes)
        if not lobby_channel:
            return

        participants, sitter, user_map = self._prepare_participants(ctx, lobby_channel)

        if len(participants) < 2:
            await ctx.reply("Not enough people to start (minimum 2).")
            return

        await ctx.send(f"Preparing round for {len(participants)} people. Duration: {duration_minutes} min.")

        pairs, round_id = await self._process_matchmaking_and_db(ctx, participants, duration_minutes)
        if not pairs:
            await ctx.reply("Could not create any pairs!")
            return

        self._log_match_results(round_id, pairs, sitter, user_map)

        logger.info("Starting lifecycle task...")
        self.is_running = True
        self.current_round_task = asyncio.create_task(
            self._round_lifecycle(ctx, pairs, sitter, user_map, lobby_channel, duration_minutes, round_id)
        )

    @commands.command(name="stop")
    @is_session_manager()
    async def stop_round(self, ctx: commands.Context):
        logger.info(f"Command !stop called by {ctx.author} (Guild: {ctx.guild.id})")
        if not self.is_running or not self.current_round_task:
            logger.warning(f"User {ctx.author} tried to stop a round while one is not running.")
            await ctx.reply("There is no round currently running.")
            return

        self.current_round_task.cancel()

    @commands.command(name="moveto")
    @is_session_manager()
    async def move_to(self, ctx: commands.Context, target_channel: discord.VoiceChannel):
        """
        Usage: !moveto <Target_Channel_ID_or_Name>
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("You must be in a Voice or Stage channel to use this command!")
            return

        source_channel = ctx.author.voice.channel
        members_to_move = source_channel.members
        count = len(members_to_move)

        if count == 0:
            await ctx.reply("There is no one in this channel.")
            return

        logger.info(f"Command !moveto: Moving {count} users from {source_channel.name} to {target_channel.name}")
        status_msg = await ctx.send(
            f"Moving **{count}** users from **{source_channel.name}** to **{target_channel.name}**..."
        )

        tasks = []
        for member in members_to_move:
            tasks.append(member.move_to(target_channel))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]

            if not errors:
                logger.info("Moving completed successfully.")
                await status_msg.edit(content=f"Successfully moved **{count}** users to **{target_channel.name}**.")
                return

            if any(isinstance(e, discord.Forbidden) for e in errors):
                await status_msg.edit(content="Error: Missing 'Move Members' permission or access to the channel.")
                logger.error("Forbidden error while moving members.")
            else:
                failed_count = len(errors)
                await status_msg.edit(
                    content=(
                        f"Partial success: Moved **{count - failed_count}** users to **{target_channel.name}**.\n"
                        f"Failed to move **{failed_count}** users."
                    )
                )
                logger.error(f"Errors occurred while moving some members: {errors}")

        except Exception as e:
            await status_msg.edit(content="An unexpected error occurred during the move.")
            logger.error(f"Unexpected error during move: {e}")

    @commands.command(name="history", help="Sends you a private message with your last 10 meetings.")
    async def history(self, ctx: commands.Context):
        source = f"Guild: {ctx.guild.id}" if ctx.guild else "DM"
        logger.info(f"Command !history called by {ctx.author} ({source})")

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        async with async_session_factory() as session:
            repo = MeetingRepository(session)
            history = await repo.get_user_history(ctx.author.id, limit=10)

        if not history:
            await ctx.author.send("You haven't participated in any meetings yet.")
            return

        header = f"{'No.':<4} | {'Date':<16} | {'Partner'}"
        separator = "-" * (len(header) + 4)
        lines = [
            "**Your Last 10 Meetings:**",
            "```",  # Start Code Block
            header,
            separator,
        ]

        local_tz = ZoneInfo(settings.TIMEZONE)

        for idx, meeting in enumerate(history, 1):
            if meeting.user_1_id == ctx.author.id:
                partner = meeting.user_2
            else:
                partner = meeting.user_1
            partner_name = partner.username if partner else "Unknown User"

            local_time = meeting.round.started_at.astimezone(local_tz)
            date_str = local_time.strftime("%d.%m.%Y %H:%M")  # Polish format

            row = f"{str(idx) + '.':<4} | {date_str:<16} | {partner_name}"
            lines.append(row)

        lines.append("```")  # End Code Block
        message_content = "\n".join(lines)

        try:
            await ctx.author.send(message_content)
            logger.info(f"Sent DM to {ctx.author} ({source})")
        except discord.Forbidden:
            logger.info(f"Couldn't send DM to {ctx.author} ({source})")
            await ctx.reply(f"{ctx.author.mention}, could not send a DM. Please enable DMs from server members.")

    @start_round.error
    @stop_round.error
    async def session_error_handler(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            if ctx.guild and settings.ALLOWED_CHANNEL_IDS:
                if ctx.channel.id not in settings.ALLOWED_CHANNEL_IDS:
                    return

            logger.warning(f"Unauthorized access attempt by {ctx.author} (Command: {ctx.command})")
            await ctx.reply("**Access denied!** You do not have permission to manage sessions.")

        elif isinstance(error, commands.BadArgument):
            await ctx.reply("Bad argument.")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing argument!")

        else:
            logger.error(f"Unhandled error in command {ctx.command}: {error}", exc_info=True)
            await ctx.send("An unexpected error has occurred.")

    # --- Helper Methods ---

    async def _validate_start_conditions(
        self, ctx: commands.Context, duration_minutes: int
    ) -> Optional[Union[discord.VoiceChannel, discord.StageChannel]]:
        if duration_minutes < 1:
            await ctx.send("Duration must be at least 1 minute.")
            return None

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be in a Voice or Stage channel to start a round!")
            return None

        return ctx.author.voice.channel

    def _prepare_participants(self, ctx: commands.Context, channel: Union[discord.VoiceChannel, discord.StageChannel]):
        all_members = [m for m in channel.members if not m.bot]
        user_map = {m.id: m for m in all_members}

        sitter: Optional[discord.Member] = None
        participants = all_members.copy()

        # If odd, the author sits out
        if len(all_members) % 2 != 0:
            if ctx.author in participants:
                sitter = ctx.author
                participants.remove(ctx.author)
            else:
                # Author ran command but isn't in the list; pick the last person
                sitter = participants.pop()

        return participants, sitter, user_map

    async def _process_matchmaking_and_db(
        self, ctx: commands.Context, participants: List[discord.Member], duration: int
    ):
        user_ids = [m.id for m in participants]
        pairs = []
        round_id = None

        async with async_session_factory() as session:
            repo = MeetingRepository(session)
            history_map = await repo.get_past_meetings_with_time(user_ids)
            pairs, _ = self.matchmaker.create_pairs(user_ids, history_map)

            if not pairs:
                return None, None

            for member in participants:
                await session.merge(User(id=member.id, username=member.name))

            new_round = Round(
                guild_id=ctx.guild.id,
                round_number=1,
                duration_minutes=duration,
            )
            session.add(new_round)
            await session.flush()  # Get ID

            for u1, u2 in pairs:
                session.add(Meeting(round_id=new_round.id, user_1_id=u1, user_2_id=u2))

            await session.commit()
            round_id = new_round.id

        return pairs, round_id

    def _fmt_user(self, user: Optional[discord.Member], uid: int) -> str:
        """Formats the user for logs: Nickname (Name) or ID if none."""
        if user:
            return f"{user.display_name} ({user.name})"
        return f"Unknown_ID_{uid}"

    def _log_match_results(
        self, round_id: int, pairs: List[Tuple[int, int]], sitter: Optional[int], user_map: Dict[int, discord.Member]
    ):
        logger.info(f"=== MATCHING RESULTS FOR ROUND {round_id} ===")

        for idx, (uid1, uid2) in enumerate(pairs, 1):
            p1 = self._fmt_user(user_map.get(uid1), uid1)
            p2 = self._fmt_user(user_map.get(uid2), uid2)
            logger.info(f"Pair {idx}: {p1} <-> {p2}")

        if sitter:
            s_str = self._fmt_user(user_map.get(sitter), sitter)
            logger.info(f"Sitter (No pair): {s_str}")

        logger.info("===========================================")

    async def _round_lifecycle(
        self,
        ctx: commands.Context,
        pairs: List[Tuple[int, int]],
        sitter: Optional[discord.Member],
        user_map: Dict[int, discord.Member],
        lobby_channel: Union[discord.VoiceChannel, discord.StageChannel],
        duration_minutes: int,
        round_id: int,
    ):
        voice_mgr = VoiceService(ctx.guild)

        try:
            logger.info(f"Round {round_id}: Preparing channels for {len(pairs)} pairs.")
            await voice_mgr.prepare_channels(len(pairs))
            await voice_mgr.move_pairs_to_channels(pairs, user_map)

            seconds = duration_minutes * 60
            warning_time = 30

            hop_delay = 0.4
            channels_count = len(voice_mgr.temp_channels)
            half_total_hop_time = (channels_count * hop_delay) / 2
            start_signaling_at_remaining = warning_time + half_total_hop_time

            if seconds > start_signaling_at_remaining:
                await asyncio.sleep(seconds - start_signaling_at_remaining)

                logger.info(f"Round {round_id}: Starting audio signal run (Duration: ~{half_total_hop_time * 2}s)")
                asyncio.create_task(self._signal_channels(ctx, voice_mgr.temp_channels, delay=hop_delay))

                await asyncio.sleep(half_total_hop_time)

                participants_mentions = [m.mention for m in user_map.values()]
                notification_msg = f"{' '.join(participants_mentions)}\n**30 seconds remaining!**"
                await ctx.send(notification_msg)

                await asyncio.sleep(warning_time)

            else:
                await asyncio.sleep(seconds)

        except asyncio.CancelledError:
            logger.info(f"Round {round_id}: Cancelled manually.")
            raise

        except Exception:
            logger.error(f"Round {round_id}: CRITICAL ERROR during lifecycle!", exc_info=True)

        finally:
            logger.info(f"Round {round_id}: Cleanup started.")
            users_to_return = []
            for uid1, uid2 in pairs:
                if uid1 in user_map:
                    users_to_return.append(user_map[uid1])
                if uid2 in user_map:
                    users_to_return.append(user_map[uid2])

            if users_to_return:
                await voice_mgr.return_users_to_lobby(users_to_return, lobby_channel)

            if ctx.guild.voice_client:
                await ctx.guild.voice_client.disconnect(force=False)

            await voice_mgr.cleanup()

            self.is_running = False
            self.current_round_task = None
            logger.info(f"Round {round_id}: Cleanup finished.")

    async def _signal_channels(self, ctx: commands.Context, channels: List[discord.VoiceChannel], delay: float):
        vc = ctx.guild.voice_client

        if not vc:
            try:
                if channels:
                    vc = await channels[0].connect()
            except Exception as e:
                logger.warning(f"Failed to connect to voice for signaling: {e}")
                return

        for channel in channels:
            try:
                if vc.channel.id != channel.id:
                    await vc.move_to(channel)
                await asyncio.sleep(delay)

            except Exception as e:
                logger.warning(f"Failed to signal channel {channel.name}: {e}")
                vc = ctx.guild.voice_client
                if not vc:
                    break

        if vc:
            await vc.disconnect()


async def setup(bot):
    await bot.add_cog(SessionCog(bot))
