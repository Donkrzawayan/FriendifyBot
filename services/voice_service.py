import logging

import discord
import asyncio
from typing import Dict, List, Tuple, Optional, Union

logger = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.category_name = "Speed-friending"
        self.category: Optional[discord.CategoryChannel] = None
        self.temp_channels: List[discord.VoiceChannel] = []

    async def move_pairs_to_new_channels(self, pairs: List[Tuple[int, int]], user_id_map: Dict[int, discord.Member]):
        """
        Args:
            pairs: List of tuples (user_id_1, user_id_2)
            user_id_map: Dictionary mapping ID -> Discord Member Object
        """
        existing_category = discord.utils.get(self.guild.categories, name=self.category_name)
        if not existing_category:
            self.category = await self.guild.create_category(self.category_name)
        else:
            self.category = existing_category

        self.temp_channels = []
        move_tasks = []

        async def create_channel_with_perms_and_move(i: int, uid1: int, uid2: int):
            member1 = user_id_map.get(uid1)
            member2 = user_id_map.get(uid2)

            overwrites = {}
            if member1:
                overwrites[member1] = discord.PermissionOverwrite(connect=True, speak=True, view_channel=True)
            if member2:
                overwrites[member2] = discord.PermissionOverwrite(connect=True, speak=True, view_channel=True)

            channel_name = f"Session {i + 1}"

            channel = await self.guild.create_voice_channel(channel_name, category=self.category, overwrites=overwrites)
            self.temp_channels.append(channel)

            if member1 and member1.voice:
                move_tasks.append(member1.move_to(channel))
            if member2 and member2.voice:
                move_tasks.append(member2.move_to(channel))

        create_tasks = [create_channel_with_perms_and_move(i, uid1, uid2) for i, (uid1, uid2) in enumerate(pairs)]
        await asyncio.gather(*create_tasks)

        if move_tasks:
            await asyncio.gather(*move_tasks)

    async def return_users_to_lobby(
        self, users: List[discord.Member], lobby_channel: Union[discord.VoiceChannel, discord.StageChannel]
    ):
        tasks = []
        for user in users:
            if user.voice:
                tasks.append(user.move_to(lobby_channel))

        await asyncio.gather(*tasks)

    async def cleanup(self):
        for channel in self.temp_channels:
            try:
                await channel.delete()
            except discord.NotFound:
                pass

        self.temp_channels = []

    async def signal_channels(self, delay: float):
        vc = self.guild.voice_client

        if not vc:
            try:
                if self.temp_channels:
                    vc = await self.temp_channels[0].connect()
            except Exception as e:
                logger.warning(f"Failed to connect to voice for signaling: {e}")
                return

        for channel in self.temp_channels:
            try:
                if vc.channel.id != channel.id:
                    await vc.move_to(channel)
                await asyncio.sleep(delay)
            except Exception as e:
                logger.warning(f"Failed to signal channel {channel.name}: {e}")
                vc = self.guild.voice_client
                if not vc:
                    break

        if vc:
            try:
                await vc.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting voice client: {e}")
