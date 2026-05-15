import discord
from discord.ext import commands
from config import settings
from database.base import async_session_factory
from database.repository import GuildSettingsRepository


class WrongChannelError(commands.CheckFailure):
    pass


def is_session_manager():
    async def predicate(ctx: commands.Context):
        if not ctx.guild:
            return False

        if ctx.author.id == ctx.guild.owner_id:
            return True

        if ctx.author.guild_permissions.administrator:
            return True

        if isinstance(ctx.author, discord.Member):
            role = ctx.guild.get_role(settings.ALLOWED_ROLE_ID)
            if role and role in ctx.author.roles:
                return True

        return False

    return commands.check(predicate)


def is_in_correct_channel():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return True

        async with async_session_factory() as session:
            repo = GuildSettingsRepository(session)
            guild_settings = await repo.get_settings(ctx.guild.id)

        if not guild_settings or not guild_settings.channel_id:
            return True

        if ctx.channel.id == guild_settings.channel_id:
            return True

        raise WrongChannelError()

    return commands.check(predicate)
