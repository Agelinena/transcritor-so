import json
import os
import sys
import time
import urllib.request
import uuid
import wave
from pathlib import Path

URL = os.environ.get("TRANSCRITOR_URL", "http://localhost:5000").rstrip("/")
PASTA = Path(__file__).resolve().parent
AMOSTRA = PASTA / "amostras" / "fala.wav"
PASTA_AUDIOS = PASTA / "audios"


def pedir(caminho, dados=None, metodo=None, tipo="application/json"):
    corpo = json.dumps(dados).encode() if isinstance(dados, dict) else dados
    requisicao = urllib.request.Request(URL + caminho, data=corpo, method=metodo)
    if corpo is not None:
        requisicao.add_header("Content-Type", tipo)
    try:
        with urllib.request.urlopen(requisicao, timeout=120) as resposta:
            return json.loads(resposta.read() or b"{}")
    except urllib.error.URLError as erro:
        sys.exit(f"Não consegui falar com o Transcritor em {URL}: {erro}")


def gerar_audio(segundos):
    PASTA_AUDIOS.mkdir(exist_ok=True)
    destino = PASTA_AUDIOS / f"fala-{segundos}s.wav"
    if destino.exists():
        return destino
    with wave.open(str(AMOSTRA)) as origem:
        parametros = origem.getparams()
        quadros = origem.readframes(origem.getnframes())
    necessarios = segundos * parametros.framerate * parametros.sampwidth * parametros.nchannels
    with wave.open(str(destino), "wb") as saida:
        saida.setparams(parametros)
        escritos = 0
        while escritos < necessarios:
            pedaco = quadros[: necessarios - escritos]
            saida.writeframes(pedaco)
            escritos += len(pedaco)
    return destino


def enviar(arquivos, modelo=None):
    modelo = modelo or modelo_instalado()
    fronteira = uuid.uuid4().hex
    partes = [f'--{fronteira}\r\nContent-Disposition: form-data; name="modelo"\r\n\r\n{modelo}\r\n'.encode()]
    for nome, caminho in arquivos:
        cabecalho = (f'--{fronteira}\r\nContent-Disposition: form-data; name="arquivos"; filename="{nome}"\r\n'
                     f"Content-Type: audio/wav\r\n\r\n")
        partes.append(cabecalho.encode() + Path(caminho).read_bytes() + b"\r\n")
    partes.append(f"--{fronteira}--\r\n".encode())
    resposta = pedir("/api/jobs", b"".join(partes), "POST", f"multipart/form-data; boundary={fronteira}")
    return resposta["criados"]


def modelo_instalado():
    info = pedir("/api/sistema")
    instalados = [m for m in info["modelos"] if m["situacao"] == "instalado"]
    if not instalados:
        sys.exit("Nenhum modelo instalado: instale um pela página do Transcritor.")
    escolhido = os.environ.get("TRANSCRITOR_MODELO")
    if escolhido:
        return escolhido
    return next((m["id"] for m in instalados if m["recomendado"]), instalados[0]["id"])


def jobs(ids):
    todos = {job["id"]: job for job in pedir("/api/jobs")}
    return [todos[i] for i in ids if i in todos]


def terminou(lista):
    return all(job["estado"] in ("concluido", "falhou") for job in lista)


def mostrar_workers():
    retrato = pedir("/api/workers")
    linha = " | ".join(f"W{w['numero']} {w['estado'][:13]:<13} {('job ' + str(w['job'])) if w['job'] else '':<7}"
                       for w in retrato["workers"])
    print(f"{time.strftime('%H:%M:%S')}  fila {len(retrato['fila']):>2}  motor {retrato['ocupadas']}/{retrato['vagas']}  "
          f"{linha}", flush=True)
    return retrato


def esperar(ids, mostrar=True):
    while True:
        lista = jobs(ids)
        if mostrar:
            mostrar_workers()
        if terminou(lista):
            return lista
        time.sleep(1)


def titulo(texto):
    print()
    print("=" * len(texto))
    print(texto)
    print("=" * len(texto))
