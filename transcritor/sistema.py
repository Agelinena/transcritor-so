import os
import platform
import shutil
import subprocess

import psutil

GB = 1024 ** 3

MODELOS = {
    "tiny": {"nome": "Tiny", "download_gb": 0.08, "ram_gb": 1, "vram_gb": 1, "descricao": "Teste rápido, erra bastante"},
    "base": {"nome": "Base", "download_gb": 0.15, "ram_gb": 1, "vram_gb": 1, "descricao": "Rápido, para rascunho"},
    "small": {"nome": "Small", "download_gb": 0.5, "ram_gb": 2, "vram_gb": 1.5, "descricao": "Bom equilíbrio na CPU"},
    "medium": {"nome": "Medium", "download_gb": 1.5, "ram_gb": 4, "vram_gb": 3, "descricao": "Mais preciso, mais lento"},
    "turbo": {"nome": "Large v3 Turbo", "download_gb": 1.6, "ram_gb": 4, "vram_gb": 3, "descricao": "Quase o melhor, rápido na GPU"},
    "large-v3": {"nome": "Large v3", "download_gb": 3.1, "ram_gb": 6, "vram_gb": 5, "descricao": "O mais preciso, o mais lento"},
}

RECOMENDACAO_GPU = ["turbo", "medium", "small", "base", "tiny"]
RECOMENDACAO_CPU = ["small", "base", "tiny"]


def detectar_gpu():
    if not shutil.which("nvidia-smi"):
        return None
    comando = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"]
    try:
        saida = subprocess.run(comando, capture_output=True, text=True, timeout=10, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    linhas = saida.strip().splitlines()
    if not linhas:
        return None
    nome, total, usada = [parte.strip() for parte in linhas[0].split(",")]
    return {"nome": nome, "vram_total_mb": int(total), "vram_usada_mb": int(usada)}


def cuda_disponivel():
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def tipo_de_calculo(dispositivo):
    if dispositivo == "cpu":
        return "int8"
    import ctranslate2
    suportados = ctranslate2.get_supported_compute_types("cuda")
    for tipo in ("int8_float16", "float16", "int8"):
        if tipo in suportados:
            return tipo
    return "float32"


def escolher_dispositivo(preferencia, gpu):
    if preferencia == "cpu":
        return "cpu"
    if gpu and cuda_disponivel():
        return "cuda"
    return "cpu"


def modelos_compativeis(dispositivo, ram_gb, vram_gb):
    lista = []
    for chave, modelo in MODELOS.items():
        if dispositivo == "cuda":
            cabe = vram_gb >= modelo["vram_gb"]
        else:
            cabe = ram_gb >= modelo["ram_gb"] + 1
        lista.append({"id": chave, **modelo, "cabe": cabe})
    ordem = RECOMENDACAO_GPU if dispositivo == "cuda" else RECOMENDACAO_CPU
    cabem = {m["id"] for m in lista if m["cabe"]}
    recomendado = next((chave for chave in ordem if chave in cabem), None)
    for modelo in lista:
        modelo["recomendado"] = modelo["id"] == recomendado
    return lista


def detectar(preferencia="auto"):
    gpu = detectar_gpu()
    dispositivo = escolher_dispositivo(preferencia, gpu)
    ram_gb = psutil.virtual_memory().total / GB
    vram_gb = gpu["vram_total_mb"] / 1024 if gpu else 0
    return {
        "so": platform.system(),
        "versao": platform.release(),
        "arquitetura": platform.machine(),
        "python": platform.python_version(),
        "nucleos": os.cpu_count() or 1,
        "ram_gb": round(ram_gb, 1),
        "gpu": gpu,
        "dispositivo": dispositivo,
        "tipo_de_calculo": tipo_de_calculo(dispositivo) if dispositivo == "cuda" else "int8",
        "modelos": modelos_compativeis(dispositivo, ram_gb, vram_gb),
    }
