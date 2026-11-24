import os
import time
from pathlib import Path


def pastas_cuda():
    try:
        import nvidia.cublas
        import nvidia.cudnn
    except ImportError:
        return []
    subpasta = "bin" if os.name == "nt" else "lib"
    return [str(Path(list(modulo.__path__)[0]) / subpasta) for modulo in (nvidia.cublas, nvidia.cudnn)]


def preparar_cuda():
    pastas = pastas_cuda()
    if not pastas:
        return
    variavel = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
    atuais = [p for p in os.environ.get(variavel, "").split(os.pathsep) if p]
    os.environ[variavel] = os.pathsep.join(pastas + [p for p in atuais if p not in pastas])
    if os.name == "nt":
        for pasta in pastas:
            os.add_dll_directory(pasta)


def carregar(pasta_modelo, dispositivo, tipo, threads):
    from faster_whisper import WhisperModel

    return WhisperModel(str(pasta_modelo), device=dispositivo, compute_type=tipo, cpu_threads=threads,
                        local_files_only=True)


def transcrever(modelo, audio, idioma, ao_avancar):
    trechos, info = modelo.transcribe(str(audio), language=idioma or None, vad_filter=True, beam_size=5)
    resultado = []
    ultimo_aviso = 0.0
    for trecho in trechos:
        texto = trecho.text.strip()
        if texto:
            resultado.append({"inicio": round(trecho.start, 2), "fim": round(trecho.end, 2), "texto": texto})
        if info.duration and time.monotonic() - ultimo_aviso >= 1:
            ao_avancar(min(trecho.end / info.duration, 0.99))
            ultimo_aviso = time.monotonic()
    return resultado, info.language
