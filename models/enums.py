from enum import Enum


class LobbyStatus(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


class RoundType(Enum):
    FUNNY_ANSWER = "funny_answer"
    COMPLETE_PHRASE = "complete_phrase"
    WORD_REMIX = "word_remix"


class RoundPhase(Enum):
    ANSWERING = "answering"
    VOTING = "voting"
    RESULTS = "results"
