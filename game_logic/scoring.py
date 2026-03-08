from typing import Dict

from config import SCORE_PER_VOTE, QUIPLASH_BONUS
from models.game import DuelState


def calculate_duel_scores(duel: DuelState) -> Dict[int, int]:
    """
    Подсчитывает очки для дуэли.
    Возвращает словарь {user_id: earned_points}.
    """
    if duel.player_b_id == -1:
        # Соло-раунд: игрок получает фиксированные 1000 очков
        return {duel.player_a_id: SCORE_PER_VOTE}

    votes_for_a = 0
    votes_for_b = 0
    total_voters = 0

    for voter_id, voted_for in duel.votes.items():
        total_voters += 1
        if voted_for == duel.player_a_id:
            votes_for_a += 1
        elif voted_for == duel.player_b_id:
            votes_for_b += 1

    scores: Dict[int, int] = {}

    score_a = votes_for_a * SCORE_PER_VOTE
    score_b = votes_for_b * SCORE_PER_VOTE

    # Quiplash бонус: все голосующие выбрали одного игрока
    if total_voters > 0:
        if votes_for_a == total_voters:
            score_a += QUIPLASH_BONUS
        elif votes_for_b == total_voters:
            score_b += QUIPLASH_BONUS

    scores[duel.player_a_id] = score_a
    scores[duel.player_b_id] = score_b

    return scores
