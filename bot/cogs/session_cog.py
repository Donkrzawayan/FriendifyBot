import logging
from typing import Dict, List, Tuple, Union, Optional
import discord
from discord.ext import commands
import asyncio

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

    @commands.command(name="start")
    async def start_round(self, ctx: commands.Context, duration_minutes: int = 5):
        logger.info(f"Command !start called by {ctx.author} (Guild: {ctx.guild.id}, Duration: {duration_minutes}m)")
        if self.is_running:
            logger.warning(f"User {ctx.author} tried to start a round while one is running.")
            await ctx.send("A round is already in progress! Use `!stop` to end it first.")
            return

        lobby_channel = await self._validate_start_conditions(ctx, duration_minutes)
        if not lobby_channel:
            return

        participants, sitter, user_map = self._prepare_participants(ctx, lobby_channel)

        if len(participants) < 2:
            await ctx.send("Not enough people to start (minimum 2).")
            return

        await ctx.send(f"Preparing round for {len(participants)} people. Duration: {duration_minutes} min.")

        pairs, round_id = await self._process_matchmaking_and_db(ctx, participants, duration_minutes)
        if not pairs:
            await ctx.send("Could not create any pairs!")
            return

        logger.info("Starting lifecycle task...")
        self.is_running = True
        self.current_round_task = asyncio.create_task(
            self._round_lifecycle(ctx, pairs, sitter, user_map, lobby_channel, duration_minutes, round_id)
        )

    @commands.command(name="stop")
    async def stop_round(self, ctx: commands.Context):
        logger.info(f"Command !stop called by {ctx.author} (Guild: {ctx.guild.id})")
        if not self.is_running or not self.current_round_task:
            logger.warning(f"User {ctx.author} tried to stop a round while one is not running.")
            await ctx.send("There is no round currently running.")
            return

        self.current_round_task.cancel()

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
            past_pairs = await repo.get_past_pairs(user_ids)
            pairs, _ = self.matchmaker.create_pairs(user_ids, past_pairs)

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

            if seconds > warning_time:
                await asyncio.sleep(seconds - warning_time)

                warning_msg = "⏰ **30 seconds remaining!**"
                notify_tasks = [ch.send(warning_msg) for ch in voice_mgr.temp_channels]
                if notify_tasks:
                    await asyncio.gather(*notify_tasks)
                await ctx.send(warning_msg)

                await asyncio.sleep(warning_time)
            else:
                await asyncio.sleep(seconds)

        except asyncio.CancelledError:
            logger.info(f"Round {round_id}: Cancelled manually.")
            raise

        except Exception as e:
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

            await voice_mgr.cleanup()

            self.is_running = False
            self.current_round_task = None
            logger.info(f"Round {round_id}: Cleanup finished.")


async def setup(bot):
    await bot.add_cog(SessionCog(bot))
