import asyncio
import logging
import discord
from discord.ext import commands
from config import settings

from logger_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("------")


async def main():
    async with bot:
        await bot.load_extension("bot.cogs.session_cog")
        await bot.start(settings.DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
