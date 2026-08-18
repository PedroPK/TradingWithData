# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [1.5.0] - 2026-08-18

### Adicionado
- Novo script `src/ibovespa_components.py` para consultar a composição atual do **Ibovespa** a partir da carteira teórica da B3
- Suporte a saída em **JSON** (`--json`) e exportação em **CSV** (`--csv`) para a lista de componentes do índice
- Testes automatizados cobrindo a normalização do payload retornado pela B3

### Alterado
- `README.md` atualizado com instruções de uso do novo script e descrição da consulta da composição atual do índice

---

## [1.4.0] - 2026-03-28

### Adicionado
- Publicação automática do gráfico no **GitHub Pages** (`docs/index.html`)
- **GitHub Actions** (`.github/workflows/update_chart.yml`) que executa o script semanalmente (segundas às 8h BRT) e a cada disparo manual
- Exportação do gráfico como HTML interativo via `fig.write_html()` com Plotly embutido via CDN
- Página `docs/index.html` criada como placeholder inicial para o GitHub Pages

### Alterado
- Script adaptado para não abrir o browser automaticamente quando executado em ambiente CI (`CI=true`)
- Exportação de PNG agora é tolerante a falhas (não interrompe a execução em ambientes sem kaleido)
- `README.md` atualizado com instruções de ativação do GitHub Pages e nova estrutura de pastas

---

## [1.3.0] - 2026-03-08

### Adicionado
- Exportação automática do gráfico como imagem PNG em `output/ibovespa_comparativo.png` via **kaleido**
- Dependência `kaleido>=0.2.1` adicionada ao `requirements.txt`
- Imagem de exemplo do gráfico referenciada no `README.md`

---

## [1.2.0] - 2026-03-08

### Adicionado
- Suporte ao **S&P 500** (`^GSPC`) como novo indexador de comparação
- Curva `S&P 500 (USD)` normalizada e exibida no gráfico (linha vermelha tracejada)
- Título do gráfico atualizado para incluir o S&P 500

---

## [1.1.0] - 2026-03-07

### Adicionado
- Suporte ao **Ouro Futuro** (`GC=F`) como novo indexador de comparação
- Curva `Ibovespa em Ouro` calculada e exibida no gráfico interativo
- Configuração de ambiente virtual com `requirements.txt`
- Documentação de instalação e execução no `README.md`
- Este arquivo `CHANGELOG.md`

### Alterado
- Gráfico atualizado para incluir a serie de Ouro com cor `#FFD700`
- Título do gráfico revisado para refletir os cinco indexadores

---

## [1.0.0] - 2024-01-01

### Adicionado
- Script principal `src/index_comparator.py`
- Notebook interativo `10_Trading_com_Dados_IBOV_em_Dolar,_IPCA_e_BTC.ipynb`
- Coleta de dados via **yfinance**: Ibovespa, USD/BRL, BTC/USD
- Coleta do **IPCA mensal** via API SIDRA (IBGE)
- Cálculo do Ibovespa em quatro perspectivas: Nominal (R$), Real (IPCA), Dólar e Bitcoin
- Normalização das curvas com base 100 na data de início
- Gráfico interativo com **Plotly** em escala logarítmica
