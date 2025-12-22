import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.base import init_db, async_session_factory
from database.models import User, Round, Meeting


async def main():
    print("dupa1")
    await init_db()
    print("dupa2")

    async with async_session_factory() as session:
        print("dupa3")

        user1 = User(id=1001, username="JanKowalski")
        user2 = User(id=1002, username="AnnaNowak")

        session.add(user1)
        session.add(user2)

        await session.flush()

        new_round = Round(guild_id=9999, round_number=1, duration_minutes=5)
        session.add(new_round)
        await session.flush()

        meeting = Meeting(round_id=new_round.id, user_1_id=user1.id, user_2_id=user2.id)
        session.add(meeting)

        await session.commit()
        print("dupa4")

    async with async_session_factory() as session:
        print("dupa5")

        stmt = select(Round).options(selectinload(Round.meetings))
        result = await session.execute(stmt)

        rounds_in_db = result.scalars().all()

        for r in rounds_in_db:
            print(r)
            for m in r.meetings:
                print(f"{m} (users: {m.user_1_id} and {m.user_2_id})")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)
