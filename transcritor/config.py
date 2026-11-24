import os
from pathlib import Path


def numero(nome, padrao):
    valor = os.environ.get(nome, "").strip()
    return int(valor) if valor else padrao


PASTA_DADOS = Path(os.environ.get("TRANSCRITOR_DADOS", "dados")).resolve()
PASTA_MODELOS = PASTA_DADOS / "modelos"
PASTA_UPLOADS = PASTA_DADOS / "uploads"
PASTA_TEMP = PASTA_DADOS / "temp"
BANCO = PASTA_DADOS / "transcritor.db"

PORTA = numero("TRANSCRITOR_PORTA", 5000)
WORKERS = numero("TRANSCRITOR_WORKERS", 3)
DISPOSITIVO = os.environ.get("TRANSCRITOR_DISPOSITIVO", "auto").strip().lower()
POLITICA = os.environ.get("TRANSCRITOR_POLITICA", "fifo").strip().lower()
VAGAS = numero("TRANSCRITOR_VAGAS", 0)
THREADS_POR_WORKER = numero("TRANSCRITOR_THREADS", 4)
TENTATIVAS = numero("TRANSCRITOR_TENTATIVAS", 2)
SEM_SINAL_SEGUNDOS = numero("TRANSCRITOR_SEM_SINAL", 15)


def criar_pastas():
    for pasta in (PASTA_DADOS, PASTA_MODELOS, PASTA_UPLOADS, PASTA_TEMP):
        pasta.mkdir(parents=True, exist_ok=True)
