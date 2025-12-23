import discord
import asyncio
from typing import Dict, List, Tuple, Optional, Union


class VoiceService:
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.category_name = "Speed-friending"
        self.category: Optional[discord.CategoryChannel] = None
        self.temp_channels: List[discord.VoiceChannel] = []

    async def prepare_channels(self, pair_count: int) -> List[discord.VoiceChannel]:
        existing_category = discord.utils.get(self.guild.categories, name=self.category_name)
        if not existing_category:
            self.category = await self.guild.create_category(self.category_name)
        else:
            self.category = existing_category

        self.temp_channels = []
        for i in range(pair_count):
            channel_name = f"Session {i + 1}"
            channel = await self.guild.create_voice_channel(channel_name, category=self.category)
            self.temp_channels.append(channel)

        return self.temp_channels

    async def move_pairs_to_channels(self, pairs: List[Tuple[int, int]], user_id_map: Dict[int, discord.Member]):
        """
        :param pairs: List of tuples (user_id_1, user_id_2)
        :param user_id_map: Dictionary mapping ID -> Discord Member Object
        """
        tasks = []

        for i, (uid1, uid2) in enumerate(pairs):
            if i >= len(self.temp_channels):
                break

            target_channel = self.temp_channels[i]

            member1 = user_id_map.get(uid1)
            member2 = user_id_map.get(uid2)

            if member1 and member1.voice:
                tasks.append(member1.move_to(target_channel))
            if member2 and member2.voice:
                tasks.append(member2.move_to(target_channel))

        await asyncio.gather(*tasks)

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
