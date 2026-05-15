import discord
from discord.ext import commands
import logging
from bot.checks import is_session_manager
from database.base import async_session_factory
from database.repository import GuildSettingsRepository

logger = logging.getLogger(__name__)


class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setchannel")
    @is_session_manager()
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Sets the specific channel where the bot listens to commands (defaults to current)."""
        target_channel = channel or ctx.channel
        await self._overwrite_channel(ctx.guild, target_channel.id)
        await ctx.reply(
            f"Command channel set to {target_channel.mention}. The bot will now only listen to commands in this channel."
        )

    @commands.command(name="clearchannel")
    @is_session_manager()
    async def clear_channel(self, ctx: commands.Context):
        """Removes the channel restriction, allowing the bot to be used anywhere."""
        await self._overwrite_channel(ctx.guild)
        await ctx.reply("Channel restriction removed. The bot will now respond in all channels.")

    async def _overwrite_channel(self, guild: discord.Guild, channel_id: int = None):
        async with async_session_factory() as session:
            repo = GuildSettingsRepository(session)
            await repo.set_allowed_channel(guild.id, channel_id)
            await session.commit()


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))
