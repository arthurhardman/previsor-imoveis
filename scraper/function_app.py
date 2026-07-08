"""Azure Function (timer mensal) que coleta as fontes REAIS para o Blob Storage.

Fontes oficiais e abertas:
- ITBI-SP: planilha do ano corrente (atualizada mensalmente pela Fazenda-SP)
  https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501
- BCB Mercado Imobiliário: séries imoveis_valor_avaliacao_<uf> (API Olinda)

O workflow de retreino (GitHub Actions) consome esses blobs.
"""

import datetime
import json
import logging
import os
import urllib.parse
import urllib.request

import azure.functions as func

app = func.FunctionApp()

ITBI_ANO_CORRENTE = "https://prefeitura.sp.gov.br/documents/d/fazenda/guias-de-itbi-pagas-4-xlsx"
BCB_BASE = (
    "https://olinda.bcb.gov.br/olinda/servico/MercadoImobiliario/versao/v1/"
    "odata/mercadoimobiliario"
)
UFS = [
    "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms", "mt",
    "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to",
]


def _baixar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def _gravar_blob(nome: str, dados: bytes) -> None:
    from azure.storage.blob import BlobServiceClient

    conn = os.environ["STORAGE_CONNECTION_STRING"]
    client = BlobServiceClient.from_connection_string(conn)
    client.get_blob_client("dados", nome).upload_blob(dados, overwrite=True)
    logging.info("gravado dados/%s (%d bytes)", nome, len(dados))


@app.timer_trigger(schedule="0 0 6 5 * *", arg_name="timer")  # dia 5 de cada mês, 06:00 UTC
def coletar_fontes(timer: func.TimerRequest) -> None:
    hoje = datetime.date.today()

    # 1. ITBI-SP: planilha do ano corrente (sobrescreve a versão anterior)
    itbi = _baixar(ITBI_ANO_CORRENTE)
    _gravar_blob(f"itbi/itbi_{hoje.year}.xlsx", itbi)

    # 2. BCB: histórico completo das séries de avaliação por UF
    series = {}
    for uf in UFS:
        filtro = urllib.parse.quote(f"Info eq 'imoveis_valor_avaliacao_{uf}'")
        url = f"{BCB_BASE}?$filter={filtro}&$format=json&$orderby=Data"
        series[uf] = json.loads(_baixar(url))["value"]
    _gravar_blob("bcb/valor_avaliacao_ufs.json", json.dumps(series).encode())

    logging.info("coleta mensal concluída (%s)", hoje.isoformat())
