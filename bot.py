import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import start, groups, santa, qr_codes
import database as db

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main function to start the bot"""

    # Initialize database
    db.init_db()

    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers (order matters!)
    dp.include_router(start.router)
    dp.include_router(groups.router)
    dp.include_router(santa.router)
    dp.include_router(qr_codes.router)

    # Start bot
    logger.info("Secret Santa bot started!")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
