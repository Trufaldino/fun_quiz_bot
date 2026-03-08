import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")

MIN_PLAYERS = 2
MAX_PLAYERS = 10

ANSWER_TIMEOUT = 90
VOTE_TIMEOUT = 30

SCORE_PER_VOTE = 1000
QUIPLASH_BONUS = 2000

DB_PATH = "quiplash.db"

LOBBY_LIFETIME_SECONDS = 2 * 60 * 60  # 2 часа
CLEANUP_INTERVAL_SECONDS = 5 * 60     # проверка каждые 5 минут

DEFAULT_ANSWER = "*молчит как рыба*"
