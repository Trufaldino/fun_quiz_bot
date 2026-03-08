from dataclasses import dataclass, field
from typing import Dict, List, Optional
import asyncio

from models.enums import RoundType, RoundPhase


@dataclass
class DuelState:
    player_a_id: int
    player_b_id: int  # -1 если соло
    question: str
    answer_a: str = ""
    answer_b: str = ""
    votes: Dict[int, int] = field(default_factory=dict)
    vote_message_ids: Dict[int, int] = field(default_factory=dict)
    is_complete: bool = False


@dataclass
class RoundState:
    round_num: int
    round_type: RoundType
    phase: Optional[RoundPhase] = None
    duels: List[DuelState] = field(default_factory=list)
    active_duel_index: int = 0
    timer_task: Optional[asyncio.Task] = None


@dataclass
class GameState:
    rounds: List[RoundState] = field(default_factory=list)
    current_round_index: int = 0
    collected_words: List[str] = field(default_factory=list)
