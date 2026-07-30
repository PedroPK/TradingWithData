from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import index_comparator as comparator


def test_build_ipca_daily_skips_header_row():
    payload = [
        {"M": "Variável", "V": "Valor"},
        {"M": "201912", "V": "0,50"},
        {"M": "202001", "V": "0,25"},
    ]

    ipca_daily = comparator.build_ipca_daily(payload)

    assert "ipca_factor" in ipca_daily.columns
    assert ipca_daily.loc["2020-01-01", "ipca_factor"] == pytest.approx(1.0075125)


def test_build_comparison_dataframe_alignment_and_expected_values(deterministic_prices_df, deterministic_ipca_payload):
    ipca_daily = comparator.build_ipca_daily(deterministic_ipca_payload)
    df = comparator.build_comparison_dataframe(deterministic_prices_df, ipca_daily)

    assert pd.Timestamp("2020-01-03") not in df.index
    assert df.loc["2020-01-01", "Ibovespa_Real"] == pytest.approx(100000 / 1.0075125)
    assert df.loc["2020-01-01", "Ibovespa_USD"] == pytest.approx(25000.0)
    assert df.loc["2020-01-01", "Ibovespa_Gold"] == pytest.approx((100000 / 4.0) / 1500.0)


def test_build_comparison_dataframe_zero_denominator_results_in_inf(deterministic_prices_df, deterministic_ipca_payload):
    prices = deterministic_prices_df.copy()
    prices.loc["2020-01-02", "BTC/USD"] = 0.0

    ipca_daily = comparator.build_ipca_daily(deterministic_ipca_payload)
    df = comparator.build_comparison_dataframe(prices, ipca_daily)

    assert np.isinf(df.loc["2020-01-02", "Ibovespa_BTC"])


def test_normalize_aligned_with_delayed_first_valid_index():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    series = pd.Series([np.nan, 10.0, 20.0], index=idx)
    ibov = pd.Series([100.0, 110.0, 120.0], index=idx)

    normalized = comparator.normalize_aligned(series, ibov, base_ibov=100.0)

    assert np.isnan(normalized.iloc[0])
    assert normalized.iloc[1] == pytest.approx(1.1)
    assert normalized.iloc[2] == pytest.approx(2.2)


def test_build_normalized_dataframe_outputs_expected_shape(deterministic_prices_df, deterministic_ipca_payload):
    ipca_daily = comparator.build_ipca_daily(deterministic_ipca_payload)
    df = comparator.build_comparison_dataframe(deterministic_prices_df, ipca_daily)

    df_norm, base_ibov = comparator.build_normalized_dataframe(df)

    assert base_ibov == pytest.approx(100000.0)
    assert df_norm.index.equals(df.index)
    assert set(df_norm.columns) == {
        "Ibovespa",
        "Ibovespa_Real",
        "Ibovespa_USD",
        "Ibovespa_BTC",
        "Ibovespa_Gold",
        "Ibovespa_SP500",
    }
    assert df_norm.iloc[0]["Ibovespa"] == pytest.approx(1.0)


def test_build_normalized_dataframe_rejects_empty_dataframe():
    with pytest.raises(ValueError, match="DataFrame de comparação vazio"):
        comparator.build_normalized_dataframe(pd.DataFrame())
