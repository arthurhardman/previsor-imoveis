"""Ingestão do microdado real: GUIAS DE ITBI PAGAS da Prefeitura de São Paulo.

Fonte oficial e aberta: https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501
Cada linha é uma Declaração de Transação Imobiliária efetivamente paga —
preço REAL de venda, não anúncio.

As planilhas não têm cabeçalho; o layout de 28 colunas é o documentado
pela Fazenda-SP (aba LEGENDA/EXPLICAÇÕES dos próprios arquivos).

Uso: python ingest_itbi.py --entrada ../data/itbi --saida ../data/processed/transacoes.csv
"""

import argparse
import re
from pathlib import Path

import pandas as pd

COLUNAS = [
    "sql_cadastro", "logradouro", "numero", "complemento", "bairro", "referencia",
    "cep", "natureza", "valor_transacao", "data_transacao", "vvr_global",
    "proporcao_pct", "vvr_proporcional", "base_calculo", "tipo_financiamento",
    "valor_financiado", "cartorio", "matricula", "situacao_sql", "area_terreno_m2",
    "testada_m", "fracao_ideal", "area_construida_m2", "uso_cod", "uso_desc",
    "padrao_cod", "padrao_desc", "ano_construcao",
]

ABA_MES = re.compile(r"^[A-Z]{3}-\d{4}$")


def _classificar_tipo(uso_desc: str) -> str | None:
    uso = str(uso_desc).upper()
    if "APARTAMENTO" in uso:
        return "apartamento"
    if uso.startswith("RESIDÊNCIA") or uso.startswith("RESIDENCIA"):
        return "casa"
    return None  # comercial, terreno, garagem etc. ficam fora do modelo residencial


def ler_arquivo(caminho: Path) -> pd.DataFrame:
    abas = pd.read_excel(caminho, sheet_name=None, header=None, names=COLUNAS)
    mensais = [df for nome, df in abas.items() if ABA_MES.match(nome)]
    df = pd.concat(mensais, ignore_index=True)
    print(f"{caminho.name}: {len(df)} transações brutas em {len(mensais)} meses")
    return df


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    n0 = len(df)

    df = df[df["natureza"].astype(str).str.startswith("1.Compra e venda")]
    df = df[pd.to_numeric(df["proporcao_pct"], errors="coerce") == 100]

    df["tipo"] = df["uso_desc"].map(_classificar_tipo)
    df = df.dropna(subset=["tipo"])

    df["area_m2"] = pd.to_numeric(df["area_construida_m2"], errors="coerce")
    df["preco"] = pd.to_numeric(df["valor_transacao"], errors="coerce")
    df["data_transacao"] = pd.to_datetime(df["data_transacao"], errors="coerce")
    df["ano"] = df["data_transacao"].dt.year
    df["ano_construcao"] = pd.to_numeric(df["ano_construcao"], errors="coerce")
    df = df.dropna(subset=["area_m2", "preco", "ano", "ano_construcao"])

    df["idade_anos"] = (df["ano"] - df["ano_construcao"]).clip(lower=0)
    df["bairro"] = df["bairro"].astype(str).str.strip().str.upper()
    df = df[df["bairro"].ne("") & df["bairro"].ne("NAN")]

    df = df[df["area_m2"].between(15, 2000)]
    df = df[df["idade_anos"] <= 120]
    df = df[df["preco"] >= 30_000]  # valores simbólicos/erros de declaração

    # outliers de preço/m² (erros de digitação, permutas declaradas errado)
    preco_m2 = df["preco"] / df["area_m2"]
    p1, p99 = preco_m2.quantile([0.01, 0.99])
    df = df[preco_m2.between(p1, p99)]

    print(f"limpeza: {n0} -> {len(df)} transações residenciais válidas")
    return df[["bairro", "tipo", "area_m2", "idade_anos", "ano", "preco"]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default=str(Path(__file__).parent.parent / "data/itbi"))
    parser.add_argument("--saida", default=str(Path(__file__).parent.parent / "data/processed/transacoes.csv"))
    args = parser.parse_args()

    arquivos = sorted(Path(args.entrada).glob("*.xlsx"))
    assert arquivos, f"nenhum xlsx em {args.entrada}"

    df = limpar(pd.concat([ler_arquivo(a) for a in arquivos], ignore_index=True))

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(saida, index=False)
    print(f"{len(df)} transações salvas em {saida}")
