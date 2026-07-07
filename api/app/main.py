"""API de previsão de preço de imóveis (FastAPI + modelo XGBoost).

Carrega models/model.joblib no startup e expõe:
- GET  /health   — usado pelo probe do Container Apps
- POST /predict  — previsão + top fatores (importância local via SHAP)
"""

from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

MODEL_PATH = Path(__file__).parent.parent / "models" / "model.joblib"

app = FastAPI(title="Previsor de Imóveis", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir ao domínio do Static Web App em produção
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = None


class Imovel(BaseModel):
    bairro: str = Field(examples=["Centro"])
    tipo: str = Field(examples=["apartamento"])
    area_m2: float = Field(gt=10, lt=2000)
    quartos: int = Field(ge=1, le=10)
    banheiros: int = Field(ge=1, le=10)
    vagas: int = Field(ge=0, le=10)
    idade_anos: int = Field(ge=0, le=100)


class Previsao(BaseModel):
    preco_estimado: float
    preco_m2: float
    fatores: dict[str, float]


@app.on_event("startup")
def load_model() -> None:
    global _pipeline
    if MODEL_PATH.exists():
        _pipeline = joblib.load(MODEL_PATH)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _pipeline is not None}


@app.post("/predict", response_model=Previsao)
def predict(imovel: Imovel) -> Previsao:
    if _pipeline is None:
        raise HTTPException(503, "Modelo não carregado. Rode o treino e reconstrua a imagem.")

    X = pd.DataFrame([imovel.model_dump()])
    preco = float(_pipeline.predict(X)[0])

    fatores = _explicar(X)
    return Previsao(
        preco_estimado=round(preco, -3),
        preco_m2=round(preco / imovel.area_m2, 2),
        fatores=fatores,
    )


def _explicar(X: pd.DataFrame) -> dict[str, float]:
    """Contribuição de cada feature no preço (R$) via SHAP, agregada por coluna original."""
    import shap

    pre, model = _pipeline.named_steps["pre"], _pipeline.named_steps["model"]
    Xt = pre.transform(X)
    valores = shap.TreeExplainer(model).shap_values(Xt)[0]

    contribuicoes: dict[str, float] = {}
    for nome, valor in zip(pre.get_feature_names_out(), valores):
        # "cat__bairro_Centro" -> "bairro"; "remainder__area_m2" -> "area_m2"
        original = nome.split("__", 1)[1].rsplit("_", 1)[0] if nome.startswith("cat__") else nome.split("__", 1)[1]
        contribuicoes[original] = contribuicoes.get(original, 0.0) + float(valor)

    return {k: round(v, 2) for k, v in sorted(contribuicoes.items(), key=lambda i: -abs(i[1]))}
