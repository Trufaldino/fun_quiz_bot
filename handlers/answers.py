import logging

from telegram import Update
from telegram.ext import ContextTypes

from models.enums import RoundPhase
from storage.state_manager import StateManager

logger = logging.getLogger(__name__)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает текстовое сообщение как ответ на вопрос.
    Возвращает True, если сообщение было обработано как ответ.
    """
    user = update.effective_user
    if not update.message or not update.message.text:
        return False

    sm = StateManager()
    lobby = sm.get_player_lobby(user.id)
    if lobby is None:
        return False

    game = lobby.game
    if game is None:
        return False

    current_round = game.rounds[game.current_round_index]
    if current_round.phase != RoundPhase.ANSWERING:
        return False

    answer_text = update.message.text.strip()
    if not answer_text:
        return False

    # Ищем дуэль, в которой участвует этот игрок
    for duel in current_round.duels:
        if duel.player_a_id == user.id and not duel.answer_a:
            duel.answer_a = answer_text
            await update.message.reply_text("✅ Ответ принят! Ожидайте остальных.")
            return True
        elif duel.player_b_id == user.id and not duel.answer_b:
            duel.answer_b = answer_text
            await update.message.reply_text("✅ Ответ принят! Ожидайте остальных.")
            return True

    # Игрок уже ответил
    for duel in current_round.duels:
        if duel.player_a_id == user.id and duel.answer_a:
            await update.message.reply_text("⚠️ Вы уже ответили на вопрос этого раунда.")
            return True
        if duel.player_b_id == user.id and duel.answer_b:
            await update.message.reply_text("⚠️ Вы уже ответили на вопрос этого раунда.")
            return True

    return False
