"""Настройки приложения. Все значения можно переопределить переменными окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]          # корень репозитория
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
REFERENCE_DIR = Path(os.getenv("REFERENCE_DIR", DATA_DIR / "reference"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", DATA_DIR / "uploads"))
DEMO_DIR = Path(os.getenv("DEMO_DIR", BASE_DIR / "demo"))
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", BASE_DIR / "frontend" / "dist"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}")

# Пороги по умолчанию (рабочие значения прототипа, уточняются на пилоте)
DEFAULT_PRICE_THRESHOLDS = (15.0, 30.0)      # % отклонения цены: средний, высокий
DEFAULT_VOLUME_THRESHOLDS = (25.0, 50.0)     # % отклонения удельного расхода
DEFAULT_ESCALATION_THRESHOLDS = (10.0, 20.0) # % превышения удорожания над индексом

# Границы показателя сопоставимости
MATCH_HIGH = 0.90
MATCH_MEDIUM = 0.75
MATCH_MIN = 0.60

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
