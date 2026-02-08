FROM nvidia/cuda:12.6.2-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    git ca-certificates curl \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip setuptools wheel

WORKDIR /opt/ComfyUI

ARG COMFYUI_REF=v0.12.3
RUN git clone --depth 1 --branch "${COMFYUI_REF}" https://github.com/Comfy-Org/ComfyUI.git .

# 1) Install GPU torch stack from the PyTorch CUDA 12.6 index ONLY
RUN python3 -m pip install --no-cache-dir \
    torch==2.9.0+cu126 torchvision==0.24.0+cu126 torchaudio==2.9.0+cu126 \
    --index-url https://download.pytorch.org/whl/cu126

# 2) Install the rest from normal PyPI (requirements.txt)
RUN python3 -m pip install --no-cache-dir -r requirements.txt \
 && python3 -c "import requests; print('requests OK')" \
 && python3 -c "import torch; print('torch OK', torch.__version__)" \
 && python3 -m pip check


# Bake the 3 models into the image (these files come from Cloud Build step)
COPY models/diffusion_models/z_image_turbo_bf16.safetensors /opt/ComfyUI/models/diffusion_models/z_image_turbo_bf16.safetensors
COPY models/text_encoders/qwen_3_4b.safetensors /opt/ComfyUI/models/text_encoders/qwen_3_4b.safetensors
COPY models/vae/ae.safetensors /opt/ComfyUI/models/vae/ae.safetensors

RUN useradd -m -u 10001 comfy \
 && chown -R comfy:comfy /opt/ComfyUI
USER comfy

EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/system_stats" >/dev/null || exit 1

CMD ["sh", "-lc", "python3 main.py --listen 0.0.0.0 --port ${PORT} --disable-auto-launch --disable-mmap"]
