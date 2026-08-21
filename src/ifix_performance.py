import argparse
import asyncio
import json
import math
import os
from datetime import timezone
from typing import Any

import pandas as pd
from websockets.asyncio.client import connect

try:
    from src.ibovespa_components import _DEFAULT_TIMEOUT, get_ifix_components
    from src.ibovespa_performance import (
        _DEFAULT_YEARS,
        build_performance_dataframe,
        build_performance_figure,
        build_plot_dataframe,
        export_performance_plot,
        fetch_price_history,
        resolve_period,
    )
except ImportError:  # pragma: no cover - allows `python src/ifix_performance.py`
    from ibovespa_components import _DEFAULT_TIMEOUT, get_ifix_components
    from ibovespa_performance import (
        _DEFAULT_YEARS,
        build_performance_dataframe,
        build_performance_figure,
        build_plot_dataframe,
        export_performance_plot,
        fetch_price_history,
        resolve_period,
    )


_IFIX_SYMBOL = "BMFBOVESPA:IFIX"
_TRADINGVIEW_URL = "wss://data.tradingview.com/socket.io/websocket"
_DEFAULT_PLOT_HTML = "ifix_performance_plot.html"


def _tradingview_message(method: str, parameters: list[Any]) -> str:
    """Encode a TradingView WebSocket protocol message."""
    body = json.dumps({"m": method, "p": parameters}, separators=(",", ":"))
    return f"~m~{len(body)}~m~{body}"


def _decode_tradingview_messages(raw_message: str) -> list[dict[str, Any]]:
    """Decode JSON messages from a TradingView WebSocket frame."""
    messages: list[dict[str, Any]] = []
    position = 0
    while position < len(raw_message):
        if not raw_message.startswith("~m~", position):
            break
        length_start = position + 3
        length_end = raw_message.find("~m~", length_start)
        if length_end == -1:
            break
        body_start = length_end + 3
        body_end = body_start + int(raw_message[length_start:length_end])
        messages.append(json.loads(raw_message[body_start:body_end]))
        position = body_end
    return messages


async def _fetch_ifix_history(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.Series:
    session = "cs_ifix"
    bar_count = math.ceil((end_date - start_date).days * 5 / 7) + 10
    symbol = json.dumps(
        {"symbol": _IFIX_SYMBOL, "adjustment": "splits", "session": "regular"},
        separators=(",", ":"),
    )

    async with connect(_TRADINGVIEW_URL, origin="https://www.tradingview.com") as websocket:
        await websocket.send(_tradingview_message("chart_create_session", [session, ""]))
        await websocket.send(_tradingview_message("resolve_symbol", [session, "symbol_1", f"={symbol}"]))
        await websocket.send(
            _tradingview_message("create_series", [session, "s1", "s1", "symbol_1", "1D", bar_count])
        )

        while True:
            raw_message = await asyncio.wait_for(websocket.recv(), timeout=_DEFAULT_TIMEOUT)
            for message in _decode_tradingview_messages(raw_message):
                if message.get("m") == "critical_error":
                    raise ValueError(f"O TradingView não retornou histórico do IFIX: {message['p'][-1]}")
                if message.get("m") != "timescale_update":
                    continue

                series = message["p"][1].get("s1", {}).get("s", [])
                if not series:
                    raise ValueError("O TradingView não retornou histórico do IFIX para o período informado.")

                close_prices = {
                    pd.Timestamp(bar["v"][0], unit="s", tz=timezone.utc).tz_localize(None).normalize(): bar["v"][4]
                    for bar in series
                }
                history = pd.Series(close_prices, name="IFIX", dtype=float).sort_index()
                history = history.loc[start_date:end_date]
                if history.empty:
                    raise ValueError("O TradingView não retornou histórico do IFIX para o período informado.")
                return history


def fetch_ifix_history(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.Series:
    """Fetch daily IFIX closing prices from TradingView's B3 symbol."""
    return asyncio.run(_fetch_ifix_history(start_date, end_date))


def get_ifix_performance(
    start_date: str | None = None,
    end_date: str | None = None,
    years: int = _DEFAULT_YEARS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch current IFIX components and compute their performance ranking."""
    resolved_start, resolved_end = resolve_period(start_date=start_date, end_date=end_date, years=years)
    reference_date, components = get_ifix_components(timeout=timeout)
    price_history = fetch_price_history(
        components["ticker"],
        resolved_start,
        resolved_end,
        adjust_for_dividends=True,
    )
    performance_df, missing_tickers = build_performance_dataframe(components, price_history, index_name="IFIX")
    return {
        "reference_date": reference_date,
        "requested_start_date": resolved_start.strftime("%Y-%m-%d"),
        "requested_end_date": resolved_end.strftime("%Y-%m-%d"),
        "total_components": len(components),
        "available_components": len(performance_df),
        "missing_tickers": missing_tickers,
        "performance": performance_df,
        "price_history": price_history,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerar um ranking de valorização/desvalorização dos componentes atuais do IFIX."
    )
    parser.add_argument("--years", type=int, default=_DEFAULT_YEARS, help="Quantidade de anos antes da data final.")
    parser.add_argument("--start-date", default=None, help="Data inicial no formato YYYY-MM-DD.")
    parser.add_argument("--end-date", default=None, help="Data final no formato YYYY-MM-DD. Padrão: hoje.")
    parser.add_argument("--json", action="store_true", help="Exibe a saída em JSON.")
    parser.add_argument("--csv", default=None, help="Salva o ranking em um arquivo CSV.")
    parser.add_argument(
        "--plot-count",
        type=int,
        default=None,
        help="Quantidade de FIIs no gráfico, dividida entre maiores altas e maiores quedas. O IFIX é sempre incluído.",
    )
    parser.add_argument("--output-dir", default="output", help="Diretório de saída para o gráfico HTML.")
    parser.add_argument("--no-show", action="store_true", help="Não abrir o gráfico no navegador.")
    parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT, help="Timeout da consulta à B3 em segundos.")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    result = get_ifix_performance(
        start_date=args.start_date,
        end_date=args.end_date,
        years=args.years,
        timeout=args.timeout,
    )
    performance_df = result["performance"]
    output_messages: list[str] = []

    if args.csv:
        performance_df.to_csv(args.csv, index=False)
        output_messages.append(f"CSV salvo em: {args.csv}")

    plot_path = None
    if args.plot_count is not None:
        ifix_history = fetch_ifix_history(
            pd.Timestamp(result["requested_start_date"]),
            pd.Timestamp(result["requested_end_date"]),
        )
        plot_df = build_plot_dataframe(
            performance_df=performance_df,
            price_history=result["price_history"],
            ibovespa_history=ifix_history,
            plot_count=args.plot_count,
            index_name="IFIX",
        )
        value_df = build_plot_dataframe(
            performance_df=performance_df,
            price_history=result["price_history"],
            ibovespa_history=ifix_history,
            plot_count=args.plot_count,
            index_name="IFIX",
            normalize=False,
        )
        figure = build_performance_figure(
            plot_df=plot_df,
            requested_start_date=result["requested_start_date"],
            requested_end_date=result["requested_end_date"],
            plot_count=min(args.plot_count, len(performance_df)),
            index_name="IFIX",
            value_df=value_df,
            values_button_label="Valores com rendimentos (R$ / pontos)",
        )
        plot_path = export_performance_plot(
            figure,
            args.output_dir,
            show_browser=not args.no_show and not bool(os.environ.get("CI")),
            filename=_DEFAULT_PLOT_HTML,
        )
        output_messages.append(f"Gráfico HTML salvo em: {plot_path}")

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
                    "plot_html_path": plot_path,
                    "performance": performance_df.to_dict(orient="records"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    for message in output_messages:
        print(message)

    print(f"Ranking de valorização/desvalorização do IFIX (carteira B3: {result['reference_date']})")
    print(f"Período solicitado: {result['requested_start_date']} até {result['requested_end_date']}")
    print(f"FIIs com histórico disponível: {result['available_components']} de {result['total_components']}")
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
