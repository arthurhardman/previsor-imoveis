"""API de previsão de preço de imóveis — modelo treinado em transações reais
(ITBI-SP) e escalado para outras UFs pelo índice do Banco Central.

- GET  /health   — probe do Container Apps
- GET  /bairros  — bairros conhecidos pelo modelo (para autocomplete)
- GET  /ufs      — multiplicadores por UF (índice BCB)
- POST /predict  — previsão + fatores (efeito % de cada feature via SHAP)
"""

import datetime
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

MODELS_DIR = Path(__file__).parent.parent / "models"

app = FastAPI(title="Previsor de Imóveis", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir ao domínio do Static Web App em produção
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = None
_bairros: list[str] = []
_uf_index: dict[str, float] = {}


class Imovel(BaseModel):
    uf: str = Field(examples=["SP"], min_length=2, max_length=2)
    bairro: str = Field(examples=["CENTRO"], description="Bairro (base de referência: São Paulo capital)")
    tipo: str = Field(examples=["apartamento"], pattern="^(apartamento|casa)$")
    area_m2: float = Field(gt=10, lt=2000)
    idade_anos: int = Field(ge=0, le=120)


class Previsao(BaseModel):
    preco_estimado: float
    preco_m2: float
    fatores_pct: dict[str, float]
    ajuste_uf: float
    metodologia: str


@app.on_event("startup")
def load_artifacts() -> None:
    global _pipeline, _bairros, _uf_index
    model_path = MODELS_DIR / "model.joblib"
    if model_path.exists():
        artefato = joblib.load(model_path)
        _pipeline, _bairros = artefato["pipeline"], artefato["bairros"]
    index_path = MODELS_DIR / "uf_index.json"
    if index_path.exists():
        _uf_index = json.loads(index_path.read_text())["multiplicadores"]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _pipeline is not None, "ufs": len(_uf_index)}


@app.get("/bairros")
def bairros() -> list[str]:
    return _bairros


@app.get("/ufs")
def ufs() -> dict[str, float]:
    return _uf_index


@app.post("/predict", response_model=Previsao)
def predict(imovel: Imovel) -> Previsao:
    if _pipeline is None:
        raise HTTPException(503, "Modelo não carregado.")

    uf = imovel.uf.upper()
    if uf not in _uf_index:
        raise HTTPException(422, f"UF desconhecida: {uf}")

    bairro = imovel.bairro.strip().upper()
    X = pd.DataFrame(
        [{
            "bairro": bairro if bairro in _bairros else "OUTRO",
            "tipo": imovel.tipo,
            "area_m2": imovel.area_m2,
            "idade_anos": imovel.idade_anos,
            "ano": datetime.date.today().year,
        }]
    )

    preco_sp = float(_pipeline.predict(X)[0])
    ajuste = _uf_index[uf]
    preco = preco_sp * ajuste

    return Previsao(
        preco_estimado=round(preco, -3),
        preco_m2=round(preco / imovel.area_m2, 2),
        fatores_pct=_explicar(X),
        ajuste_uf=ajuste,
        metodologia=(
            "Modelo XGBoost treinado em ~100 mil transações reais (ITBI São Paulo 2024-2026), "
            "escalado por UF pela mediana de avaliação de imóveis financiados (Banco Central)."
        ),
    )


def _explicar(X: pd.DataFrame) -> dict[str, float]:
    """Efeito de cada feature no preço, em % (SHAP no espaço log -> multiplicativo)."""
    import shap

    interno = _pipeline.regressor_
    pre, model = interno.named_steps["pre"], interno.named_steps["model"]
    Xt = pre.transform(X)
    valores = shap.TreeExplainer(model).shap_values(Xt)[0]

    log_contrib: dict[str, float] = {}
    for nome, valor in zip(pre.get_feature_names_out(), valores):
        original = nome.split("__", 1)[1].rsplit("_", 1)[0] if nome.startswith("cat__") else nome.split("__", 1)[1]
        log_contrib[original] = log_contrib.get(original, 0.0) + float(valor)

    pct = {k: round((np.expm1(v)) * 100, 1) for k, v in log_contrib.items()}
    return dict(sorted(pct.items(), key=lambda i: -abs(i[1])))
