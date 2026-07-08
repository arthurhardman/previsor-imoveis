"""Índice de nível de preço por UF a partir do Banco Central (dados abertos).

Série: mediana do valor de avaliação de imóveis financiados por UF
(`imoveis_valor_avaliacao_<uf>`), API Olinda do BCB.

Gera models/uf_index.json com o multiplicador de cada UF em relação a SP —
usado pela API para escalar a previsão (treinada no microdado ITBI-SP)
para outros estados. Aproximação assumida e documentada: o perfil dos
imóveis financiados é comparável entre UFs.

Uso: python ingest_bcb.py
"""

import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

BASE = "https://olinda.bcb.gov.br/olinda/servico/MercadoImobiliario/versao/v1/odata/mercadoimobiliario"

UFS = [
    "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms", "mt",
    "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to",
]


def buscar_serie(sufixo: str) -> dict[str, float]:
    """Retorna {data: valor} da série imoveis_valor_avaliacao_<sufixo>."""
    filtro = quote(f"Info eq 'imoveis_valor_avaliacao_{sufixo}'")
    url = f"{BASE}?$filter={filtro}&$format=json&$orderby=Data"
    with urlopen(url, timeout=60) as resp:
        dados = json.load(resp)["value"]
    return {r["Data"]: float(r["Valor"]) for r in dados if r["Valor"]}


def montar_indice() -> dict:
    series = {uf: buscar_serie(uf) for uf in UFS}

    # última data presente em TODAS as UFs, para comparar o mesmo mês;
    # média dos últimos 3 meses disponíveis para suavizar
    def media_recente(s: dict[str, float]) -> float:
        ultimos = sorted(s)[-3:]
        return sum(s[d] for d in ultimos) / len(ultimos)

    medias = {uf: media_recente(s) for uf, s in series.items() if s}
    ref_sp = medias["sp"]
    return {
        "referencia": "imoveis_valor_avaliacao (BCB, média dos 3 meses mais recentes)",
        "data_referencia": max(sorted(series["sp"])),
        "multiplicadores": {uf.upper(): round(v / ref_sp, 4) for uf, v in sorted(medias.items())},
    }


if __name__ == "__main__":
    indice = montar_indice()
    saida = Path(__file__).parent.parent / "models" / "uf_index.json"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(json.dumps(indice, indent=2, ensure_ascii=False))
    print(f"Índice de {len(indice['multiplicadores'])} UFs salvo em {saida}")
    print(indice["multiplicadores"])
