import random
import re
from typing import List

from questions import ROUND_3_WORD_FALLBACK


# Русские стоп-слова, которые не интересны для Word Remix
STOP_WORDS = {
    "и", "в", "на", "с", "не", "что", "это", "как", "а", "но",
    "по", "к", "у", "из", "за", "от", "до", "для", "он", "она",
    "оно", "они", "мы", "вы", "ты", "я", "бы", "же", "ли",
    "то", "так", "уже", "ещё", "еще", "все", "всё", "мне", "меня",
    "мой", "моя", "мою", "его", "её", "ее", "их", "нас", "вас",
    "тебя", "себя", "свой", "свою", "своё", "если", "когда",
    "чтобы", "потому", "был", "была", "было", "были", "будет",
    "есть", "нет", "очень", "только", "тоже", "этот", "эта",
    "эти", "тот", "та", "те", "где", "там", "тут", "здесь",
}


def extract_words(answers: List[str]) -> List[str]:
    """Извлекает интересные слова из ответов предыдущих раундов."""
    words = []
    for answer in answers:
        tokens = re.findall(r"[а-яА-ЯёЁa-zA-Z]+", answer)
        for token in tokens:
            lower = token.lower()
            if len(lower) >= 3 and lower not in STOP_WORDS:
                words.append(lower)
    return list(set(words))


def pick_remix_words(collected_words: List[str], count: int = 3) -> List[str]:
    """
    Выбирает слова для Word Remix задания.
    Если слов из прошлых раундов недостаточно, добавляет из fallback-списка.
    """
    available = collected_words[:]
    random.shuffle(available)

    if len(available) >= count:
        return available[:count]

    # Добирает из fallback
    needed = count - len(available)
    fallback = [w for w in ROUND_3_WORD_FALLBACK if w not in available]
    random.shuffle(fallback)
    available.extend(fallback[:needed])

    return available[:count]
