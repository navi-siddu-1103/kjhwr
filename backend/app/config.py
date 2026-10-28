from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MIN_DATE, MAX_DATE = date(2026, 1, 1), date(2026, 1, 31)
DEFAULT_CUTOFF_HOUR = 9