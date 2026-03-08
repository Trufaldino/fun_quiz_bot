from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

MAIN_MENU_TEXT = (
    "🎭 Добро пожаловать в AI Верстак Quiplash!\n\n"
    "📖 Как играть:\n"
    "1️⃣ Создай лобби или войди по коду от друга\n"
    "2️⃣ Дождись игроков (минимум 2), хост нажимает «Начать игру»\n"
    "3️⃣ Тебе придёт вопрос в личку — ответь смешно!\n"
    "4️⃣ Все голосуют за лучший ответ\n"
    "5️⃣ Кто набрал больше очков — тот победил!\n\n"
    "🏆 За каждый голос: +1000 очков\n"
    "🎉 Все проголосовали за тебя: +2000 бонус (QUIPLASH!)\n\n"
    "Что хотите сделать?"
)

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🎮 Создать лобби", callback_data="create_lobby"),
            InlineKeyboardButton("🚪 Войти в лобби", callback_data="join_lobby"),
        ]
    ]
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await update.message.reply_text(MAIN_MENU_TEXT, reply_markup=MAIN_MENU_KEYBOARD)


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню по кнопке."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(MAIN_MENU_TEXT, reply_markup=MAIN_MENU_KEYBOARD)
