import sys
import json
from pathlib import Path

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def deterministic_prices_df():
    df = pd.read_csv(FIXTURES_DIR / "prices_deterministic.csv", parse_dates=["date"])
    df = df.set_index("date")
    return df


@pytest.fixture
def deterministic_ipca_payload():
    with (FIXTURES_DIR / "ipca_monthly_deterministic.json").open("r", encoding="utf-8") as f:
        return json.load(f)
