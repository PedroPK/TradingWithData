import argparse
import json
import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

try:
    from src.ibovespa_components import get_ibovespa_components
except ImportError:  # pragma: no cover - allows `python src/ibovespa_performance.py`
    from ibovespa_components import get_ibovespa_components


_DEFAULT_YEARS = 4
_DEFAULT_TIMEOUT = 30
_DEFAULT_PLOT_HTML = "ibovespa_performance_plot.html"
_DYNAMIC_HOVER_SORT_SCRIPT = """
const graph = document.getElementById("{plot_id}");

graph.on("plotly_beforehover", (event) => {
    const xaxis = graph._fullLayout.xaxis;
    const graphBounds = graph.getBoundingClientRect();
    const cursorX = event.clientX - graphBounds.left - xaxis._offset;

    if (!Number.isFinite(cursorX)) {
        return;
    }

    graph._fullData
        .map((trace, originalIndex) => {
            const closestPointIndex = trace.x.reduce(
                (closestIndex, value, index) => (
                    Math.abs(xaxis.d2p(value) - cursorX)
                    < Math.abs(xaxis.d2p(trace.x[closestIndex]) - cursorX)
                        ? index
                        : closestIndex
                ),
                0,
            );
            return {
                originalIndex,
                trace,
                value: Number.isFinite(Number(trace.y[closestPointIndex]))
                    ? Number(trace.y[closestPointIndex])
                    : -Infinity,
            };
        })
        .sort((left, right) => (
            (right.value - left.value) || (left.originalIndex - right.originalIndex)
        ))
        .forEach(({ trace }, rank) => {
            trace.index = rank;
        });
});
"""


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


def fetch_ibovespa_history(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.Series:
    """Fetch adjusted close history for the Ibovespa index."""
    raw_prices = yf.download(
        "^BVSP",
        start=start_date.strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    close_prices = extract_close_prices(raw_prices, ["^BVSP"])
    series = close_prices["^BVSP"].dropna()
    if series.empty:
        raise ValueError("O Yahoo Finance não retornou histórico do Ibovespa para o período informado.")
    return series


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


def select_plot_tickers(performance_df: pd.DataFrame, plot_count: int) -> list[str]:
    """Select top and bottom performers for plotting."""
    if plot_count <= 0:
        raise ValueError("A quantidade de ações para o gráfico deve ser maior que zero.")

    effective_count = min(plot_count, len(performance_df))
    top_count = (effective_count + 1) // 2
    bottom_count = effective_count // 2

    top_tickers = performance_df.head(top_count)["ticker"].tolist()
    bottom_tickers = performance_df.tail(bottom_count)["ticker"].tolist()
    return top_tickers + bottom_tickers


def _normalize_series(series: pd.Series) -> pd.Series:
    """Normalize a price series to base 100 using its first valid point."""
    valid_series = series.dropna()
    if valid_series.empty:
        raise ValueError("Série vazia não pode ser normalizada.")
    base_value = float(valid_series.iloc[0])
    return (series / base_value) * 100


def build_plot_dataframe(
    performance_df: pd.DataFrame,
    price_history: pd.DataFrame,
    ibovespa_history: pd.Series,
    plot_count: int,
) -> pd.DataFrame:
    """Build normalized time series for the selected performers plus Ibovespa."""
    selected_tickers = select_plot_tickers(performance_df, plot_count)
    selected_history = price_history[selected_tickers].copy()

    plot_df = pd.DataFrame(index=selected_history.index.union(ibovespa_history.index).sort_values())
    plot_df["Ibovespa"] = _normalize_series(ibovespa_history).reindex(plot_df.index)

    performance_lookup = performance_df.set_index("ticker")
    for ticker in selected_tickers:
        label = f"{ticker} - {performance_lookup.loc[ticker, 'company']}"
        plot_df[label] = _normalize_series(selected_history[ticker]).reindex(plot_df.index)

    return plot_df.ffill().dropna(how="all")


def build_performance_figure(
    plot_df: pd.DataFrame,
    requested_start_date: str,
    requested_end_date: str,
    plot_count: int,
) -> go.Figure:
    """Create the performance comparison figure."""
    fig = go.Figure()
    hover_templates: list[str] = []
    hover_texts = {"points": [], "percent": []}

    for column in plot_df.columns:
        trace_kwargs: dict[str, Any] = {}
        if column == "Ibovespa":
            trace_kwargs["line"] = dict(color="black", width=3)

        hover_templates.append(f"<b>{column}</b>: %{{text}}<extra></extra>")
        hover_texts["points"].append(plot_df[column].map(lambda value: f"{value:.2f} pontos").tolist())
        hover_texts["percent"].append(((plot_df[column] - 100).map(lambda value: f"{value:+.2f}%")).tolist())

        fig.add_trace(
            go.Scatter(
                x=plot_df.index,
                y=plot_df[column],
                mode="lines",
                name=column,
                text=hover_texts["percent"][-1],
                hovertemplate=hover_templates[-1],
                **trace_kwargs,
            )
        )

    fig.update_layout(
        title=dict(
            text=(
                "Evolução normalizada dos componentes selecionados do Ibovespa "
                f"({requested_start_date} a {requested_end_date}, base 100, {plot_count} ações)"
            ),
            x=0.5,
            xanchor="center",
            y=0.99,
            yanchor="top",
        ),
        xaxis_title="Data",
        yaxis=dict(title="Base 100", domain=[0, 0.86]),
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="top", y=0.91, xanchor="center", x=0.5),
        updatemenus=[
            dict(
                type="buttons",
                active=1,
                direction="right",
                x=0,
                xanchor="left",
                y=0.98,
                yanchor="top",
                buttons=[
                    dict(
                        label="Pontos (base 100)",
                        method="restyle",
                        args=[{"text": hover_texts["points"], "hovertemplate": hover_templates}],
                    ),
                    dict(
                        label="Variação (%)",
                        method="restyle",
                        args=[{"text": hover_texts["percent"], "hovertemplate": hover_templates}],
                    ),
                ],
            )
        ],
        margin=dict(t=5),
    )
    return fig


def export_performance_plot(fig: go.Figure, output_dir: str, show_browser: bool) -> str:
    """Export the selected performance chart to HTML."""
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, _DEFAULT_PLOT_HTML)
    fig.write_html(
        html_path,
        include_plotlyjs="cdn",
        post_script=_DYNAMIC_HOVER_SORT_SCRIPT,
    )
    if show_browser:
        fig.show()
    return html_path


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
        "price_history": price_history,
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
    parser.add_argument(
        "--plot-count",
        type=int,
        default=None,
        help="Quantidade de ações para o gráfico, dividida entre maiores altas e maiores quedas. O Ibovespa é sempre incluído.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Diretório de saída para o gráfico HTML quando --plot-count for informado.",
    )
    parser.add_argument("--no-show", action="store_true", help="Não abrir o gráfico no navegador.")
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
    ci_mode = bool(os.environ.get("CI"))
    show_browser = not args.no_show and not ci_mode
    output_messages: list[str] = []

    if args.csv:
        performance_df.to_csv(args.csv, index=False)
        output_messages.append(f"CSV salvo em: {args.csv}")

    plot_path = None
    if args.plot_count is not None:
        ibovespa_history = fetch_ibovespa_history(
            pd.Timestamp(result["requested_start_date"]),
            pd.Timestamp(result["requested_end_date"]),
        )
        plot_df = build_plot_dataframe(
            performance_df=performance_df,
            price_history=result["price_history"],
            ibovespa_history=ibovespa_history,
            plot_count=args.plot_count,
        )
        fig = build_performance_figure(
            plot_df=plot_df,
            requested_start_date=result["requested_start_date"],
            requested_end_date=result["requested_end_date"],
            plot_count=min(args.plot_count, len(performance_df)),
        )
        plot_path = export_performance_plot(fig, args.output_dir, show_browser)
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
