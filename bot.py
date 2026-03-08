import asyncio
import logging
import sys
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, LOBBY_LIFETIME_SECONDS, CLEANUP_INTERVAL_SECONDS
from storage.state_manager import StateManager
from storage.database import Database
from handlers.start import start_command, main_menu_callback
from handlers.lobby import (
    create_lobby_callback,
    join_lobby_callback,
    start_game_callback,
    handle_lobby_code_input,
)
from handlers.answers import handle_answer
from handlers.voting import vote_callback

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def text_message_handler(update: Update, context):
    """
    Единый обработчик текстовых сообщений.
    Приоритет: ввод кода лобби -> ответ на вопрос.
    """
    if not update.message or not update.message.text:
        return

    # 1. Проверяем, ждём ли мы код лобби от этого игрока
    handled = await handle_lobby_code_input(update, context)
    if handled:
        return

    # 2. Проверяем, является ли это ответом на вопрос
    handled = await handle_answer(update, context)
    if handled:
        return


async def cleanup_old_lobbies(app: Application):
    """Фоновая задача: удаляет лобби старше LOBBY_LIFETIME_SECONDS."""
    sm = StateManager()
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        now = datetime.now()
        to_remove = []
        for lobby_id, lobby in sm.lobbies.items():
            age = (now - lobby.created_at).total_seconds()
            if age > LOBBY_LIFETIME_SECONDS:
                to_remove.append(lobby_id)
        for lobby_id in to_remove:
            logger.info(f"Удаляю устаревшее лобби {lobby_id}")
            lobby = sm.get_lobby(lobby_id)
            if lobby and lobby.game:
                for round_state in lobby.game.rounds:
                    if round_state.timer_task and not round_state.timer_task.done():
                        round_state.timer_task.cancel()
            sm.remove_lobby(lobby_id)


async def post_init(app: Application):
    """Инициализация после запуска бота."""
    db = Database()
    await db.init()
    logger.info("База данных инициализирована.")

    # Запускаем фоновую очистку.
    # Ссылку сохраняем в app.bot_data, чтобы GC не уничтожил задачу.
    cleanup_task = asyncio.create_task(cleanup_old_lobbies(app))
    app.bot_data["cleanup_task"] = cleanup_task
    logger.info("Фоновая очистка лобби запущена.")


async def post_shutdown(app: Application):
    """Закрытие ресурсов."""
    # Отменяем фоновую задачу очистки, если она ещё жива
    cleanup_task = app.bot_data.get("cleanup_task")
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()

    db = Database()
    await db.close()
    logger.info("База данных закрыта.")


def main():
    if BOT_TOKEN == "YOUR_TOKEN_HERE":
        print("ОШИБКА: Укажите токен бота в config.py (BOT_TOKEN)")
        sys.exit(1)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Команды
    app.add_handler(CommandHandler("start", start_command))

    # Callback-кнопки
    app.add_handler(CallbackQueryHandler(create_lobby_callback, pattern="^create_lobby$"))
    app.add_handler(CallbackQueryHandler(join_lobby_callback, pattern="^join_lobby$"))
    app.add_handler(CallbackQueryHandler(start_game_callback, pattern=r"^start_game:"))
    app.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote:"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))

    # Текстовые сообщения (ввод кода и ответы на вопросы)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler)
    )

    logger.info("Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
