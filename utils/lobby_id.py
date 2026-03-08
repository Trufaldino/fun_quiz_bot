import random

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LOBBY_ID_LENGTH = 6


def generate_lobby_id() -> str:
    return "".join(random.choices(ALPHABET, k=LOBBY_ID_LENGTH))
