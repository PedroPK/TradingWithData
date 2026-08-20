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


def test_select_plot_tickers_balances_top_and_bottom_performers():
    performance_df = pd.DataFrame(
        {
            "ticker": ["AAA3", "BBB4", "CCC3", "DDD3", "EEE3", "FFF3"],
            "company": ["A", "B", "C", "D", "E", "F"],
            "return_percent": [60.0, 50.0, 40.0, -10.0, -20.0, -30.0],
        }
    )

    selected = ibovespa_performance.select_plot_tickers(performance_df, 4)

    assert selected == ["AAA3", "BBB4", "EEE3", "FFF3"]


def test_build_plot_dataframe_includes_ibovespa_and_selected_tickers():
    performance_df = pd.DataFrame(
        {
            "ticker": ["AAA3", "BBB4", "CCC3", "DDD3"],
            "company": ["Empresa A", "Empresa B", "Empresa C", "Empresa D"],
            "return_percent": [50.0, 20.0, -10.0, -30.0],
        }
    )
    index = pd.to_datetime(["2022-08-18", "2022-08-19", "2022-08-22"])
    price_history = pd.DataFrame(
        {
            "AAA3": [10.0, 12.0, 15.0],
            "BBB4": [20.0, 22.0, 24.0],
            "CCC3": [30.0, 29.0, 28.0],
            "DDD3": [40.0, 38.0, 35.0],
        },
        index=index,
    )
    ibovespa_history = pd.Series([100000.0, 101000.0, 102000.0], index=index, name="^BVSP")

    plot_df = ibovespa_performance.build_plot_dataframe(
        performance_df=performance_df,
        price_history=price_history,
        ibovespa_history=ibovespa_history,
        plot_count=2,
    )

    assert list(plot_df.columns) == ["Ibovespa", "AAA3 - Empresa A", "DDD3 - Empresa D"]
    assert plot_df.iloc[0]["Ibovespa"] == pytest.approx(100.0)
    assert plot_df.iloc[0]["AAA3 - Empresa A"] == pytest.approx(100.0)
    assert plot_df.iloc[-1]["DDD3 - Empresa D"] == pytest.approx(87.5)


def test_build_performance_figure_separates_title_and_legend():
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    plot_df = pd.DataFrame(
        {"Ibovespa": [100.0, 101.0], "AAA3 - Empresa A": [100.0, 105.0]},
        index=index,
    )

    figure = ibovespa_performance.build_performance_figure(
        plot_df=plot_df,
        requested_start_date="2024-01-01",
        requested_end_date="2024-01-02",
        plot_count=2,
    )

    assert figure.layout.title.y > figure.layout.legend.y
    assert figure.layout.yaxis.domain == (0, 0.86)


def test_build_performance_figure_defaults_hover_to_named_percent_changes():
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    plot_df = pd.DataFrame(
        {"Ibovespa": [100.0, 102.0], "AAA3 - Empresa A": [100.0, 95.0]},
        index=index,
    )
    value_df = pd.DataFrame(
        {"Ibovespa": [120000.0, 122400.0], "AAA3 - Empresa A": [10.0, 9.5]},
        index=index,
    )

    figure = ibovespa_performance.build_performance_figure(
        plot_df=plot_df,
        requested_start_date="2024-01-01",
        requested_end_date="2024-01-02",
        plot_count=2,
        value_df=value_df,
    )

    assert figure.data[0].hovertemplate == "<b>Ibovespa</b>: %{text}<extra></extra>"
    assert figure.data[1].hovertemplate == "<b>AAA3 - Empresa A</b>: %{text}<extra></extra>"
    assert figure.data[0].text == ("+0.00%", "+2.00%")
    buttons = figure.layout.updatemenus[0].buttons
    assert figure.layout.updatemenus[0].active == 1
    assert [button.label for button in buttons] == ["Valores (R$ / pontos)", "Variação (%)"]
    assert buttons[0].args[0]["text"][0] == ["120000.00 pontos", "122400.00 pontos"]
    assert buttons[0].args[0]["text"][1] == ["R$ 10,00", "R$ 9,50"]


def test_export_performance_plot_sorts_hover_entries_by_cursor_value(tmp_path):
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    plot_df = pd.DataFrame(
        {
            "Ibovespa": [100.0, 102.0],
            "AAA3 - Empresa A": [100.0, 110.0],
            "BBB4 - Empresa B": [100.0, 90.0],
        },
        index=index,
    )

    figure = ibovespa_performance.build_performance_figure(
        plot_df=plot_df,
        requested_start_date="2024-01-01",
        requested_end_date="2024-01-02",
        plot_count=2,
    )

    html_path = ibovespa_performance.export_performance_plot(
        figure,
        output_dir=str(tmp_path),
        show_browser=False,
    )
    html = open(html_path, encoding="utf-8").read()

    assert 'graph.on("plotly_beforehover"' in html
    assert "trace.index = rank;" in html
    assert "Variação (%)" in html
