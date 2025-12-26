import asyncio
import logging
from database.base import engine, Base

# Import models so that SQLAlchemy knows what to create
from database.models import User, Round, Meeting

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db():
    logger.info("Connecting to the database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

        logger.info("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

    logger.info("The tables have been created.")


if __name__ == "__main__":
    asyncio.run(init_db())
