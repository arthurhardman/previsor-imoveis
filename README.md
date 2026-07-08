# Previsor de Imóveis 🏠

Projeto de portfólio de Machine Learning **de ponta a ponta**: coleta de dados → treino → deploy na nuvem → API com explicabilidade → front interativo → retreino automático.

**Demo:** https://polite-field-004e2630f.7.azurestaticapps.net
**API:** https://previmoveis-api.ambitiouspond-daff3a18.brazilsouth.azurecontainerapps.io/docs

> A primeira requisição pode levar alguns segundos: a API roda com scale-to-zero e "acorda" sob demanda — decisão deliberada para custo zero.

## Arquitetura

```
Azure Functions (timer semanal)     GitHub Actions (retrain, semanal)
  coleta anúncios                     baixa dados do Blob → treina XGBoost
        │                             → commita models/model.joblib
        ▼                                     │ (dispara deploy)
  Blob Storage (dados brutos)                 ▼
                                    GitHub Actions (deploy-api)
                                      build Docker → ghcr.io → Container App
                                              │
   React (Static Web Apps)  ─────►  FastAPI (Container Apps, scale-to-zero)
                                      /predict com SHAP (fatores do preço)
                                              │
                                    Application Insights (telemetria)
```

## Decisões de custo (conta pessoal, alvo ~R$ 0/mês)

| Decisão | Por quê |
|---|---|
| Container Apps com `minReplicas: 0` | Não paga nada sem tráfego; cold start de segundos é aceitável em demo |
| Imagem no ghcr.io (pública) | Azure Container Registry Basic custa ~US$ 5/mês; ghcr é grátis |
| Treino no GitHub Actions, não no Azure ML | Endpoints gerenciados do Azure ML ficam ligados 24/7 e custam caro |
| Functions no plano Consumption | 1M execuções grátis/mês; o scraper usa ~4 |
| Log Analytics com retenção 30 dias | Primeiros 5 GB/mês grátis |
| **Budget alert de R$ 20** (passo 5 abaixo) | Rede de segurança contra qualquer descuido |

## Rodando localmente

```bash
# 1. Dados de exemplo + treino
cd training
pip install -r requirements.txt
python generate_sample_data.py
python train.py                      # salva models/model.joblib e loga no MLflow (mlruns/)

# 2. API
cd ../api
pip install -r requirements.txt
cp -r ../models .                    # a API lê api/models/model.joblib
uvicorn app.main:app --reload        # http://localhost:8000/docs

# 3. Front
cd ../web
npm install
npm run dev                          # http://localhost:5173 (proxy /api -> :8000)
```

## Deploy na Azure (conta pessoal)

> Pré-requisitos: `az` CLI logado na **assinatura pessoal** (`az account show` para conferir!) e repositório no GitHub.

```bash
# 1. Resource group
az group create -n previsor-imoveis -l brazilsouth

# 2. Publicar a primeira imagem no ghcr (ou rode o workflow deploy-api manualmente)
cd api && cp -r ../models . && docker build -t ghcr.io/<seu-user>/previsor-imoveis-api:latest .
docker push ghcr.io/<seu-user>/previsor-imoveis-api:latest
# No GitHub: Packages -> previsor-imoveis-api -> Change visibility -> Public

# 3. Infra
az deployment group create -g previsor-imoveis -f infra/main.bicep \
  -p ghcrImage=ghcr.io/<seu-user>/previsor-imoveis-api:latest

# 4. Scraper (Consumption em eastus — a cota de VMs em brazilsouth era 0 nesta assinatura)
az functionapp create -n previmoveis-scraper -g previsor-imoveis \
  --consumption-plan-location eastus --runtime python --runtime-version 3.12 \
  --functions-version 4 --os-type Linux --storage-account <storage-do-bicep>
cd scraper && zip -r scraper.zip function_app.py sample_source.py requirements.txt host.json
az functionapp deployment source config-zip -n previmoveis-scraper -g previsor-imoveis \
  --src scraper.zip --build-remote true

# 5. Budget alert (rede de segurança de custo!)
az consumption budget create --budget-name limite-projeto --amount 20 \
  --category cost --time-grain monthly \
  --start-date $(date +%Y-%m-01) --end-date 2027-12-31

# 6. Front: criar Static Web App (Free) apontando para a pasta web/ via portal ou:
az staticwebapp create -n previmoveis-web -g previsor-imoveis \
  --source https://github.com/<seu-user>/previsor-imoveis --branch main \
  --app-location web --output-location dist --login-with-github
```

Secrets do GitHub Actions: `AZURE_CREDENTIALS` (`az ad sp create-for-rbac --sdk-auth --role contributor --scopes /subscriptions/<sub>/resourceGroups/previsor-imoveis`) e `STORAGE_ACCOUNT` (output do deploy do Bicep).

## Dados

Enquanto o scraper usa a fonte sintética (`scraper/sample_source.py`), o pipeline roda de ponta a ponta com dados gerados. Para dados reais, substitua `_coletar()` em `scraper/function_app.py` — **respeitando robots.txt e termos de uso da fonte** (alternativas: APIs públicas, dados abertos de ITBI da prefeitura).

## Roadmap

- [ ] Fonte de dados real (dados abertos de ITBI / API pública)
- [ ] Monitoramento de drift (comparar distribuição das previsões semana a semana no App Insights)
- [ ] Comparação de modelos no MLflow (XGBoost vs LightGBM vs linear)
- [ ] Posts no LinkedIn documentando cada etapa
