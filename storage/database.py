import aiosqlite
from config import DB_PATH


class Database:
    """Работа с SQLite для сохранения статистики игроков."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db = None
        return cls._instance

    async def init(self):
        self._db = await aiosqlite.connect(DB_PATH)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                total_score INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    async def upsert_player(self, user_id: int, username: str):
        await self._db.execute(
            """
            INSERT INTO players (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
            """,
            (user_id, username),
        )
        await self._db.commit()

    async def add_game_result(self, user_id: int, score: int, is_winner: bool):
        await self._db.execute(
            """
            UPDATE players
            SET total_score = total_score + ?,
                games_played = games_played + 1,
                wins = wins + ?
            WHERE user_id = ?
            """,
            (score, 1 if is_winner else 0, user_id),
        )
        await self._db.commit()

    async def get_player_stats(self, user_id: int):
        async with self._db.execute(
            "SELECT username, total_score, games_played, wins FROM players WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            return await cursor.fetchone()
