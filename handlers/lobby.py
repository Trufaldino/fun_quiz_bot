import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import MIN_PLAYERS, MAX_PLAYERS
from models.enums import LobbyStatus
from models.player import PlayerState
from models.lobby import LobbyState
from storage.state_manager import StateManager
from storage.database import Database
from utils.lobby_id import generate_lobby_id
from game_logic.round_manager import start_game, send_to_player

logger = logging.getLogger(__name__)


def _player_list_text(lobby: LobbyState) -> str:
    names = [p.display_name for p in lobby.players.values()]
    return "👥 Игроки в лобби:\n" + "\n".join(f"  • {n}" for n in names)


def _get_display_name(update: Update) -> str:
    user = update.effective_user
    if user.first_name:
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
        return name
    return user.username or f"Игрок_{user.id}"


async def create_lobby_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового лобби."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    sm = StateManager()

    # Проверяем, не состоит ли игрок уже в лобби
    existing = sm.get_player_lobby(user.id)
    if existing and existing.status != LobbyStatus.FINISHED:
        await query.edit_message_text("❌ Вы уже находитесь в лобби!")
        return

    # Генерируем уникальный ID
    lobby_id = generate_lobby_id()
    for _ in range(100):
        if lobby_id not in sm.lobbies:
            break
        lobby_id = generate_lobby_id()
    else:
        # Крайне маловероятно, но защищаемся
        await query.edit_message_text("❌ Не удалось создать лобби. Попробуйте снова.")
        return

    lobby = LobbyState(lobby_id=lobby_id, host_id=user.id)
    sm.add_lobby(lobby)

    display_name = _get_display_name(update)
    player = PlayerState(
        user_id=user.id,
        username=user.username or "",
        display_name=display_name,
    )
    sm.add_player_to_lobby(lobby_id, player)

    # Регистрация в БД
    db = Database()
    await db.upsert_player(user.id, user.username or "")

    await query.edit_message_text(
        f"✅ Лобби создано!\n\n"
        f"🔑 Код лобби: <b>{lobby_id}</b>\n\n"
        f"Поделитесь этим кодом с друзьями.\n"
        f"Минимум {MIN_PLAYERS} игрока для начала.\n\n"
        f"{_player_list_text(lobby)}",
        parse_mode="HTML",
    )


async def join_lobby_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса входа в лобби — просим ввести код."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    sm = StateManager()

    existing = sm.get_player_lobby(user.id)
    if existing and existing.status != LobbyStatus.FINISHED:
        await query.edit_message_text("❌ Вы уже находитесь в лобби!")
        return

    sm.set_waiting_for_code(user.id)
    await query.edit_message_text("🔑 Введите код лобби:")


async def handle_lobby_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введённого кода лобби."""
    user = update.effective_user
    sm = StateManager()

    if not sm.is_waiting_for_code(user.id):
        return False  # Не обрабатываем

    sm.clear_waiting_for_code(user.id)
    code = update.message.text.strip().upper()

    lobby = sm.get_lobby(code)
    if lobby is None:
        await update.message.reply_text(
            "❌ Лобби с таким кодом не найдено. Попробуйте /start"
        )
        return True

    if lobby.status != LobbyStatus.WAITING:
        await update.message.reply_text(
            "❌ Это лобби уже в игре или завершено."
        )
        return True

    if len(lobby.players) >= MAX_PLAYERS:
        await update.message.reply_text(
            f"❌ Лобби переполнено (максимум {MAX_PLAYERS} игроков)."
        )
        return True

    if user.id in lobby.players:
        await update.message.reply_text("❌ Вы уже в этом лобби!")
        return True

    display_name = _get_display_name(update)
    player = PlayerState(
        user_id=user.id,
        username=user.username or "",
        display_name=display_name,
    )
    sm.add_player_to_lobby(code, player)

    # Регистрация в БД
    db = Database()
    await db.upsert_player(user.id, user.username or "")

    player_count = len(lobby.players)
    list_text = _player_list_text(lobby)

    await update.message.reply_text(
        f"✅ Вы вошли в лобби <b>{code}</b>!\n\n{list_text}",
        parse_mode="HTML",
    )

    # Уведомляем всех остальных
    for uid in lobby.players:
        if uid == user.id:
            continue
        text = f"📢 {display_name} присоединился к лобби!\n\n{list_text}"
        if uid == lobby.host_id and player_count >= MIN_PLAYERS:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 Начать игру",
                            callback_data=f"start_game:{code}",
                        )
                    ]
                ]
            )
            try:
                await context.bot.send_message(
                    chat_id=uid, text=text, reply_markup=keyboard
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить хоста {uid}: {e}")
        else:
            await send_to_player(context.bot, uid, text)

    return True


async def start_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Хост нажал кнопку начала игры."""
    query = update.callback_query
    await query.answer()

    data = query.data  # start_game:{lobby_id}
    parts = data.split(":")
    if len(parts) != 2:
        return

    lobby_id = parts[1]
    sm = StateManager()
    lobby = sm.get_lobby(lobby_id)

    if lobby is None:
        await query.edit_message_text("❌ Лобби не найдено.")
        return

    if query.from_user.id != lobby.host_id:
        await query.answer("❌ Только хост может начать игру!", show_alert=True)
        return

    if len(lobby.players) < MIN_PLAYERS:
        await query.answer(
            f"❌ Нужно минимум {MIN_PLAYERS} игрока!", show_alert=True
        )
        return

    if lobby.status != LobbyStatus.WAITING:
        await query.edit_message_text("❌ Игра уже началась или завершена.")
        return

    await query.edit_message_text("🚀 Запускаю игру...")
    await start_game(context.bot, lobby)
