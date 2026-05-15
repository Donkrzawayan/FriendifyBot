from datetime import datetime, timezone
from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Dict, List, Sequence, Tuple
from database.models import GuildSettings, Meeting, Round


class MeetingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_past_meetings_with_time(self, user_ids: List[int]) -> Dict[Tuple[int, int], datetime]:
        """
        Retrieves the timestamp of the *latest* meeting between any two users in the list.
        Returns: Dictionary {(user_id_min, user_id_max): last_met_datetime}
        """
        if not user_ids:
            return {}

        stmt = (
            select(Meeting.user_1_id, Meeting.user_2_id, func.max(Round.started_at))
            .join(Round, Meeting.round_id == Round.id)
            .where(and_(Meeting.user_1_id.in_(user_ids), Meeting.user_2_id.in_(user_ids)))
            .group_by(Meeting.user_1_id, Meeting.user_2_id)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        history_map = {}
        for u1, u2, last_met in rows:
            # Store lower ID first so (A, B) equals (B, A)
            pair_key = tuple(sorted((u1, u2)))

            if last_met.tzinfo is None:
                last_met = last_met.replace(tzinfo=timezone.utc)

            if pair_key not in history_map:
                history_map[pair_key] = last_met

        return history_map

    async def get_user_history(self, user_id: int, limit: int = 10) -> Sequence[Meeting]:
        stmt = (
            select(Meeting)
            .join(Round, Meeting.round_id == Round.id)
            .options(selectinload(Meeting.round), selectinload(Meeting.user_1), selectinload(Meeting.user_2))
            .where(or_(Meeting.user_1_id == user_id, Meeting.user_2_id == user_id))
            .order_by(Round.started_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        meetings = result.scalars().all()

        for meeting in meetings:
            if meeting.round.started_at.tzinfo is None:
                meeting.round.started_at = meeting.round.started_at.replace(tzinfo=timezone.utc)

        return meetings


class GuildSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_settings(self, guild_id: int) -> GuildSettings | None:
        return await self.session.get(GuildSettings, guild_id)

    async def set_allowed_channel(self, guild_id: int, channel_id: int | None) -> GuildSettings:
        """Upserts guild settings with the new channel_id."""
        settings = await self.session.get(GuildSettings, guild_id)

        if not settings:
            settings = GuildSettings(guild_id=guild_id, channel_id=channel_id)
            self.session.add(settings)
        else:
            settings.channel_id = channel_id

        await self.session.flush()
        return settings
