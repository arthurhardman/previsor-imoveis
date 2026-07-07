"""Treina o modelo de previsão de preço de imóveis.

- Lê data/raw/anuncios.csv
- Pipeline sklearn (one-hot p/ categóricas) + XGBoost
- Loga métricas e artefatos no MLflow (local, pasta mlruns/)
- Salva o pipeline final em models/model.joblib (consumido pela API)

Uso: python train.py [--data ../data/raw/anuncios.csv]
"""

import argparse
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

CATEGORICAS = ["bairro", "tipo"]
NUMERICAS = ["area_m2", "quartos", "banheiros", "vagas", "idade_anos"]
TARGET = "preco"


def build_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS)],
        remainder="passthrough",
    )
    model = XGBRegressor(
        n_estimators=600,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
    )
    return Pipeline([("pre", pre), ("model", model)])


def main(data_path: str) -> None:
    df = pd.read_csv(data_path)
    X, y = df[CATEGORICAS + NUMERICAS], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    mlflow.set_experiment("previsor-imoveis")
    with mlflow.start_run():
        pipe = build_pipeline()
        pipe.fit(X_train, y_train)

        pred = pipe.predict(X_test)
        metrics = {
            "mae": mean_absolute_error(y_test, pred),
            "mape": mean_absolute_percentage_error(y_test, pred),
            "r2": r2_score(y_test, pred),
        }
        mlflow.log_params({"n_rows": len(df), "model": "xgboost"})
        mlflow.log_metrics(metrics)
        print({k: round(v, 4) for k, v in metrics.items()})

        out = Path(__file__).parent.parent / "models" / "model.joblib"
        out.parent.mkdir(exist_ok=True)
        joblib.dump(pipe, out)
        mlflow.log_artifact(str(out))
        print(f"Modelo salvo em {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(Path(__file__).parent.parent / "data/raw/anuncios.csv"))
    args = parser.parse_args()
    main(args.data)
