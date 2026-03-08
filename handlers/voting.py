import logging

from telegram import Update
from telegram.ext import ContextTypes

from models.enums import RoundPhase
from storage.state_manager import StateManager

logger = logging.getLogger(__name__)


async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки голосования."""
    query = update.callback_query

    data = query.data  # vote:{lobby_id}:{duel_index}:{voted_for_user_id}
    parts = data.split(":")
    if len(parts) != 4:
        await query.answer("❌ Ошибка данных.", show_alert=True)
        return

    _, lobby_id, duel_index_str, voted_for_str = parts

    try:
        duel_index = int(duel_index_str)
        voted_for = int(voted_for_str)
    except ValueError:
        await query.answer("❌ Ошибка данных.", show_alert=True)
        return

    voter_id = query.from_user.id
    sm = StateManager()
    lobby = sm.get_lobby(lobby_id)

    if lobby is None:
        await query.answer("❌ Лобби не найдено.", show_alert=True)
        return

    game = lobby.game
    if game is None:
        await query.answer("❌ Игра не активна.", show_alert=True)
        return

    current_round = game.rounds[game.current_round_index]
    if current_round.phase != RoundPhase.VOTING:
        await query.answer("❌ Голосование уже закончилось.", show_alert=True)
        return

    if duel_index >= len(current_round.duels):
        await query.answer("❌ Ошибка данных дуэли.", show_alert=True)
        return

    duel = current_round.duels[duel_index]

    # Нельзя голосовать за себя
    if voter_id == duel.player_a_id or voter_id == duel.player_b_id:
        await query.answer("❌ Нельзя голосовать в своей дуэли!", show_alert=True)
        return

    # Нельзя голосовать дважды
    if voter_id in duel.votes:
        await query.answer("❌ Вы уже проголосовали!", show_alert=True)
        return

    # Записываем голос
    duel.votes[voter_id] = voted_for

    # Убираем кнопки у проголосовавшего
    try:
        voted_for_player = lobby.players.get(voted_for)
        voted_name = voted_for_player.display_name if voted_for_player else "???"
        await query.edit_message_reply_markup(reply_markup=None)
        await query.answer(f"✅ Вы проголосовали за: {voted_name}!")
    except Exception as e:
        logger.warning(f"Ошибка при обработке голоса: {e}")
        await query.answer("✅ Голос принят!")
