import pandas as pd
import pytest

from src import dollar_comparator as comparator


def sample_prices():
    return pd.DataFrame(
        {
            'USD/BRL': [4.0, 4.4, 99.0, 5.28, 5.544],
            'Dollar Index': [100.0, 110.0, None, 132.0, 138.6],
        },
        index=pd.date_range('2020-01-01', periods=5),
    )


def test_aligns_observed_prices_and_correlates_returns():
    aligned, normalized, returns, correlation = comparator.prepare_comparison(sample_prices())

    assert len(aligned) == 4
    assert pd.Timestamp('2020-01-03') not in aligned.index
    assert normalized.iloc[0].tolist() == [100.0, 100.0]
    assert returns['USD/BRL'].tolist() == pytest.approx([0.1, 0.2, 0.05])
    assert correlation == pytest.approx(1.0)


def test_correlation_uses_returns_not_price_levels():
    prices = pd.DataFrame(
        {'USD/BRL': [1.0, 2.0, 3.0, 6.0], 'Dollar Index': [10.0, 20.0, 40.0, 60.0]},
        index=pd.date_range('2020-01-01', periods=4),
    )
    _, _, _, correlation = comparator.prepare_comparison(prices)
    assert correlation == pytest.approx(-0.5)


@pytest.mark.parametrize(
    'prices, message',
    [
        (sample_prices().iloc[:3], 'pelo menos três'),
        (sample_prices().assign(**{'USD/BRL': 0}), 'positivas e finitas'),
        (sample_prices().drop(columns=['Dollar Index']), 'necessárias as séries'),
    ],
)
def test_invalid_data_fails_explicitly(prices, message):
    with pytest.raises(ValueError, match=message):
        comparator.prepare_comparison(prices)


def test_download_requires_both_series(monkeypatch):
    data = pd.DataFrame(
        {('Close', 'USDBRL=X'): [4.0]},
        index=pd.date_range('2020-01-01', periods=1),
    )
    monkeypatch.setattr(comparator.yf, 'download', lambda *args, **kwargs: data)
    with pytest.raises(ValueError, match='ambas as séries'):
        comparator.get_price_data()


def test_download_extracts_and_renames_close_prices(monkeypatch):
    data = pd.DataFrame(
        {('Close', 'USDBRL=X'): [4.0], ('Close', 'DX-Y.NYB'): [100.0],
         ('Open', 'USDBRL=X'): [3.9], ('Open', 'DX-Y.NYB'): [99.0]},
        index=pd.date_range('2020-01-01', periods=1),
    )
    monkeypatch.setattr(comparator.yf, 'download', lambda *args, **kwargs: data)
    prices = comparator.get_price_data()
    assert prices.columns.tolist() == ['USD/BRL', 'Dollar Index']
    assert prices.iloc[0].tolist() == [4.0, 100.0]


def test_pipeline_writes_independent_page(monkeypatch, tmp_path):
    prices = sample_prices()
    prices['Dollar Index'] = [100.0, 105.0, None, 115.0, 130.0]
    monkeypatch.setattr(comparator, 'get_price_data', lambda start_date: prices)
    existing = tmp_path / 'index.html'
    existing.write_text('existing page', encoding='utf-8')

    path = comparator.run_pipeline(docs_dir=tmp_path, show_browser=False)
    html = path.read_text(encoding='utf-8')

    assert path.name == 'dolar.html'
    assert existing.read_text(encoding='utf-8') == 'existing page'
    assert 'USD/BRL' in html and 'Dollar Index' in html
    assert '01/01/2020 a 05/01/2020; 3 retornos' in html
    assert 'Correlação de Pearson' in html
    assert 'USD/BRL +38.60%' in html and 'Dollar Index +30.00%' in html
    assert 'não muda ao ampliar o gráfico' in html


def test_constant_returns_report_unavailable_correlation(monkeypatch, tmp_path):
    prices = sample_prices()
    prices['USD/BRL'] = 4.0
    monkeypatch.setattr(comparator, 'get_price_data', lambda start_date: prices)
    html = comparator.run_pipeline(docs_dir=tmp_path, show_browser=False).read_text(encoding='utf-8')
    assert 'indisponível (retornos constantes)' in html
