import base64
import json

import pytest

from src import ibovespa_components


def _sample_payload():
    return {
        "header": {"date": "18/08/26"},
        "results": [
            {
                "cod": "ABEV3",
                "asset": "AMBEV S/A",
                "type": "ON      ",
                "part": "2,710",
                "theoricalQty": "4.273.841.357",
            },
            {
                "cod": "B3SA3",
                "asset": "B3",
                "type": "ON      NM",
                "part": "3,112",
                "theoricalQty": "4.997.059.816",
            },
        ],
    }


def test_build_b3_url_encodes_ibov_payload():
    url = ibovespa_components._build_b3_url("IBOV")
    encoded_payload = url.rsplit("/", 1)[-1]
    payload = json.loads(base64.b64decode(encoded_payload).decode("utf-8"))

    assert payload == {
        "pageNumber": 1,
        "pageSize": 200,
        "index": "IBOV",
        "segment": "1",
        "language": "pt-br",
    }


def test_portfolio_to_dataframe_normalizes_b3_payload():
    df = ibovespa_components.portfolio_to_dataframe(_sample_payload())

    assert list(df.columns) == [
        "ticker",
        "company",
        "share_type",
        "weight_percent",
        "theoretical_quantity",
    ]
    assert df.to_dict(orient="records") == [
        {
            "ticker": "ABEV3",
            "company": "AMBEV S/A",
            "share_type": "ON",
            "weight_percent": pytest.approx(2.710),
            "theoretical_quantity": pytest.approx(4273841357.0),
        },
        {
            "ticker": "B3SA3",
            "company": "B3",
            "share_type": "ON      NM".strip(),
            "weight_percent": pytest.approx(3.112),
            "theoretical_quantity": pytest.approx(4997059816.0),
        },
    ]


def test_portfolio_to_dataframe_rejects_empty_results():
    with pytest.raises(ValueError, match="não retornou componentes"):
        ibovespa_components.portfolio_to_dataframe({"results": []})
