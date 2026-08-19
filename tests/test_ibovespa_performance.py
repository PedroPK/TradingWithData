import pandas as pd
import pytest

from src import ibovespa_performance


def test_resolve_period_defaults_to_last_four_years():
    start_date, end_date = ibovespa_performance.resolve_period(today="2026-08-18")

    assert start_date == pd.Timestamp("2022-08-18")
    assert end_date == pd.Timestamp("2026-08-18")


def test_extract_close_prices_normalizes_multiindex_columns():
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    columns = pd.MultiIndex.from_product([["Close"], ["ABEV3.SA", "VALE3.SA"]])
    price_data = pd.DataFrame([[10.0, 50.0], [11.0, 55.0]], index=index, columns=columns)

    close_prices = ibovespa_performance.extract_close_prices(price_data, ["ABEV3.SA", "VALE3.SA"])

    assert list(close_prices.columns) == ["ABEV3", "VALE3"]
    assert close_prices.loc[pd.Timestamp("2024-01-02"), "VALE3"] == pytest.approx(55.0)


def test_build_performance_dataframe_sorts_from_best_to_worst():
    components = pd.DataFrame(
        [
            {"ticker": "AAA3", "company": "Empresa A", "share_type": "ON", "weight_percent": 1.2},
            {"ticker": "BBB4", "company": "Empresa B", "share_type": "PN", "weight_percent": 2.3},
            {"ticker": "CCC3", "company": "Empresa C", "share_type": "ON", "weight_percent": 3.4},
            {"ticker": "DDD3", "company": "Empresa D", "share_type": "ON", "weight_percent": 0.5},
        ]
    )
    index = pd.to_datetime(["2022-08-18", "2023-01-02", "2026-08-18"])
    price_history = pd.DataFrame(
        {
            "AAA3": [10.0, 12.0, 15.0],
            "BBB4": [20.0, 19.0, 18.0],
            "CCC3": [5.0, 6.0, 7.0],
            "DDD3": [None, None, None],
        },
        index=index,
    )

    performance_df, missing_tickers = ibovespa_performance.build_performance_dataframe(components, price_history)

    assert performance_df["ticker"].tolist() == ["AAA3", "CCC3", "BBB4"]
    assert performance_df["return_percent"].tolist() == pytest.approx([50.0, 40.0, -10.0], rel=1e-6, abs=1e-6)
    assert performance_df.loc[0, "start_date"] == "2022-08-18"
    assert performance_df.loc[2, "end_price"] == pytest.approx(18.0)
    assert missing_tickers == ["DDD3"]
