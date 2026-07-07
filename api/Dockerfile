# Imagem da API — publicada no ghcr.io (grátis para imagem pública; evita o custo do ACR)
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
# O modelo é copiado para dentro da imagem no build (gerado por training/train.py)
COPY models/ models/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
