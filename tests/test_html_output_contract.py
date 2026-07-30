from pathlib import Path

from src import index_comparator as comparator


def _generate_html_with_mocks(monkeypatch, tmp_path, deterministic_prices_df, deterministic_ipca_payload):
    monkeypatch.setattr(comparator, "get_price_data", lambda start_date=comparator._DEFAULT_START_DATE: deterministic_prices_df)
    monkeypatch.setattr(comparator, "_fetch_ipca", lambda: deterministic_ipca_payload)

    def fake_write_image(self, file, width=0, height=0, scale=1):
        Path(file).write_bytes(b"png")

    monkeypatch.setattr(comparator.go.Figure, "write_image", fake_write_image)

    docs_dir = tmp_path / "docs"
    output_dir = tmp_path / "output"
    result = comparator.run_pipeline(docs_dir=str(docs_dir), output_dir=str(output_dir), show_browser=False)
    html_path = Path(result["html_path"])
    return html_path.read_text(encoding="utf-8")


def test_html_contains_all_expected_series(monkeypatch, tmp_path, deterministic_prices_df, deterministic_ipca_payload):
    html = _generate_html_with_mocks(monkeypatch, tmp_path, deterministic_prices_df, deterministic_ipca_payload)

    expected_series = [
        "Ibovespa Nominal (R$)",
        "Corrigido pelo IPCA",
        "Em Ouro",
        "Em S&P 500",
        "Em Bitcoin",
    ]

    for series_name in expected_series:
        assert series_name in html

    assert ("Em Dólar" in html) or ("Em D\\u00f3lar" in html)


def test_html_contains_key_layout_contract(monkeypatch, tmp_path, deterministic_prices_df, deterministic_ipca_payload):
    html = _generate_html_with_mocks(monkeypatch, tmp_path, deterministic_prices_df, deterministic_ipca_payload)

    assert "Ibovespa vs Indexadores" in html
    assert '"type":"log"' in html
    assert '"hovermode":"x unified"' in html


def test_figure_contract_has_six_traces_and_log_axis(deterministic_prices_df, deterministic_ipca_payload):
    ipca_daily = comparator.build_ipca_daily(deterministic_ipca_payload)
    df = comparator.build_comparison_dataframe(deterministic_prices_df, ipca_daily)
    df_norm, base_ibov = comparator.build_normalized_dataframe(df)
    fig = comparator.build_figure(df_norm, base_ibov)

    assert len(fig.data) == 6
    names = {trace.name for trace in fig.data}
    assert names == {
        "Ibovespa Nominal (R$)",
        "Corrigido pelo IPCA",
        "Em Dólar",
        "Em Ouro",
        "Em S&P 500",
        "Em Bitcoin",
    }
    assert fig.layout.yaxis.type == "log"
    assert fig.layout.hovermode == "x unified"
