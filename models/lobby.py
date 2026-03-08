from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from models.enums import LobbyStatus
from models.player import PlayerState
from models.game import GameState


@dataclass
class LobbyState:
    lobby_id: str
    host_id: int
    players: Dict[int, PlayerState] = field(default_factory=dict)
    status: LobbyStatus = LobbyStatus.WAITING
    game: Optional[GameState] = None
    created_at: datetime = field(default_factory=datetime.now)
