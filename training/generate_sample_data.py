"""Gera dados sintéticos de anúncios de imóveis para desenvolver o pipeline
antes de ter dados reais do scraper.

Uso: python generate_sample_data.py --n 5000 --out ../data/raw/anuncios.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BAIRROS = {
    # bairro: (preço base por m², desvio)
    "Centro": (6500, 900),
    "Jardins": (9500, 1400),
    "Vila Nova": (5200, 700),
    "Boa Vista": (4300, 600),
    "Industrial": (3200, 500),
    "Beira Rio": (7800, 1100),
}

TIPOS = ["apartamento", "casa", "kitnet", "cobertura"]


def gerar(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    bairros = rng.choice(list(BAIRROS), size=n)
    tipos = rng.choice(TIPOS, size=n, p=[0.55, 0.3, 0.1, 0.05])

    area = np.clip(rng.lognormal(4.2, 0.45, n), 18, 600).round(0)
    quartos = np.clip((area / 35).round() + rng.integers(-1, 2, n), 1, 6)
    banheiros = np.clip(quartos - rng.integers(0, 2, n), 1, 5)
    vagas = np.clip(rng.integers(0, 4, n), 0, 3)
    idade = rng.integers(0, 40, n)

    preco_m2 = np.array([rng.normal(*BAIRROS[b]) for b in bairros])
    mult_tipo = pd.Series(tipos).map(
        {"apartamento": 1.0, "casa": 0.92, "kitnet": 0.85, "cobertura": 1.35}
    ).to_numpy()
    preco = (
        preco_m2 * area * mult_tipo
        * (1 - idade * 0.006)
        * (1 + vagas * 0.04)
        * rng.normal(1, 0.08, n)  # ruído de mercado
    )

    return pd.DataFrame(
        {
            "bairro": bairros,
            "tipo": tipos,
            "area_m2": area,
            "quartos": quartos.astype(int),
            "banheiros": banheiros.astype(int),
            "vagas": vagas.astype(int),
            "idade_anos": idade,
            "preco": preco.round(-3),
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--out", default="../data/raw/anuncios.csv")
    args = parser.parse_args()

    df = gerar(args.n)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df)} anúncios gerados em {out}")
