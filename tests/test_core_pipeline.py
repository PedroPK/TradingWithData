from pathlib import Path

import pandas as pd
import pytest
import requests

from src import index_comparator as comparator


def _sample_prices():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Ibovespa": [100000.0, 101000.0, 100500.0, 102500.0, 103000.0],
            "USD/BRL": [4.0, 4.1, 4.2, 4.1, 4.0],
            "BTC/USD": [7000.0, 7050.0, 7100.0, 7200.0, 7300.0],
            "Gold_USD": [1500.0, 1510.0, 1505.0, 1520.0, 1530.0],
            "SP500_USD": [3200.0, 3210.0, 3220.0, 3230.0, 3240.0],
        },
        index=idx,
    )


def _sample_ipca_payload():
    return [
        {"M": "202001", "V": "0,50"},
        {"M": "202002", "V": "0,20"},
        {"M": "202003", "V": "0,10"},
    ]


def test_fetch_ipca_retries_transient_errors(monkeypatch):
    calls = {"count": 0}
    waits = []

    def fake_get_table(**kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.Timeout("temporary timeout")
        return _sample_ipca_payload()

    monkeypatch.setattr(comparator.sidrapy, "get_table", fake_get_table)
    monkeypatch.setattr(comparator.time, "sleep", lambda sec: waits.append(sec))

    payload = comparator._fetch_ipca()

    assert calls["count"] == 3
    assert waits == [2, 4]
    assert isinstance(payload, list)


def test_fetch_ipca_does_not_retry_http_4xx(monkeypatch):
    calls = {"count": 0}

    def fake_get_table(**kwargs):
        calls["count"] += 1
        response = requests.Response()
        response.status_code = 403
        raise requests.exceptions.HTTPError("forbidden", response=response)

    monkeypatch.setattr(comparator.sidrapy, "get_table", fake_get_table)
    monkeypatch.setattr(comparator.time, "sleep", lambda _: (_ for _ in ()).throw(AssertionError("sleep should not be called")))

    with pytest.raises(requests.exceptions.HTTPError):
        comparator._fetch_ipca()

    assert calls["count"] == 1


def test_build_ipca_daily_parses_comma_decimal():
    ipca_daily = comparator.build_ipca_daily(_sample_ipca_payload())

    assert "ipca_factor" in ipca_daily.columns
    assert ipca_daily["ipca_factor"].iloc[0] == pytest.approx(1.005)
    assert ipca_daily["ipca_factor"].iloc[-1] > 1.0


def test_pipeline_generates_html_and_png_with_mocks(monkeypatch, tmp_path):
    monkeypatch.setattr(comparator, "get_price_data", lambda start_date=comparator._DEFAULT_START_DATE: _sample_prices())
    monkeypatch.setattr(comparator, "_fetch_ipca", lambda: _sample_ipca_payload())

    def fake_write_image(self, file, width=0, height=0, scale=1):
        Path(file).write_bytes(b"png")

    monkeypatch.setattr(comparator.go.Figure, "write_image", fake_write_image)

    docs_dir = tmp_path / "docs"
    output_dir = tmp_path / "output"
    result = comparator.run_pipeline(docs_dir=str(docs_dir), output_dir=str(output_dir), show_browser=False)

    html_path = Path(result["html_path"])
    png_path = Path(result["png_path"])

    assert html_path.exists()
    assert png_path.exists()
    assert png_path.stat().st_size > 0
    assert "plotly" in html_path.read_text(encoding="utf-8").lower()


def test_png_export_failure_breaks_ci(monkeypatch, tmp_path):
    monkeypatch.setattr(comparator, "get_price_data", lambda start_date=comparator._DEFAULT_START_DATE: _sample_prices())
    monkeypatch.setattr(comparator, "_fetch_ipca", lambda: _sample_ipca_payload())

    def fake_raise_write_image(self, file, width=0, height=0, scale=1):
        raise RuntimeError("kaleido unavailable")

    monkeypatch.setattr(comparator.go.Figure, "write_image", fake_raise_write_image)
    monkeypatch.setenv("CI", "true")

    with pytest.raises(RuntimeError, match="Falha na exportação de PNG em CI"):
        comparator.run_pipeline(docs_dir=str(tmp_path / "docs"), output_dir=str(tmp_path / "output"), show_browser=False)
