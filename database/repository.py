from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Set, Tuple
from database.models import Meeting


class MeetingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_past_pairs(self, user_ids: List[int]) -> Set[Tuple[int, int]]:
        """
        Returns: a set of pairs that have already taken place.
        """
        if not user_ids:
            return set()

        stmt = select(Meeting.user_1_id, Meeting.user_2_id).where(
            and_(Meeting.user_1_id.in_(user_ids), Meeting.user_2_id.in_(user_ids))
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        past_pairs = set()
        for u1, u2 in rows:
            # Store lower ID first so (A, B) equals (B, A)
            pair = tuple(sorted((u1, u2)))
            past_pairs.add(pair)

        return past_pairs
