import argparse
import base64
import json
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

_B3_INDEX_URL = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/{payload}"
_DEFAULT_INDEX = "IBOV"
_DEFAULT_PAGE_SIZE = 200
_DEFAULT_LANGUAGE = "pt-br"
_DEFAULT_TIMEOUT = 30
_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


def _build_b3_url(index: str, page_number: int = 1, page_size: int = _DEFAULT_PAGE_SIZE, language: str = _DEFAULT_LANGUAGE) -> str:
    """Build the B3 portfolio URL for a given index."""
    payload = {
        "pageNumber": page_number,
        "pageSize": page_size,
        "index": index.upper(),
        "segment": "1",
        "language": language,
    }
    encoded_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return _B3_INDEX_URL.format(payload=encoded_payload)


def fetch_index_portfolio(index: str = _DEFAULT_INDEX, timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch the current theoretical portfolio payload for a B3 index."""
    request = Request(_build_b3_url(index=index), headers=_REQUEST_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _parse_b3_decimal(value: str | None) -> float | None:
    """Convert B3 locale-formatted decimals to float."""
    if value in (None, ""):
        return None
    return float(value.replace(".", "").replace(",", "."))


def portfolio_to_dataframe(payload: dict[str, Any]) -> pd.DataFrame:
    """Normalize the B3 portfolio payload into a dataframe."""
    results = payload.get("results", [])
    if not results:
        raise ValueError("A B3 não retornou componentes para o índice informado.")

    df = pd.DataFrame(results).rename(
        columns={
            "cod": "ticker",
            "asset": "company",
            "type": "share_type",
            "part": "weight_percent",
            "theoricalQty": "theoretical_quantity",
        }
    )
    df = df[["ticker", "company", "share_type", "weight_percent", "theoretical_quantity"]].copy()
    df["weight_percent"] = df["weight_percent"].map(_parse_b3_decimal)
    df["theoretical_quantity"] = df["theoretical_quantity"].map(_parse_b3_decimal)
    df["share_type"] = df["share_type"].str.strip()
    return df


def get_ibovespa_components(timeout: int = _DEFAULT_TIMEOUT) -> tuple[str, pd.DataFrame]:
    """Return the B3 reference date and current Ibovespa components."""
    payload = fetch_index_portfolio(index=_DEFAULT_INDEX, timeout=timeout)
    reference_date = payload["header"]["date"]
    return reference_date, portfolio_to_dataframe(payload)


def get_ifix_components(timeout: int = _DEFAULT_TIMEOUT) -> tuple[str, pd.DataFrame]:
    """Return the B3 reference date and current IFIX components."""
    payload = fetch_index_portfolio(index="IFIX", timeout=timeout)
    reference_date = payload["header"]["date"]
    return reference_date, portfolio_to_dataframe(payload)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Listar a composição atual do Ibovespa a partir da carteira teórica da B3.")
    parser.add_argument("--json", action="store_true", help="Exibe a saída em JSON.")
    parser.add_argument("--csv", default=None, help="Salva a composição em um arquivo CSV.")
    parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT, help="Timeout da requisição HTTP em segundos.")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    reference_date, components = get_ibovespa_components(timeout=args.timeout)

    if args.csv:
        components.to_csv(args.csv, index=False)
        print(f"CSV salvo em: {args.csv}")

    if args.json:
        print(
            json.dumps(
                {
                    "reference_date": reference_date,
                    "total_components": len(components),
                    "components": components.to_dict(orient="records"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"Composição atual do Ibovespa na B3 (data de referência: {reference_date})")
    print(f"Total de ativos: {len(components)}")
    print(components.to_string(index=False))


if __name__ == "__main__":
    main()
