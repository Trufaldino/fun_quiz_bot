from dataclasses import dataclass


@dataclass
class PlayerState:
    user_id: int
    username: str
    display_name: str
    score: int = 0
