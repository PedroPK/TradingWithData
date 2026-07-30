import os
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "10_Trading_com_Dados_IBOV_em_Dolar,_IPCA_e_BTC.ipynb"


@pytest.mark.notebook
def test_notebook_executes_end_to_end():
    if os.environ.get("RUN_NOTEBOOK_TESTS") != "1":
        pytest.skip("Set RUN_NOTEBOOK_TESTS=1 to execute the full notebook in automated runs.")

    with NOTEBOOK_PATH.open("r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    client = NotebookClient(
        nb,
        timeout=900,
        kernel_name="python3",
        allow_errors=False,
        resources={"metadata": {"path": str(NOTEBOOK_PATH.parent)}},
    )
    client.execute()
