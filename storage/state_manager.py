from typing import Dict, Optional

from models.lobby import LobbyState
from models.player import PlayerState


class StateManager:
    """Singleton для хранения всех активных лобби и индекса игроков."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.lobbies: Dict[str, LobbyState] = {}
            cls._instance.player_lobby_index: Dict[int, str] = {}
            cls._instance._waiting_for_lobby_code: set = set()
        return cls._instance

    def get_lobby(self, lobby_id: str) -> Optional[LobbyState]:
        return self.lobbies.get(lobby_id)

    def get_player_lobby(self, user_id: int) -> Optional[LobbyState]:
        lobby_id = self.player_lobby_index.get(user_id)
        if lobby_id is None:
            return None
        return self.lobbies.get(lobby_id)

    def add_lobby(self, lobby: LobbyState):
        self.lobbies[lobby.lobby_id] = lobby

    def remove_lobby(self, lobby_id: str):
        lobby = self.lobbies.pop(lobby_id, None)
        if lobby:
            for uid in list(lobby.players.keys()):
                self.player_lobby_index.pop(uid, None)

    def add_player_to_lobby(self, lobby_id: str, player: PlayerState):
        lobby = self.lobbies.get(lobby_id)
        if lobby is None:
            return
        lobby.players[player.user_id] = player
        self.player_lobby_index[player.user_id] = lobby_id

    def remove_player_from_lobby(self, user_id: int):
        lobby_id = self.player_lobby_index.pop(user_id, None)
        if lobby_id and lobby_id in self.lobbies:
            self.lobbies[lobby_id].players.pop(user_id, None)

    def set_waiting_for_code(self, user_id: int):
        self._waiting_for_lobby_code.add(user_id)

    def is_waiting_for_code(self, user_id: int) -> bool:
        return user_id in self._waiting_for_lobby_code

    def clear_waiting_for_code(self, user_id: int):
        self._waiting_for_lobby_code.discard(user_id)
