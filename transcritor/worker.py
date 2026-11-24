import gc
import os
import signal
import subprocess
import threading
from pathlib import Path


class Canal:
    def __init__(self, conexao):
        self.conexao = conexao
        self.trava = threading.Lock()

    def enviar(self, *evento):
        with self.trava:
            self.conexao.send(evento)

    def receber(self):
        return self.conexao.recv()


def avisar_que_esta_vivo(canal, parar):
    while not parar.wait(2):
        canal.enviar("vivo")


def converter(origem, destino):
    comando = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origem), "-vn", "-ac", "1", "-ar", "16000", str(destino)]
    subprocess.run(comando, check=True, capture_output=True)


def executar(numero, conexao, semaforo, ajustes):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    canal = Canal(conexao)
    parar = threading.Event()
    threading.Thread(target=avisar_que_esta_vivo, args=(canal, parar), daemon=True).start()

    from transcritor import motor
    motor.preparar_cuda()
    print(f"[worker {numero}] pronto, pid {os.getpid()}", flush=True)
    canal.enviar("livre")

    while True:
        job = canal.receber()
        if job is None:
            break
        try:
            processar(numero, job, canal, semaforo, ajustes)
        except Exception as erro:
            print(f"[worker {numero}] job {job['id']} falhou: {erro}", flush=True)
            canal.enviar("erro", job["id"], str(erro)[:500])
        canal.enviar("livre")
    parar.set()


def processar(numero, job, canal, semaforo, ajustes):
    from transcritor import motor

    audio = Path(ajustes["pasta_temp"]) / f"job-{job['id']}.wav"
    try:
        canal.enviar("estado", job["id"], "convertendo")
        converter(job["arquivo"], audio)

        canal.enviar("estado", job["id"], "esperando")
        with semaforo:
            canal.enviar("estado", job["id"], "transcrevendo")
            print(f"[worker {numero}] job {job['id']}: entrou no motor ({ajustes['dispositivo']})", flush=True)
            modelo = motor.carregar(Path(ajustes["pasta_modelos"]) / job["modelo"], ajustes["dispositivo"],
                                    ajustes["tipo"], ajustes["threads"])
            trechos, idioma = motor.transcrever(modelo, audio, job["idioma"],
                                                lambda progresso: canal.enviar("progresso", job["id"], progresso))
            del modelo
            gc.collect()
    finally:
        audio.unlink(missing_ok=True)

    print(f"[worker {numero}] job {job['id']}: pronto, {len(trechos)} trechos", flush=True)
    canal.enviar("fim", job["id"], trechos, idioma)
