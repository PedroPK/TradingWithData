import argparse
import os
from pathlib import Path
import webbrowser

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


DEFAULT_START_DATE = '2010-01-01'
TICKERS = ['USDBRL=X', 'DX-Y.NYB']


def get_price_data(start_date=DEFAULT_START_DATE):
    """Download USD/BRL and the US Dollar Index from Yahoo Finance."""
    data = yf.download(TICKERS, start=start_date, auto_adjust=False, progress=False)
    if data.empty or not isinstance(data.columns, pd.MultiIndex) or 'Close' not in data.columns:
        raise ValueError('Não foi possível obter os fechamentos de USD/BRL e Dollar Index.')
    prices = data['Close']
    if any(ticker not in prices.columns for ticker in TICKERS):
        raise ValueError('O Yahoo Finance não retornou ambas as séries solicitadas.')
    return prices[TICKERS].rename(columns={'USDBRL=X': 'USD/BRL', 'DX-Y.NYB': 'Dollar Index'})


def prepare_comparison(prices):
    """Align observed prices without filling missing dates and calculate returns."""
    columns = ['USD/BRL', 'Dollar Index']
    if not set(columns).issubset(prices.columns):
        raise ValueError('São necessárias as séries USD/BRL e Dollar Index.')
    aligned = prices[columns].apply(pd.to_numeric, errors='raise').dropna().sort_index()
    if len(aligned) < 3:
        raise ValueError('São necessárias pelo menos três datas com cotações para ambas as séries.')
    if not aligned.index.is_unique:
        raise ValueError('As datas das cotações não podem estar duplicadas.')
    if not ((aligned > 0) & (aligned < float('inf'))).all().all():
        raise ValueError('As cotações devem ser positivas e finitas.')
    returns = aligned.pct_change().dropna()
    correlation = returns['USD/BRL'].corr(returns['Dollar Index'])
    normalized = aligned.div(aligned.iloc[0]).mul(100)
    return aligned, normalized, returns, correlation


def build_figure(normalized):
    fig = go.Figure()
    for column, color in [('USD/BRL', '#0066cc'), ('Dollar Index', '#d35400')]:
        fig.add_trace(go.Scatter(
            x=normalized.index, y=normalized[column], name=column,
            mode='lines', line=dict(color=color, width=2),
        ))
    fig.update_layout(
        title='USD/BRL e Dollar Index — evolução normalizada',
        xaxis_title='Data',
        yaxis_title='Índice (primeira data comum = 100)',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h'),
    )
    return fig


def run_pipeline(start_date=DEFAULT_START_DATE, docs_dir=None, show_browser=None):
    if docs_dir is None:
        docs_dir = Path(__file__).resolve().parents[1] / 'docs'
    aligned, normalized, returns, correlation = prepare_comparison(get_price_data(start_date))
    fig = build_figure(normalized)
    correlation_text = f'{correlation:.3f}' if pd.notna(correlation) else 'indisponível (retornos constantes)'
    start = aligned.index[0].strftime('%d/%m/%Y')
    end = aligned.index[-1].strftime('%d/%m/%Y')
    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dólar em reais e Dollar Index</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #233044; max-width: 1200px; margin: auto; padding: 1.5rem; line-height: 1.5; }}
    .summary {{ background: #eef4fa; padding: 1rem 1.25rem; border-radius: 0.5rem; }}
    .chart {{ width: 100%; }}
  </style>
</head>
<body>
  <main>
    <h1>Dólar em reais e Dollar Index</h1>
    <p>Compare a variação do dólar frente ao real com sua evolução frente a uma cesta de moedas internacionais.</p>
    <div class="summary">
      <strong>Correlação de Pearson dos retornos entre datas comuns: {correlation_text}</strong>
      <br>Período completo: {start} a {end}; {len(returns)} retornos.
      <br>Variação acumulada: USD/BRL {normalized['USD/BRL'].iloc[-1] - 100:+.2f}%;
      Dollar Index {normalized['Dollar Index'].iloc[-1] - 100:+.2f}%.
    </div>
    <div class="chart">{fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})}</div>
    <p>As séries começam em 100 na primeira data comum. Os retornos são calculados entre observações
    consecutivas comuns, sem preencher cotações ausentes. A correlação resume todo o período acima e
    não muda ao ampliar o gráfico; valores próximos de 1 indicam movimentos semelhantes, próximos
    de -1 movimentos opostos e próximos de 0 pouca relação linear.</p>
    <p>O Dollar Index mede o dólar em relação a uma cesta específica de moedas, não a todas as moedas
    globais. Divergências podem refletir fatores locais ou outros fatores; correlação não demonstra causa.</p>
    <p>Fonte: Yahoo Finance, fechamentos de USDBRL=X e DX-Y.NYB. Dados sujeitos a disponibilidade e revisão.</p>
    <p><a href="index.html">Ver comparativo do Ibovespa</a></p>
  </main>
</body>
</html>
'''
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    html_path = docs_dir / 'dolar.html'
    html_path.write_text(html, encoding='utf-8')
    print(f'HTML interativo salvo em: {html_path}')
    if show_browser is None:
        show_browser = not bool(os.environ.get('CI'))
    if show_browser:
        webbrowser.open(html_path.resolve().as_uri())
    return html_path


def main():
    parser = argparse.ArgumentParser(description='Comparar USD/BRL com o Dollar Index.')
    parser.add_argument('--start-date', default=DEFAULT_START_DATE, help='Data inicial (AAAA-MM-DD).')
    parser.add_argument('--docs-dir', default=None, help='Diretório de saída da página HTML.')
    parser.add_argument('--no-show', action='store_true', help='Não abrir a página no navegador.')
    args = parser.parse_args()
    run_pipeline(start_date=args.start_date, docs_dir=args.docs_dir, show_browser=False if args.no_show else None)


if __name__ == '__main__':
    main()
