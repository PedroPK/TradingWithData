import yfinance as yf
import sidrapy
import pandas as pd
import plotly.graph_objects as go

# 1. Buscar dados diários desde 2010
# Adicionado GC=F (Ouro Futuro) e ^GSPC (S&P 500)
tickers = ['^BVSP', 'USDBRL=X', 'BTC-USD', 'GC=F', '^GSPC']
data_yf = yf.download(tickers, start='2010-01-01')

# 2. Tratamento robusto para as colunas do yfinance
# O yfinance atual pode retornar MultiIndex. Vamos garantir que pegamos apenas o 'Close'.
if isinstance(data_yf.columns, pd.MultiIndex):
    df_prices = data_yf['Close'].copy()
else:
    # Fallback para versões antigas ou comportamento simples
    df_prices = data_yf.copy()

# Renomear para facilitar
df_prices = df_prices.rename(columns={
    '^BVSP': 'Ibovespa',
    'USDBRL=X': 'USD/BRL',
    'BTC-USD': 'BTC/USD',
    'GC=F': 'Gold_USD',  # Preço da onça de ouro em Dólar
    '^GSPC': 'SP500_USD' # S&P 500 em Dólar
})

# Garantir que é numérico e remover falhas no Ibovespa (base do estudo)
df_prices = df_prices.dropna(subset=['Ibovespa'])

# 3. Buscar IPCA mensal via SIDRA
ipca_data = sidrapy.get_table(
    table_code='1737',
    territorial_level='1',
    ibge_territorial_code='1',
    variable='63',
    period='all'
)
ipca_df = pd.DataFrame(ipca_data)

# Limpeza do IPCA
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

# Cálculo do fator acumulado
ipca_df = ipca_df[['date', 'ipca']].sort_values('date')
ipca_df['ipca_var'] = ipca_df['ipca'] / 100
ipca_df['ipca_factor'] = (1 + ipca_df['ipca_var']).cumprod()

# Expandir para diário
ipca_daily = ipca_df.set_index('date').resample('D').ffill()

# 4. Consolidar dados (Juntar Preços + Inflação)
df = df_prices.join(ipca_daily['ipca_factor'], how='left')

# Preencher o IPCA nos dias de fim de semana/feriado com o último valor (forward fill)
df['ipca_factor'] = df['ipca_factor'].ffill()
df = df.dropna(subset=['ipca_factor', 'USD/BRL']) # Remove dias sem cotação de cambio ou inflação

# 5. Calcular indicadores
# Ibov em Reais (Nominal) - Já temos
# Ibov Real (Deflacionado)
df['Ibovespa_Real'] = df['Ibovespa'] / df['ipca_factor']

# Ibov em Dólar
df['Ibovespa_USD'] = df['Ibovespa'] / df['USD/BRL']

# Ibov em Bitcoin (Ibov em Dólar / Preço BTC em Dólar)
df['Ibovespa_BTC'] = df['Ibovespa_USD'] / df['BTC/USD']

# Ibov em Ouro (Ibov em Dólar / Preço Ouro em Dólar)
df['Ibovespa_Gold'] = df['Ibovespa_USD'] / df['Gold_USD']

# Ibov em S&P 500 (Ibov em Dólar / Preço S&P 500 em Dólar)
df['Ibovespa_SP500'] = df['Ibovespa_USD'] / df['SP500_USD']

# 6. Normalizar as curvas (Base 100 ou Base Inicial) para comparação visual
# Vamos usar o primeiro valor válido de cada série para alinhar todas visualmente no gráfico
df_norm = pd.DataFrame(index=df.index)

# Base de referência visual: Ibovespa Nominal
base_ibov = df['Ibovespa'].iloc[0]
df_norm['Ibovespa'] = df['Ibovespa'] / base_ibov

# Função auxiliar para normalizar e alinhar visualmente com o Ibovespa na data de início da série
def normalize_aligned(series, base_global_val):
    first_idx = series.first_valid_index()
    if first_idx is None:
        return series * float('nan')

    base_series_val = series.loc[first_idx]
    # Fator de ajuste: trazer a série para começar no mesmo "y" que o Ibov Nominal naquele dia
    # Se a série começa junto com o Ibov (2010), base_ibov_at_start será igual a base_ibov
    base_ibov_at_start = df['Ibovespa'].loc[first_idx]

    return (series / base_series_val) * (base_ibov_at_start / base_ibov)

df_norm['Ibovespa_Real'] = normalize_aligned(df['Ibovespa_Real'], base_ibov)
df_norm['Ibovespa_USD']  = normalize_aligned(df['Ibovespa_USD'], base_ibov)
df_norm['Ibovespa_BTC']  = normalize_aligned(df['Ibovespa_BTC'], base_ibov)
df_norm['Ibovespa_Gold'] = normalize_aligned(df['Ibovespa_Gold'], base_ibov)
df_norm['Ibovespa_SP500'] = normalize_aligned(df['Ibovespa_SP500'], base_ibov)

# 7. Criar gráfico
fig = go.Figure()

# Nominal
fig.add_trace(go.Scatter(x=df_norm.index, y=df_norm['Ibovespa'] * base_ibov,
                         mode='lines', name='Ibovespa Nominal (R$)', line=dict(color='blue', width=2)))

# IPCA
fig.add_trace(go.Scatter(x=df_norm.index, y=df_norm['Ibovespa_Real'] * base_ibov,
                         mode='lines', name='Corrigido pelo IPCA', line=dict(color='green')))

# Dólar
fig.add_trace(go.Scatter(x=df_norm.index, y=df_norm['Ibovespa_USD'] * base_ibov,
                         mode='lines', name='Em Dólar', line=dict(color='orange')))

# Ouro (Novo)
fig.add_trace(go.Scatter(x=df_norm.index, y=df_norm['Ibovespa_Gold'] * base_ibov,
                         mode='lines', name='Em Ouro', line=dict(color='#FFD700')))

# S&P 500
fig.add_trace(go.Scatter(x=df_norm.index, y=df_norm['Ibovespa_SP500'] * base_ibov,
                         mode='lines', name='Em S&P 500', line=dict(color='red')))

# Bitcoin
fig.add_trace(go.Scatter(x=df_norm.index, y=df_norm['Ibovespa_BTC'] * base_ibov,
                         mode='lines', name='Em Bitcoin', line=dict(color='purple')))

fig.update_layout(
    title='Ibovespa vs Indexadores: Inflação, Dólar, S&P 500, Ouro e Bitcoin (Normalizado e em escala logarítmica)',
    xaxis_title='Anos',
    yaxis_title='Pontuação Ajustada (Escala Logarítmica Recomendada)',
    yaxis_tickformat=',.0f',
    hovermode='x unified',
    template='plotly_white',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    # Dica: Em gráficos com Bitcoin, escala logarítmica ajuda muito a visualizar
    yaxis_type="log"
)

fig.show()
