"""Örnek (kurgusal) veri: 20 kurum ihtiyacı ve 40 girişim profili."""

import json
from pathlib import Path

from app.schemas import StartupProfile

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


def load_startups() -> list[StartupProfile]:
    raw = json.loads((SEED_DIR / "startups.json").read_text(encoding="utf-8"))
    return [StartupProfile.model_validate(item) for item in raw]


def load_needs() -> list[dict]:
    return json.loads((SEED_DIR / "needs.json").read_text(encoding="utf-8"))
