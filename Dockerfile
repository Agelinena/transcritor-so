FROM python:3.12-slim

ARG GPU=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-gpu.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$GPU" = "1" ]; then pip install --no-cache-dir -r requirements-gpu.txt; fi

RUN useradd --create-home --uid 1000 transcritor \
    && mkdir /dados && chown transcritor:transcritor /dados

COPY app.py ./
COPY transcritor ./transcritor
COPY templates ./templates
COPY static ./static

USER transcritor
ENV TRANSCRITOR_DADOS=/dados PYTHONUNBUFFERED=1
VOLUME /dados
EXPOSE 5000
CMD ["python", "app.py"]
