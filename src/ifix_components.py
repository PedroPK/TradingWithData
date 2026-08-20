import argparse
import json

try:
    from src.ibovespa_components import _DEFAULT_TIMEOUT, get_ifix_components
except ImportError:  # pragma: no cover - allows `python src/ifix_components.py`
    from ibovespa_components import _DEFAULT_TIMEOUT, get_ifix_components


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Listar a composição atual do IFIX a partir da carteira teórica da B3.")
    parser.add_argument("--json", action="store_true", help="Exibe a saída em JSON.")
    parser.add_argument("--csv", default=None, help="Salva a composição em um arquivo CSV.")
    parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT, help="Timeout da requisição HTTP em segundos.")
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    reference_date, components = get_ifix_components(timeout=args.timeout)

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

    print(f"Composição atual do IFIX na B3 (data de referência: {reference_date})")
    print(f"Total de FIIs: {len(components)}")
    print(components.to_string(index=False))


if __name__ == "__main__":
    main()
