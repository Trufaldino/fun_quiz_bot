import asyncio
import logging
import random
from typing import List

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config import ANSWER_TIMEOUT, VOTE_TIMEOUT, DEFAULT_ANSWER
from models.enums import RoundType, RoundPhase, LobbyStatus
from models.game import DuelState, RoundState, GameState
from models.lobby import LobbyState
from game_logic.pairing import make_pairs
from game_logic.scoring import calculate_duel_scores
from game_logic.word_remix import extract_words, pick_remix_words
from storage.state_manager import StateManager
from storage.database import Database
from questions import ROUND_1_QUESTIONS, ROUND_2_PHRASES

logger = logging.getLogger(__name__)

ROUND_NAMES = {
    RoundType.FUNNY_ANSWER: "Смешной ответ",
    RoundType.COMPLETE_PHRASE: "Дополни фразу",
    RoundType.WORD_REMIX: "Word Remix",
}


async def send_to_player(bot: Bot, user_id: int, text: str):
    """Безопасная отправка сообщения в ЛС."""
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение игроку {user_id}: {e}")


async def broadcast_lobby(bot: Bot, lobby: LobbyState, text: str):
    """Рассылка сообщения всем игрокам лобби."""
    for uid in lobby.players:
        await send_to_player(bot, uid, text)


def build_leaderboard(lobby: LobbyState) -> str:
    """Формирует текст таблицы лидеров."""
    sorted_players = sorted(
        lobby.players.values(), key=lambda p: p.score, reverse=True
    )
    lines = ["🏆 Таблица лидеров:"]
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(sorted_players):
        prefix = medals[i] if i < len(medals) else f"{i + 1}."
        lines.append(f"{prefix} {p.display_name} — {p.score} очков")
    return "\n".join(lines)


async def start_game(bot: Bot, lobby: LobbyState):
    """Запускает игру: создаёт GameState и начинает раунд 1."""
    lobby.status = LobbyStatus.PLAYING
    lobby.game = GameState()

    round_types = [
        RoundType.FUNNY_ANSWER,
        RoundType.COMPLETE_PHRASE,
        RoundType.WORD_REMIX,
    ]

    for i, rt in enumerate(round_types):
        lobby.game.rounds.append(
            RoundState(round_num=i + 1, round_type=rt)
        )

    await broadcast_lobby(
        bot, lobby, "🎮 Игра начинается! Приготовьтесь!\n\nВпереди 3 раунда."
    )
    await asyncio.sleep(2)
    await run_round(bot, lobby)


async def run_round(bot: Bot, lobby: LobbyState):
    """Запускает текущий раунд."""
    game = lobby.game
    round_state = game.rounds[game.current_round_index]
    round_name = ROUND_NAMES[round_state.round_type]

    await broadcast_lobby(
        bot,
        lobby,
        f"📢 Раунд {round_state.round_num}/3: {round_name}",
    )
    await asyncio.sleep(1)

    player_ids = list(lobby.players.keys())
    pairs = make_pairs(player_ids)

    # Выбор вопросов
    questions = _pick_questions(round_state.round_type, len(pairs), game)

    for idx, (pa, pb) in enumerate(pairs):
        q = questions[idx]
        duel = DuelState(player_a_id=pa, player_b_id=pb, question=q)
        round_state.duels.append(duel)

    # Фаза ответов
    round_state.phase = RoundPhase.ANSWERING
    await _answering_phase(bot, lobby, round_state)


def _pick_questions(
    round_type: RoundType, count: int, game: GameState
) -> List[str]:
    """Выбирает вопросы для раунда."""
    if round_type == RoundType.FUNNY_ANSWER:
        pool = ROUND_1_QUESTIONS[:]
        random.shuffle(pool)
        return pool[:count]
    elif round_type == RoundType.COMPLETE_PHRASE:
        pool = ROUND_2_PHRASES[:]
        random.shuffle(pool)
        return pool[:count]
    elif round_type == RoundType.WORD_REMIX:
        questions = []
        for _ in range(count):
            words = pick_remix_words(game.collected_words, 3)
            q = f"Придумай фразу со словами: {', '.join(words)}"
            questions.append(q)
        return questions
    return []


async def _answering_phase(bot: Bot, lobby: LobbyState, round_state: RoundState):
    """Рассылает вопросы и запускает таймер."""
    for duel in round_state.duels:
        pa = lobby.players.get(duel.player_a_id)
        if pa:
            await send_to_player(
                bot,
                duel.player_a_id,
                f"❓ Ваш вопрос:\n\n{duel.question}\n\n"
                f"Напишите ответ в течение {ANSWER_TIMEOUT} секунд.",
            )
        if duel.player_b_id != -1:
            pb = lobby.players.get(duel.player_b_id)
            if pb:
                await send_to_player(
                    bot,
                    duel.player_b_id,
                    f"❓ Ваш вопрос:\n\n{duel.question}\n\n"
                    f"Напишите ответ в течение {ANSWER_TIMEOUT} секунд.",
                )

    # Таймер
    round_state.timer_task = asyncio.create_task(
        _answer_timer(bot, lobby, round_state)
    )


async def _answer_timer(bot: Bot, lobby: LobbyState, round_state: RoundState):
    """Ожидает таймаут или завершение всех ответов."""
    for elapsed in range(ANSWER_TIMEOUT):
        await asyncio.sleep(1)
        # Проверяем, все ли ответили
        if _all_answered(round_state):
            break

    # Заполняем дефолтные ответы
    _fill_default_answers(round_state)

    # Собираем слова для Word Remix
    _collect_words(lobby.game, round_state)

    # Переходим к голосованию
    round_state.phase = RoundPhase.VOTING
    await _voting_phase(bot, lobby, round_state)


def _all_answered(round_state: RoundState) -> bool:
    for duel in round_state.duels:
        if not duel.answer_a:
            return False
        if duel.player_b_id != -1 and not duel.answer_b:
            return False
    return True


def _fill_default_answers(round_state: RoundState):
    for duel in round_state.duels:
        if not duel.answer_a:
            duel.answer_a = DEFAULT_ANSWER
        if duel.player_b_id != -1 and not duel.answer_b:
            duel.answer_b = DEFAULT_ANSWER


def _collect_words(game: GameState, round_state: RoundState):
    """Собирает слова из ответов для будущего Word Remix."""
    if round_state.round_type in (RoundType.FUNNY_ANSWER, RoundType.COMPLETE_PHRASE):
        answers = []
        for duel in round_state.duels:
            if duel.answer_a != DEFAULT_ANSWER:
                answers.append(duel.answer_a)
            if duel.player_b_id != -1 and duel.answer_b != DEFAULT_ANSWER:
                answers.append(duel.answer_b)
        words = extract_words(answers)
        game.collected_words.extend(words)


async def _voting_phase(bot: Bot, lobby: LobbyState, round_state: RoundState):
    """Запускает голосование дуэль за дуэлью."""
    round_state.active_duel_index = 0
    await _start_duel_vote(bot, lobby, round_state)


async def _start_duel_vote(bot: Bot, lobby: LobbyState, round_state: RoundState):
    """Начинает голосование по текущей дуэли."""
    idx = round_state.active_duel_index
    duel = round_state.duels[idx]

    if duel.player_b_id == -1:
        # Соло — автоматически даём очки и идём дальше
        duel.is_complete = True
        scores = calculate_duel_scores(duel)
        for uid, pts in scores.items():
            if uid in lobby.players:
                lobby.players[uid].score += pts

        pa = lobby.players.get(duel.player_a_id)
        name_a = pa.display_name if pa else "???"
        await broadcast_lobby(
            bot,
            lobby,
            f"🎤 Соло от {name_a}!\n\n"
            f"Вопрос: {duel.question}\n"
            f"Ответ: {duel.answer_a}\n\n"
            f"🎁 {name_a} получает {scores.get(duel.player_a_id, 0)} очков!",
        )
        await asyncio.sleep(3)
        await _advance_to_next_duel(bot, lobby, round_state)
        return

    pa = lobby.players.get(duel.player_a_id)
    pb = lobby.players.get(duel.player_b_id)
    name_a = pa.display_name if pa else "???"
    name_b = pb.display_name if pb else "???"

    # Случайный порядок A/B для анонимности
    show_a_first = random.choice([True, False])

    if show_a_first:
        text = (
            f"⚔️ Дуэль {idx + 1}/{len(round_state.duels)}\n\n"
            f"Вопрос: {duel.question}\n\n"
            f"🅰 {duel.answer_a}\n\n"
            f"🅱 {duel.answer_b}"
        )
        btn_a_id = duel.player_a_id
        btn_b_id = duel.player_b_id
    else:
        text = (
            f"⚔️ Дуэль {idx + 1}/{len(round_state.duels)}\n\n"
            f"Вопрос: {duel.question}\n\n"
            f"🅰 {duel.answer_b}\n\n"
            f"🅱 {duel.answer_a}"
        )
        btn_a_id = duel.player_b_id
        btn_b_id = duel.player_a_id

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🅰 Голосовать",
                    callback_data=f"vote:{lobby.lobby_id}:{idx}:{btn_a_id}",
                ),
                InlineKeyboardButton(
                    "🅱 Голосовать",
                    callback_data=f"vote:{lobby.lobby_id}:{idx}:{btn_b_id}",
                ),
            ]
        ]
    )

    text += f"\n\n⏱ Голосуйте! У вас {VOTE_TIMEOUT} секунд."

    # Шлём голосование всем, кроме участников дуэли
    voters = [
        uid
        for uid in lobby.players
        if uid != duel.player_a_id and uid != duel.player_b_id
    ]

    for uid in voters:
        try:
            msg = await bot.send_message(
                chat_id=uid, text=text, reply_markup=keyboard
            )
            duel.vote_message_ids[uid] = msg.message_id
        except Exception as e:
            logger.warning(f"Не удалось отправить голосование игроку {uid}: {e}")

    # Участникам дуэли показываем без кнопок
    for uid in [duel.player_a_id, duel.player_b_id]:
        await send_to_player(bot, uid, text.replace(
            f"\n\n⏱ Голосуйте! У вас {VOTE_TIMEOUT} секунд.",
            "\n\n⏳ Ожидание голосования..."
        ))

    # Таймер голосования
    round_state.timer_task = asyncio.create_task(
        _vote_timer(bot, lobby, round_state, show_a_first)
    )


async def _vote_timer(
    bot: Bot, lobby: LobbyState, round_state: RoundState, show_a_first: bool
):
    """Ожидает таймаут голосования или завершение голосов."""
    idx = round_state.active_duel_index
    duel = round_state.duels[idx]

    total_voters = len(lobby.players) - (1 if duel.player_b_id == -1 else 2)

    for _ in range(VOTE_TIMEOUT):
        await asyncio.sleep(1)
        if len(duel.votes) >= total_voters:
            break

    await _finish_duel_vote(bot, lobby, round_state, show_a_first)


async def _finish_duel_vote(
    bot: Bot, lobby: LobbyState, round_state: RoundState, show_a_first: bool
):
    """Подводит итоги дуэли."""
    idx = round_state.active_duel_index
    duel = round_state.duels[idx]
    duel.is_complete = True

    # Убираем кнопки у оставшихся сообщений
    for uid, msg_id in duel.vote_message_ids.items():
        try:
            await bot.edit_message_reply_markup(
                chat_id=uid, message_id=msg_id, reply_markup=None
            )
        except Exception:
            pass

    scores = calculate_duel_scores(duel)
    for uid, pts in scores.items():
        if uid in lobby.players:
            lobby.players[uid].score += pts

    pa = lobby.players.get(duel.player_a_id)
    pb = lobby.players.get(duel.player_b_id)
    name_a = pa.display_name if pa else "???"
    name_b = pb.display_name if pb else "???"

    votes_for_a = sum(1 for v in duel.votes.values() if v == duel.player_a_id)
    votes_for_b = sum(1 for v in duel.votes.values() if v == duel.player_b_id)

    total_voters = votes_for_a + votes_for_b
    quiplash_a = total_voters > 0 and votes_for_a == total_voters
    quiplash_b = total_voters > 0 and votes_for_b == total_voters

    result_text = (
        f"📊 Результаты дуэли:\n\n"
        f"Вопрос: {duel.question}\n\n"
        f"🅰 {name_a}: {duel.answer_a}\n"
        f"   Голосов: {votes_for_a} | +{scores.get(duel.player_a_id, 0)} очков"
    )
    if quiplash_a:
        result_text += " 🎉 QUIPLASH!"
    result_text += (
        f"\n\n🅱 {name_b}: {duel.answer_b}\n"
        f"   Голосов: {votes_for_b} | +{scores.get(duel.player_b_id, 0)} очков"
    )
    if quiplash_b:
        result_text += " 🎉 QUIPLASH!"

    await broadcast_lobby(bot, lobby, result_text)
    await asyncio.sleep(4)
    await _advance_to_next_duel(bot, lobby, round_state)


async def _advance_to_next_duel(
    bot: Bot, lobby: LobbyState, round_state: RoundState
):
    """Переходит к следующей дуэли или завершает раунд."""
    round_state.active_duel_index += 1

    if round_state.active_duel_index < len(round_state.duels):
        await _start_duel_vote(bot, lobby, round_state)
    else:
        # Раунд завершён
        round_state.phase = RoundPhase.RESULTS
        await broadcast_lobby(
            bot,
            lobby,
            f"✅ Раунд {round_state.round_num} завершён!\n\n"
            + build_leaderboard(lobby),
        )
        await asyncio.sleep(4)
        await _advance_to_next_round(bot, lobby)


async def _advance_to_next_round(bot: Bot, lobby: LobbyState):
    """Переходит к следующему раунду или завершает игру."""
    game = lobby.game
    game.current_round_index += 1

    if game.current_round_index < len(game.rounds):
        await run_round(bot, lobby)
    else:
        await _finish_game(bot, lobby)


async def _finish_game(bot: Bot, lobby: LobbyState):
    """Завершает игру, объявляет победителя, сохраняет в БД."""
    lobby.status = LobbyStatus.FINISHED

    sorted_players = sorted(
        lobby.players.values(), key=lambda p: p.score, reverse=True
    )
    winner = sorted_players[0] if sorted_players else None

    final_text = "🏁 Игра окончена!\n\n" + build_leaderboard(lobby)
    if winner:
        final_text += f"\n\n🎊 Победитель: {winner.display_name} с {winner.score} очками!"

    play_again_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Играть снова", callback_data="create_lobby"),
            InlineKeyboardButton("🚪 В главное меню", callback_data="main_menu"),
        ]
    ])

    for uid in lobby.players:
        try:
            await bot.send_message(chat_id=uid, text=final_text, reply_markup=play_again_keyboard)
        except Exception as e:
            logger.warning(f"Не удалось отправить финал игроку {uid}: {e}")

    # Сохранение в БД
    db = Database()
    for p in lobby.players.values():
        is_winner = (winner is not None and p.user_id == winner.user_id)
        try:
            await db.add_game_result(p.user_id, p.score, is_winner)
        except Exception as e:
            logger.warning(f"Ошибка записи статистики для {p.user_id}: {e}")

    # Отменяем активный таймер раунда, если он ещё работает
    if lobby.game:
        for round_state in lobby.game.rounds:
            if round_state.timer_task and not round_state.timer_task.done():
                round_state.timer_task.cancel()

    # Очистка лобби
    sm = StateManager()
    sm.remove_lobby(lobby.lobby_id)
