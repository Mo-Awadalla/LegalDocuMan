# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: Python backend + serve frontend
FROM python:3.11-slim

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /project

COPY requirements.txt .

RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY --from=frontend-build /frontend/dist /project/frontend/dist

RUN mkdir -p /project/models && \
    curl -L -o /project/models/checkpoint_best_total.pth \
    "https://huggingface.co/Mo-Awadalla/legaldocuman-rfdetr/resolve/main/checkpoint_best_total.pth"

RUN mkdir -p /project/processed /project/uploads

EXPOSE 5000

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-120} run:app"]
