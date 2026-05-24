FROM python:3.11-slim

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /project

COPY requirements.txt .

# Install CPU-only PyTorch first to avoid pulling in the large CUDA wheels
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bake the RF-DETR checkpoint into the image so the model is available at runtime.
# Downloaded from HuggingFace Hub: https://huggingface.co/Mo-Awadalla/legaldocuman-rfdetr
RUN mkdir -p /project/models && \
    curl -L -o /project/models/checkpoint_best_total.pth \
    "https://huggingface.co/Mo-Awadalla/legaldocuman-rfdetr/resolve/main/checkpoint_best_total.pth"

CMD ["python", "run.py"]
