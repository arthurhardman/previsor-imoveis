"""Treina o modelo de previsão de preço de imóveis com dados reais (ITBI-SP).

- Lê data/processed/transacoes.csv (gerado por ingest_itbi.py)
- Bairros raros são agrupados em OUTRO (a lista de bairros conhecidos
  acompanha o artefato para a API aplicar o mesmo mapeamento)
- Alvo em escala log (preços têm cauda longa)
- Loga métricas e artefatos no MLflow; salva models/model.joblib

Uso: python train.py [--data ../data/processed/transacoes.csv]
"""

import argparse
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

CATEGORICAS = ["bairro", "tipo"]
NUMERICAS = ["area_m2", "idade_anos", "ano"]
TARGET = "preco"
MIN_TRANSACOES_BAIRRO = 50


def build_model() -> TransformedTargetRegressor:
    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS)],
        remainder="passthrough",
    )
    xgb = XGBRegressor(
        n_estimators=800,
        learning_rate=0.05,
        max_depth=8,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        n_jobs=-1,
    )
    return TransformedTargetRegressor(
        regressor=Pipeline([("pre", pre), ("model", xgb)]),
        func=np.log1p,
        inverse_func=np.expm1,
    )


def main(data_path: str) -> None:
    df = pd.read_csv(data_path)

    contagem = df["bairro"].value_counts()
    bairros_conhecidos = sorted(contagem[contagem >= MIN_TRANSACOES_BAIRRO].index)
    df["bairro"] = df["bairro"].where(df["bairro"].isin(bairros_conhecidos), "OUTRO")

    X, y = df[CATEGORICAS + NUMERICAS], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    mlflow.set_experiment("previsor-imoveis")
    with mlflow.start_run():
        model = build_model()
        model.fit(X_train, y_train)

        pred = model.predict(X_test)
        metrics = {
            "mae": mean_absolute_error(y_test, pred),
            "mape": mean_absolute_percentage_error(y_test, pred),
            "r2": r2_score(y_test, pred),
            "mediana_erro_pct": float(np.median(np.abs(pred - y_test) / y_test)),
        }
        mlflow.log_params(
            {
                "n_rows": len(df),
                "n_bairros": len(bairros_conhecidos),
                "model": "xgboost-log-target",
                "fonte": "ITBI-SP 2024-2026",
            }
        )
        mlflow.log_metrics(metrics)
        print({k: round(v, 4) for k, v in metrics.items()})

        # estatísticas por bairro: a API usa para avisar quando a consulta
        # está fora do suporte dos dados (extrapolação)
        stats = (
            df.groupby("bairro")
            .agg(
                n=("preco", "size"),
                area_p5=("area_m2", lambda s: s.quantile(0.05)),
                area_p95=("area_m2", lambda s: s.quantile(0.95)),
                idade_p5=("idade_anos", lambda s: s.quantile(0.05)),
                idade_p95=("idade_anos", lambda s: s.quantile(0.95)),
            )
            .round(0)
            .astype(int)
            .to_dict("index")
        )

        out = Path(__file__).parent.parent / "models" / "model.joblib"
        out.parent.mkdir(exist_ok=True)
        joblib.dump(
            {"pipeline": model, "bairros": bairros_conhecidos, "bairro_stats": stats}, out
        )
        mlflow.log_artifact(str(out))
        print(f"Modelo + {len(bairros_conhecidos)} bairros salvos em {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", default=str(Path(__file__).parent.parent / "data/processed/transacoes.csv")
    )
    args = parser.parse_args()
    main(args.data)
