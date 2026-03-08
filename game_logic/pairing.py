import random
from typing import List, Tuple


def make_pairs(player_ids: List[int]) -> List[Tuple[int, int]]:
    """
    Разбивает список игроков на пары.
    При нечётном числе игроков последний играет соло (partner = -1).
    """
    shuffled = player_ids[:]
    random.shuffle(shuffled)

    pairs: List[Tuple[int, int]] = []
    i = 0
    while i < len(shuffled) - 1:
        pairs.append((shuffled[i], shuffled[i + 1]))
        i += 2

    if i < len(shuffled):
        pairs.append((shuffled[i], -1))

    return pairs
