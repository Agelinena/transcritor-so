import logging
import os
import signal
import subprocess
import sys
import time
import uuid

from flask import Flask, Response, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from werkzeug.utils import secure_filename

from transcritor import config, formatos, modelos, sistema
from transcritor.banco import Banco
from transcritor.gerente import Gerente
from transcritor.metricas import Coletor

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 ** 3
logging.getLogger("werkzeug").setLevel(logging.WARNING)

estado = {}

IDIOMAS = {"": "Detectar sozinho", "pt": "Português", "en": "Inglês", "es": "Espanhol", "fr": "Francês"}


def medir_duracao(caminho):
    comando = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(caminho)]
    try:
        saida = subprocess.run(comando, capture_output=True, text=True, timeout=60).stdout.strip()
        return float(saida)
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def descrever_sistema():
    info = dict(estado["sistema"])
    info["modelos"] = [{**modelo, "situacao": modelos.situacao(modelo["id"])} for modelo in info["modelos"]]
    info["workers"] = config.WORKERS
    info["vagas"] = estado["gerente"].vagas
    return info


@app.get("/")
def inicio():
    return render_template("index.html", idiomas=IDIOMAS)


@app.get("/api/sistema")
def api_sistema():
    return jsonify(descrever_sistema())


@app.post("/api/modelos/<nome>")
def api_instalar(nome):
    if nome not in sistema.MODELOS:
        return jsonify(erro="Modelo desconhecido"), 404
    modelos.instalar(nome)
    return jsonify(situacao=modelos.situacao(nome))


@app.get("/api/jobs")
def api_jobs():
    return jsonify(estado["banco"].listar())


@app.post("/api/jobs")
def api_criar_jobs():
    modelo = request.form.get("modelo", "")
    idioma = request.form.get("idioma", "") or None
    if not modelos.instalado(modelo):
        return jsonify(erro="Instale o modelo antes de usar"), 400
    arquivos = request.files.getlist("arquivos")
    if not arquivos:
        return jsonify(erro="Envie pelo menos um arquivo"), 400
    criados, recusados = [], []
    for arquivo in arquivos:
        nome = arquivo.filename or "arquivo"
        destino = config.PASTA_UPLOADS / f"{uuid.uuid4().hex}-{secure_filename(nome) or 'arquivo'}"
        arquivo.save(destino)
        duracao = medir_duracao(destino)
        if not duracao:
            destino.unlink(missing_ok=True)
            recusados.append(nome)
            continue
        criados.append(estado["banco"].criar(nome, str(destino), duracao, modelo, idioma))
    estado["gerente"].adicionar([estado["banco"].obter_para_fila(job_id) for job_id in criados])
    return jsonify(criados=criados, recusados=recusados), 201 if criados else 400


@app.get("/api/jobs/<int:job_id>")
def api_job(job_id):
    job = estado["banco"].obter(job_id)
    if job is None:
        return jsonify(erro="Não encontrado"), 404
    job.pop("arquivo", None)
    return jsonify(job)


@app.delete("/api/jobs/<int:job_id>")
def api_apagar(job_id):
    job = estado["banco"].obter(job_id)
    if job is None:
        return jsonify(erro="Não encontrado"), 404
    if job["estado"] == "processando":
        return jsonify(erro="Espere a transcrição terminar"), 409
    estado["gerente"].cancelar(job_id)
    estado["banco"].apagar(job_id)
    if os.path.exists(job["arquivo"]):
        os.remove(job["arquivo"])
    return jsonify(apagado=job_id)


@app.get("/api/jobs/<int:job_id>.<formato>")
def api_baixar(job_id, formato):
    job = estado["banco"].obter(job_id)
    if job is None or job["estado"] != "concluido" or formato not in ("txt", "srt"):
        return jsonify(erro="Não encontrado"), 404
    texto = formatos.para_txt(job["trechos"]) if formato == "txt" else formatos.para_srt(job["trechos"])
    nome = os.path.splitext(job["nome"])[0] + "." + formato
    return Response(texto, mimetype="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{nome}"})


@app.get("/api/workers")
def api_workers():
    return jsonify(estado["gerente"].retrato())


@app.post("/api/workers/<int:numero>/matar")
def api_matar(numero):
    pid = estado["gerente"].matar(numero)
    if pid is None:
        return jsonify(erro="Worker não existe"), 404
    return jsonify(morto=numero, pid=pid)


@app.post("/api/politica")
def api_politica():
    politica = (request.get_json(silent=True) or {}).get("politica", "")
    if not estado["gerente"].trocar_politica(politica):
        return jsonify(erro="Use fifo ou sjf"), 400
    return jsonify(politica=politica)


@app.get("/metrics")
def api_metricas():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


def calcular_vagas(dispositivo, nucleos):
    if config.VAGAS > 0:
        return config.VAGAS
    if dispositivo == "cuda":
        return 1
    return max(1, nucleos // config.THREADS_POR_WORKER)


def iniciar():
    config.criar_pastas()
    from transcritor import motor
    motor.preparar_cuda()

    info = sistema.detectar(config.DISPOSITIVO)
    print(f"[sistema] {info['so']} {info['versao']} ({info['arquitetura']}), {info['nucleos']} núcleos, "
          f"{info['ram_gb']} GB de RAM", flush=True)
    if info["gpu"]:
        print(f"[sistema] GPU: {info['gpu']['nome']}, {info['gpu']['vram_total_mb']} MB", flush=True)
    print(f"[sistema] transcrição em: {info['dispositivo']} ({info['tipo_de_calculo']})", flush=True)

    banco = Banco(config.BANCO)
    vagas = calcular_vagas(info["dispositivo"], info["nucleos"])
    gerente = Gerente(banco, info["dispositivo"], info["tipo_de_calculo"], vagas)
    estado.update(sistema=info, banco=banco, gerente=gerente)
    REGISTRY.register(Coletor(gerente, banco))

    recomendado = next((m["id"] for m in info["modelos"] if m["recomendado"]), None)
    instalados = [m["id"] for m in info["modelos"] if modelos.instalado(m["id"])]
    if not instalados and recomendado and os.environ.get("TRANSCRITOR_INSTALAR_AUTOMATICO", "1") == "1":
        print(f"[modelos] nenhum modelo instalado; instalando o recomendado: {recomendado}", flush=True)
        modelos.instalar(recomendado)

    gerente.iniciar(config.WORKERS)
    print(f"[gerente] {config.WORKERS} workers, {vagas} vaga(s) no motor, política {config.POLITICA}", flush=True)
    return gerente


def main():
    gerente = iniciar()

    def sair(*_):
        print("[gerente] encerrando os workers", flush=True)
        gerente.encerrar()
        sys.exit(0)

    signal.signal(signal.SIGTERM, sair)
    print(f"[web] abra http://localhost:{config.PORTA}", flush=True)
    try:
        app.run(host="0.0.0.0", port=config.PORTA, threaded=True, use_reloader=False)
    finally:
        gerente.encerrar()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
