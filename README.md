# TradingWithData

Comparativo do índice iBovespa, medido em **Reais nominais**, com outros índices financeiros, tais como o **IPCA**, convertido para **Dólar**, ajustado ao **Ouro** e **Bitcoin** (este último com dados históricos desde 2010).

> Veja o [CHANGELOG](CHANGELOG.md) para o histórico de versões.

---

## Requisitos

- Python **3.10+**
- `git` (opcional, para clonar o repositório)

---

## Instalação

### 1. Clone o repositório (ou abra a pasta no VS Code)

```bash
git clone https://github.com/<seu-usuario>/TradingWithData.git
cd TradingWithData
```

### 2. Crie e ative o ambiente virtual

```bash
# Criar
python3 -m venv .venv

# Ativar — macOS / Linux
source .venv/bin/activate

# Ativar — Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

As bibliotecas instaladas são:

| Pacote    | Finalidade                                      |
|-----------|-------------------------------------------------|
| `yfinance`| Download de cotações históricas (Yahoo Finance) |
| `sidrapy` | Coleta do IPCA via API SIDRA (IBGE)             |
| `pandas`  | Manipulação e tratamento de dados               |
| `plotly`  | Geração do gráfico interativo                   |

---

## Execução

### Script Python

Com o ambiente virtual ativado, execute:

```bash
python src/index_comparator.py
```

O script irá:
1. Baixar cotações históricas do Ibovespa, USD/BRL, BTC/USD e Ouro Futuro (via yfinance)
2. Buscar o IPCA mensal histórico via SIDRA/IBGE
3. Calcular o Ibovespa em cada perspectiva (nominal, real, dólar, ouro e bitcoin)
4. Abrir um gráfico interativo no seu navegador padrão.

### Notebook Jupyter

Abra o arquivo `10_Trading_com_Dados_IBOV_em_Dolar,_IPCA_e_BTC.ipynb` diretamente no VS Code ou no Jupyter Lab:

```bash
# Instale o Jupyter se necessário
pip install notebook

jupyter notebook
```

---

## Estrutura do Projeto

```
TradingWithData/
├── src/
│   └── index_comparator.py   # Script principal
├── 10_Trading_com_Dados_IBOV_em_Dolar,_IPCA_e_BTC.ipynb
├── requirements.txt          # Dependências Python
├── CHANGELOG.md              # Histórico de versões
└── README.md
```

---

## Resultado Esperado

Um gráfico interativo (abre no navegador) com cinco curvas normalizadas desde 2010:

- **Ibovespa Nominal (R$)**
- **Corrigido pelo IPCA**
- **Em Dólar (USD)**
- **Em Ouro**
- **Em Bitcoin**

O eixo Y usa escala logarítmica para facilitar a comparação entre ativos de magnitudes muito diferentes.
