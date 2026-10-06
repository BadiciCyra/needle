"""Seed verisi.

startups.json: 40 kurgusal girişim + needs.json: 20 kurgusal ihtiyaç (testler ve analizler bunlara bağlı).
startups_gercek.json: gerçek girişimler, her kayıtta kaynak linkiyle (STARTUPS_FILE ile seçilir).
"""

import json
from pathlib import Path

from app.schemas import StartupProfile

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


def load_startups(filename: str = "startups.json") -> list[StartupProfile]:
    raw = json.loads((SEED_DIR / filename).read_text(encoding="utf-8"))
    return [StartupProfile.model_validate(item) for item in raw]


def load_needs() -> list[dict]:
    return json.loads((SEED_DIR / "needs.json").read_text(encoding="utf-8"))
