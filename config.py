"""
Konfigurasi bot.
Membaca environment variables dari Railway / file .env (jika dipasang).
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()

_owner_raw = os.getenv("OWNER_ID", "0").strip()
try:
    OWNER_ID: int = int(_owner_raw)
except ValueError:
    OWNER_ID = 0


DB_PATH: str = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"


def validate() -> None:
    """Pastikan environment variables wajib sudah diisi."""
    missing = []
    if not DISCORD_TOKEN:
        missing.append("DISCORD_TOKEN")
    if not OWNER_ID:
        missing.append("OWNER_ID")
    if missing:
        raise RuntimeError(
            f"Environment variable berikut belum diisi: {', '.join(missing)}"
        )
