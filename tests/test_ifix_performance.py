import json

import pandas as pd
import pytest

from src import ifix_performance
from src import ibovespa_performance


def test_decode_tradingview_messages_extracts_timescale_update():
    payload = {
        "m": "timescale_update",
        "p": ["cs_ifix", {"s1": {"s": [{"i": 0, "v": [1787144400.0, 1, 2, 1, 3685.89]}]}}],
    }
    body = json.dumps(payload, separators=(",", ":"))

    messages = ifix_performance._decode_tradingview_messages(f"~m~{len(body)}~m~{body}")

    assert messages == [payload]


def test_build_plot_dataframe_and_figure_label_ifix():
    index = pd.date_range("2026-08-17", periods=2, freq="D")
    performance_df = pd.DataFrame(
        {
            "ticker": ["AAA11", "BBB11"],
            "company": ["FII A", "FII B"],
            "return_percent": [10.0, -5.0],
        }
    )
    price_history = pd.DataFrame({"AAA11": [100.0, 110.0], "BBB11": [100.0, 95.0]}, index=index)
    ifix_history = pd.Series([3600.0, 3685.89], index=index)

    plot_df = ibovespa_performance.build_plot_dataframe(
        performance_df=performance_df,
        price_history=price_history,
        ibovespa_history=ifix_history,
        plot_count=2,
        index_name="IFIX",
    )
    value_df = ibovespa_performance.build_plot_dataframe(
        performance_df=performance_df,
        price_history=price_history,
        ibovespa_history=ifix_history,
        plot_count=2,
        index_name="IFIX",
        normalize=False,
    )
    figure = ibovespa_performance.build_performance_figure(
        plot_df=plot_df,
        requested_start_date="2026-08-17",
        requested_end_date="2026-08-18",
        plot_count=2,
        index_name="IFIX",
        value_df=value_df,
    )

    assert list(plot_df.columns) == ["IFIX", "AAA11 - FII A", "BBB11 - FII B"]
    assert plot_df.iloc[0]["IFIX"] == pytest.approx(100.0)
    assert "componentes selecionados do IFIX" in figure.layout.title.text
    assert figure.data[0].name == "IFIX"
    assert figure.layout.updatemenus[0].buttons[0].args[0]["text"][0] == ["3600.00 pontos", "3685.89 pontos"]
    assert figure.layout.updatemenus[0].buttons[0].args[0]["text"][1] == ["R$ 100,00", "R$ 110,00"]
