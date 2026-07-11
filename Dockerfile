# VoxBox — challenge-phrase voice capture + Chatterbox voice cloning
FROM python:3.12-slim

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
ENV PIP_DEFAULT_TIMEOUT=120
RUN pip install --no-cache-dir --retries 10 -r requirements.txt

COPY app ./app
COPY static ./static

RUN mkdir -p /app/base_voices /app/outputs

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV HF_HUB_DISABLE_XET=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
