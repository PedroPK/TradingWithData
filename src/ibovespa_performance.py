import argparse
import json
from typing import Any

import pandas as pd
import yfinance as yf

try:
    from src.ibovespa_components import get_ibovespa_components
except ImportError:  # pragma: no cover - allows `python src/ibovespa_performance.py`
    from ibovespa_components import get_ibovespa_components


_DEFAULT_YEARS = 4
_DEFAULT_TIMEOUT = 30


def resolve_period(
    start_date: str | None = None,
    end_date: str | None = None,
    years: int = _DEFAULT_YEARS,
    today: str | pd.Timestamp | None = None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Resolve the analysis window, defaulting to the last four years."""
    resolved_today = pd.Timestamp(today).normalize() if today is not None else pd.Timestamp.today().normalize()
    resolved_end = pd.Timestamp(end_date).normalize() if end_date else resolved_today
    if start_date:
        resolved_start = pd.Timestamp(start_date).normalize()
    else:
        if years <= 0:
            raise ValueError("O número de anos deve ser maior que zero.")
        resolved_start = resolved_end - pd.DateOffset(years=years)

    if resolved_start >= resolved_end:
        raise ValueError("A data inicial deve ser anterior à data final.")
    return resolved_start, resolved_end


def _to_yfinance_tickers(tickers: pd.Series) -> list[str]:
    """Convert B3 tickers to Yahoo Finance tickers."""
    return [f"{ticker}.SA" for ticker in tickers.tolist()]


def extract_close_prices(price_data: pd.DataFrame, requested_tickers: list[str]) -> pd.DataFrame:
    """Extract close prices from a yfinance download result."""
    if price_data.empty:
        raise ValueError("O Yahoo Finance não retornou histórico para o período informado.")

    if isinstance(price_data.columns, pd.MultiIndex):
        close_prices = price_data["Close"].copy()
    elif "Close" in price_data.columns:
        if len(requested_tickers) != 1:
            raise ValueError("Formato inesperado do retorno do Yahoo Finance para múltiplos ativos.")
        close_prices = price_data[["Close"]].copy()
        close_prices.columns = requested_tickers
    else:
        close_prices = price_data.copy()

    close_prices.columns = [ticker.removesuffix(".SA") for ticker in close_prices.columns]
    return close_prices


def fetch_price_history(
    tickers: pd.Series,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Fetch adjusted close prices for the requested analysis period."""
    yahoo_tickers = _to_yfinance_tickers(tickers)
    raw_prices = yf.download(
        yahoo_tickers,
        start=start_date.strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    return extract_close_prices(raw_prices, yahoo_tickers)


def build_performance_dataframe(components: pd.DataFrame, price_history: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Build a sorted valuation/devaluation table for Ibovespa components."""
    component_lookup = components.set_index("ticker")
    rows: list[dict[str, Any]] = []
    missing_tickers: list[str] = []

    for ticker in components["ticker"]:
        if ticker not in price_history.columns:
            missing_tickers.append(ticker)
            continue

        series = price_history[ticker].dropna()
        if series.empty:
            missing_tickers.append(ticker)
            continue

        start_price = float(series.iloc[0])
        end_price = float(series.iloc[-1])
        absolute_change = end_price - start_price
        return_percent = ((end_price / start_price) - 1) * 100
        component = component_lookup.loc[ticker]
        rows.append(
            {
                "ticker": ticker,
                "company": component["company"],
                "share_type": component["share_type"],
                "weight_percent": float(component["weight_percent"]),
                "start_date": series.index[0].strftime("%Y-%m-%d"),
                "end_date": series.index[-1].strftime("%Y-%m-%d"),
                "start_price": start_price,
                "end_price": end_price,
                "absolute_change": absolute_change,
                "return_percent": return_percent,
            }
        )

    if not rows:
        raise ValueError("Nenhum componente do Ibovespa teve histórico disponível no período informado.")

    performance_df = pd.DataFrame(rows).sort_values("return_percent", ascending=False, kind="stable").reset_index(drop=True)
    return performance_df, missing_tickers


def get_ibovespa_performance(
    start_date: str | None = None,
    end_date: str | None = None,
    years: int = _DEFAULT_YEARS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch current IBOV components and compute their performance ranking."""
    resolved_start, resolved_end = resolve_period(start_date=start_date, end_date=end_date, years=years)
    reference_date, components = get_ibovespa_components(timeout=timeout)
    price_history = fetch_price_history(components["ticker"], resolved_start, resolved_end)
    performance_df, missing_tickers = build_performance_dataframe(components, price_history)
    return {
        "reference_date": reference_date,
        "requested_start_date": resolved_start.strftime("%Y-%m-%d"),
        "requested_end_date": resolved_end.strftime("%Y-%m-%d"),
        "total_components": len(components),
        "available_components": len(performance_df),
        "missing_tickers": missing_tickers,
        "performance": performance_df,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerar um ranking de valorização/desvalorização dos componentes atuais do Ibovespa."
    )
    parser.add_argument(
        "--years",
        type=int,
        default=_DEFAULT_YEARS,
        help="Quantidade de anos para voltar a partir da data final. Ignorado se --start-date for informado.",
    )
    parser.add_argument("--start-date", default=None, help="Data inicial no formato YYYY-MM-DD.")
    parser.add_argument("--end-date", default=None, help="Data final no formato YYYY-MM-DD. Padrão: hoje.")
    parser.add_argument("--json", action="store_true", help="Exibe a saída em JSON.")
    parser.add_argument("--csv", default=None, help="Salva o ranking em um arquivo CSV.")
    parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT, help="Timeout da consulta à B3 em segundos.")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    result = get_ibovespa_performance(
        start_date=args.start_date,
        end_date=args.end_date,
        years=args.years,
        timeout=args.timeout,
    )
    performance_df = result["performance"]

    if args.csv:
        performance_df.to_csv(args.csv, index=False)
        print(f"CSV salvo em: {args.csv}")

    if args.json:
        print(
            json.dumps(
                {
                    "reference_date": result["reference_date"],
                    "requested_start_date": result["requested_start_date"],
                    "requested_end_date": result["requested_end_date"],
                    "total_components": result["total_components"],
                    "available_components": result["available_components"],
                    "missing_tickers": result["missing_tickers"],
                    "performance": performance_df.to_dict(orient="records"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"Ranking de valorização/desvalorização do Ibovespa (carteira B3: {result['reference_date']})")
    print(f"Período solicitado: {result['requested_start_date']} até {result['requested_end_date']}")
    print(f"Ativos com histórico disponível: {result['available_components']} de {result['total_components']}")
    if result["missing_tickers"]:
        print(f"Sem histórico no período: {', '.join(result['missing_tickers'])}")

    print(
        performance_df.to_string(
            index=False,
            formatters={
                "weight_percent": lambda value: f"{value:.3f}%",
                "start_price": lambda value: f"{value:.2f}",
                "end_price": lambda value: f"{value:.2f}",
                "absolute_change": lambda value: f"{value:.2f}",
                "return_percent": lambda value: f"{value:.2f}%",
            },
        )
    )


if __name__ == "__main__":
    main()
