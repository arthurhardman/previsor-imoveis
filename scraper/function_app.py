"""Azure Function (timer semanal) que coleta anúncios e grava CSV no Blob Storage.

IMPORTANTE: a coleta em portais (OLX/Zap) precisa respeitar robots.txt e os termos
de uso do site — verifique antes de ativar. O stub abaixo mantém o pipeline
funcionando com dados sintéticos até você plugar uma fonte real (ideal: uma API
pública ou dados abertos de transações imobiliárias da sua prefeitura).
"""

import datetime
import io
import logging
import os

import azure.functions as func

app = func.FunctionApp()


@app.timer_trigger(schedule="0 0 6 * * 1", arg_name="timer")  # segundas 06:00 UTC
def coletar_anuncios(timer: func.TimerRequest) -> None:
    logging.info("Iniciando coleta de anúncios")

    csv_bytes = _coletar()

    from azure.storage.blob import BlobServiceClient

    conn = os.environ["STORAGE_CONNECTION_STRING"]
    nome = f"raw/anuncios_{datetime.date.today().isoformat()}.csv"
    client = BlobServiceClient.from_connection_string(conn)
    client.get_blob_client("dados", nome).upload_blob(io.BytesIO(csv_bytes), overwrite=True)
    logging.info("Coleta gravada em dados/%s", nome)


def _coletar() -> bytes:
    """TODO: substituir por coleta real (respeitando robots.txt / ToS da fonte)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from sample_source import gerar_lote

    return gerar_lote()
