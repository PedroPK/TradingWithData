import os
import time
import argparse
import requests
import yfinance as yf
import sidrapy
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# IBGE SIDRA API — helper with retry / exponential backoff
# ---------------------------------------------------------------------------
_IBGE_MAX_RETRIES = 5
_IBGE_BACKOFF_BASE = 2   # seconds
_IBGE_MAX_WAIT = 32      # seconds (cap to prevent unbounded wait times)
_DEFAULT_START_DATE = '2010-01-01'
_DEFAULT_TICKERS = ['^BVSP', 'USDBRL=X', 'BTC-USD', 'GC=F', '^GSPC']


def _fetch_ipca():
    """Fetch IPCA data from IBGE SIDRA API with retry/exponential-backoff for transient failures."""
    effective_retries = max(1, _IBGE_MAX_RETRIES)
    exc_to_raise = None
    for attempt in range(effective_retries):
        try:
            return sidrapy.get_table(
                table_code='1737',
                territorial_level='1',
                ibge_territorial_code='1',
                variable='63',
                period='all'
            )
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as exc:
            exc_to_raise = exc
        except requests.exceptions.HTTPError as exc:
            # Retry only on confirmed 5xx responses; re-raise immediately for anything else
            # (4xx, unknown status codes outside 500-599, or absent response object)
            if exc.response is None or not (500 <= exc.response.status_code < 600):
                raise
            exc_to_raise = exc

        if attempt == effective_retries - 1:
            raise exc_to_raise  # type: ignore[misc]
        wait = min(_IBGE_BACKOFF_BASE ** (attempt + 1), _IBGE_MAX_WAIT)
        print(f"IBGE API error (attempt {attempt + 1}/{effective_retries}): {exc_to_raise}. "
              f"Retrying in {wait}s...")
        time.sleep(wait)


def get_price_data(start_date=_DEFAULT_START_DATE, tickers=None):
    """Fetch and normalize price series from yfinance."""
    if tickers is None:
        tickers = _DEFAULT_TICKERS

    data_yf = yf.download(tickers, start=start_date)

    if isinstance(data_yf.columns, pd.MultiIndex):
        df_prices = data_yf['Close'].copy()
    else:
        df_prices = data_yf.copy()

    df_prices = df_prices.rename(columns={
        '^BVSP': 'Ibovespa',
        'USDBRL=X': 'USD/BRL',
        'BTC-USD': 'BTC/USD',
        'GC=F': 'Gold_USD',
        '^GSPC': 'SP500_USD'
    })
    df_prices = df_prices.dropna(subset=['Ibovespa'])
    return df_prices


def build_ipca_daily(ipca_data):
    """Clean SIDRA payload and return a daily IPCA factor dataframe."""
    ipca_df = pd.DataFrame(ipca_data)

    if ipca_df.empty:
        raise ValueError('IPCA payload vazio.')

    if ipca_df.iloc[0].astype(str).str.contains('Variável').any():
        ipca_df = ipca_df.iloc[1:].copy()

    data_col = next(col for col in ipca_df.columns if ipca_df[col].astype(str).str.match(r'^\d{6}$').any())
    ipca_df['date'] = pd.to_datetime(ipca_df[data_col], format='%Y%m')

    ipca_df['ipca'] = (
        ipca_df['V']
        .astype(str)
        .str.replace(',', '.', regex=False)
        .replace({'...': None, '': None})
        .astype(float)
    )
    ipca_df = ipca_df.dropna(subset=['ipca'])

    ipca_df = ipca_df[['date', 'ipca']].sort_values('date')
    ipca_df['ipca_var'] = ipca_df['ipca'] / 100
    ipca_df['ipca_factor'] = (1 + ipca_df['ipca_var']).cumprod()
    return ipca_df.set_index('date').resample('D').ffill()


def build_comparison_dataframe(df_prices, ipca_daily):
    """Join prices and inflation and compute derived comparison series."""
    df = df_prices.join(ipca_daily['ipca_factor'], how='left')
    df['ipca_factor'] = df['ipca_factor'].ffill()
    df = df.dropna(subset=['ipca_factor', 'USD/BRL'])

    df['Ibovespa_Real'] = df['Ibovespa'] / df['ipca_factor']
    df['Ibovespa_USD'] = df['Ibovespa'] / df['USD/BRL']
    df['Ibovespa_BTC'] = df['Ibovespa_USD'] / df['BTC/USD']
    df['Ibovespa_Gold'] = df['Ibovespa_USD'] / df['Gold_USD']
    df['Ibovespa_SP500'] = df['Ibovespa_USD'] / df['SP500_USD']
    return df


def normalize_aligned(series, ibov_series, base_ibov):
    """Normalize a series preserving visual alignment to the nominal Ibovespa."""
    first_idx = series.first_valid_index()
    if first_idx is None:
        return series * float('nan')

    base_series_val = series.loc[first_idx]
    base_ibov_at_start = ibov_series.loc[first_idx]
    return (series / base_series_val) * (base_ibov_at_start / base_ibov)


def build_normalized_dataframe(df):
    """Build normalized dataframe used in the chart."""
    if df.empty:
        raise ValueError('DataFrame de comparação vazio.')

    df_norm = pd.DataFrame(index=df.index)
    base_ibov = df['Ibovespa'].iloc[0]
    df_norm['Ibovespa'] = df['Ibovespa'] / base_ibov
    df_norm['Ibovespa_Real'] = normalize_aligned(df['Ibovespa_Real'], df['Ibovespa'], base_ibov)
    df_norm['Ibovespa_USD'] = normalize_aligned(df['Ibovespa_USD'], df['Ibovespa'], base_ibov)
    df_norm['Ibovespa_BTC'] = normalize_aligned(df['Ibovespa_BTC'], df['Ibovespa'], base_ibov)
    df_norm['Ibovespa_Gold'] = normalize_aligned(df['Ibovespa_Gold'], df['Ibovespa'], base_ibov)
    df_norm['Ibovespa_SP500'] = normalize_aligned(df['Ibovespa_SP500'], df['Ibovespa'], base_ibov)
    return df_norm, base_ibov


def build_figure(df_norm, base_ibov):
    """Create plotly figure from normalized comparison data."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_norm.index,
        y=df_norm['Ibovespa'] * base_ibov,
        mode='lines',
        name='Ibovespa Nominal (R$)',
        line=dict(color='blue', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df_norm.index,
        y=df_norm['Ibovespa_Real'] * base_ibov,
        mode='lines',
        name='Corrigido pelo IPCA',
        line=dict(color='green')
    ))
    fig.add_trace(go.Scatter(
        x=df_norm.index,
        y=df_norm['Ibovespa_USD'] * base_ibov,
        mode='lines',
        name='Em Dólar',
        line=dict(color='orange')
    ))
    fig.add_trace(go.Scatter(
        x=df_norm.index,
        y=df_norm['Ibovespa_Gold'] * base_ibov,
        mode='lines',
        name='Em Ouro',
        line=dict(color='#FFD700')
    ))
    fig.add_trace(go.Scatter(
        x=df_norm.index,
        y=df_norm['Ibovespa_SP500'] * base_ibov,
        mode='lines',
        name='Em S&P 500',
        line=dict(color='red')
    ))
    fig.add_trace(go.Scatter(
        x=df_norm.index,
        y=df_norm['Ibovespa_BTC'] * base_ibov,
        mode='lines',
        name='Em Bitcoin',
        line=dict(color='purple')
    ))

    fig.update_layout(
        title='Ibovespa vs Indexadores: Inflação, Dólar, S&P 500, Ouro e Bitcoin (Normalizado e em escala logarítmica)',
        xaxis_title='Anos',
        yaxis_title='Pontuação Ajustada (Escala Logarítmica Recomendada)',
        yaxis_tickformat=',.0f',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        yaxis_type='log'
    )
    return fig


def export_outputs(fig, docs_dir, output_dir, ci_mode):
    """Export HTML and PNG outputs. PNG failure is fatal in CI."""
    os.makedirs(docs_dir, exist_ok=True)
    html_path = os.path.join(docs_dir, 'index.html')
    fig.write_html(html_path, include_plotlyjs='cdn')
    print(f'HTML interativo salvo em: {html_path}')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'ibovespa_comparativo.png')
    try:
        fig.write_image(output_path, width=1400, height=700, scale=2)
        print(f'Gráfico salvo em: {output_path}')
    except Exception as exc:
        if ci_mode:
            raise RuntimeError(f'Falha na exportação de PNG em CI: {exc}') from exc
        print(f'Aviso: não foi possível exportar PNG ({exc})')
    return html_path, output_path


def run_pipeline(start_date=_DEFAULT_START_DATE, root_dir=None, docs_dir=None, output_dir=None, show_browser=None):
    """Run the full data-to-chart pipeline."""
    if root_dir is None:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if docs_dir is None:
        docs_dir = os.path.join(root_dir, 'docs')
    if output_dir is None:
        output_dir = os.path.join(root_dir, 'output')

    ci_mode = bool(os.environ.get('CI'))
    if show_browser is None:
        show_browser = not ci_mode

    df_prices = get_price_data(start_date=start_date)
    ipca_data = _fetch_ipca()
    ipca_daily = build_ipca_daily(ipca_data)
    df = build_comparison_dataframe(df_prices, ipca_daily)
    df_norm, base_ibov = build_normalized_dataframe(df)
    fig = build_figure(df_norm, base_ibov)
    html_path, output_path = export_outputs(fig, docs_dir, output_dir, ci_mode)

    if show_browser:
        fig.show()

    return {'html_path': html_path, 'png_path': output_path}


def _build_arg_parser():
    parser = argparse.ArgumentParser(description='Gerar comparativo do Ibovespa com IPCA, dólar, ouro, S&P 500 e bitcoin.')
    parser.add_argument('--start-date', default=_DEFAULT_START_DATE, help='Data inicial para download do histórico (formato YYYY-MM-DD).')
    parser.add_argument('--root-dir', default=None, help='Diretório raiz para resolução de docs/ e output/.')
    parser.add_argument('--docs-dir', default=None, help='Diretório de saída para o HTML interativo.')
    parser.add_argument('--output-dir', default=None, help='Diretório de saída para o PNG.')
    parser.add_argument('--no-show', action='store_true', help='Não abrir o gráfico no navegador.')
    return parser


def main():
    args = _build_arg_parser().parse_args()
    run_pipeline(
        start_date=args.start_date,
        root_dir=args.root_dir,
        docs_dir=args.docs_dir,
        output_dir=args.output_dir,
        show_browser=not args.no_show
    )


if __name__ == '__main__':
    main()
