import multiprocessing
import threading
import time
from multiprocessing.connection import wait

import psutil

from transcritor import config, metricas, sistema, worker
from transcritor.escalonador import POLITICAS, Escalonador


class Gerente:
    def __init__(self, banco, dispositivo, tipo, vagas):
        self.contexto = multiprocessing.get_context("spawn")
        self.banco = banco
        self.dispositivo = dispositivo
        self.vagas = vagas
        self.semaforo = self.contexto.BoundedSemaphore(vagas)
        self.trava = threading.Lock()
        self.escalonador = Escalonador(config.POLITICA)
        self.workers = {}
        self.reinicios = 0
        self.gpu = None
        self.rodando = True
        self.ajustes = {
            "dispositivo": dispositivo,
            "tipo": tipo,
            "threads": config.THREADS_POR_WORKER,
            "pasta_modelos": str(config.PASTA_MODELOS),
            "pasta_temp": str(config.PASTA_TEMP),
        }

    def iniciar(self, quantidade):
        with self.trava:
            for job in self.banco.recuperar_fila():
                self.escalonador.adicionar(job)
            for numero in range(1, quantidade + 1):
                self.criar_worker(numero)
        threading.Thread(target=self.ouvir, name="ouvinte", daemon=True).start()
        threading.Thread(target=self.vigiar, name="vigia", daemon=True).start()

    def criar_worker(self, numero):
        conexao, conexao_do_worker = self.contexto.Pipe()
        processo = self.contexto.Process(target=worker.executar, name=f"worker-{numero}",
                                         args=(numero, conexao_do_worker, self.semaforo, self.ajustes), daemon=True)
        processo.start()
        conexao_do_worker.close()
        agora = time.time()
        self.workers[numero] = {
            "numero": numero, "processo": processo, "conexao": conexao, "pid": processo.pid,
            "estado": "iniciando", "job": None, "visto": agora, "desde": agora, "aberta": True,
            "uso": psutil.Process(processo.pid), "cpu": 0.0, "memoria": 0,
        }
        print(f"[gerente] worker {numero} criado, pid {processo.pid}", flush=True)

    def mudar_estado(self, item, estado):
        if item["estado"] != estado:
            item["estado"] = estado
            item["desde"] = time.time()

    def adicionar(self, jobs):
        with self.trava:
            for job in jobs:
                self.escalonador.adicionar(job)
            self.despachar()

    def cancelar(self, job_id):
        with self.trava:
            return self.escalonador.remover(job_id)

    def trocar_politica(self, politica):
        if politica not in POLITICAS:
            return False
        with self.trava:
            self.escalonador.politica = politica
        print(f"[gerente] política de escalonamento: {politica}", flush=True)
        return True

    def despachar(self):
        for item in self.workers.values():
            if item["estado"] != "livre" or not item["aberta"]:
                continue
            job = self.escalonador.proximo()
            if job is None:
                return
            agora = time.time()
            job["tentativas"] += 1
            if job["tentativas"] == 1:
                metricas.ESPERA.labels(self.escalonador.politica).observe(agora - job["criado"])
            item["job"] = job
            self.mudar_estado(item, "convertendo")
            self.banco.atualizar(job["id"], estado="processando", worker=item["numero"], pid=item["pid"],
                                 inicio=agora, tentativas=job["tentativas"], progresso=0)
            print(f"[gerente] job {job['id']} ({job['duracao']:.0f} s) -> worker {item['numero']} "
                  f"[{self.escalonador.politica}]", flush=True)
            try:
                item["conexao"].send(job)
            except OSError:
                item["aberta"] = False

    def ouvir(self):
        while self.rodando:
            with self.trava:
                conexoes = {item["conexao"]: item for item in self.workers.values() if item["aberta"]}
            for conexao in wait(list(conexoes), timeout=0.5):
                item = conexoes[conexao]
                try:
                    evento = conexao.recv()
                except (EOFError, OSError):
                    item["aberta"] = False
                    continue
                with self.trava:
                    if self.workers.get(item["numero"]) is item:
                        self.tratar(item, evento)
                        self.despachar()

    def tratar(self, item, evento):
        tipo, *dados = evento
        item["visto"] = time.time()
        if tipo == "livre":
            item["job"] = None
            self.mudar_estado(item, "livre")
        elif tipo == "estado":
            self.mudar_estado(item, dados[1])
        elif tipo == "progresso":
            self.banco.atualizar(dados[0], progresso=round(dados[1], 3))
        elif tipo == "fim":
            job_id, trechos, idioma = dados
            job = item["job"]
            fim = time.time()
            self.banco.atualizar(job_id, estado="concluido", fim=fim, trechos=trechos, idioma_detectado=idioma,
                                 progresso=1, erro=None)
            if job:
                inicio = self.banco.obter(job_id)["inicio"] or fim
                metricas.PROCESSAMENTO.labels(job["modelo"], self.dispositivo).observe(fim - inicio)
                metricas.CONCLUIDOS.labels(job["modelo"]).inc()
                metricas.AUDIO.inc(job["duracao"])
        elif tipo == "erro":
            self.banco.atualizar(dados[0], estado="falhou", fim=time.time(), erro=dados[1])

    def vigiar(self):
        contador = 0
        while self.rodando:
            time.sleep(1)
            contador += 1
            if contador % 2 == 0:
                self.gpu = sistema.detectar_gpu() if self.dispositivo == "cuda" else None
            with self.trava:
                for item in list(self.workers.values()):
                    self.conferir(item)
                self.despachar()

    def conferir(self, item):
        vivo = item["processo"].is_alive()
        calado = time.time() - item["visto"] > config.SEM_SINAL_SEGUNDOS
        if vivo and calado:
            print(f"[gerente] worker {item['numero']} sem sinal de vida há {config.SEM_SINAL_SEGUNDOS} s: "
                  f"encerrando pid {item['pid']}", flush=True)
            item["processo"].kill()
            item["processo"].join(5)
            vivo = False
        if not vivo:
            self.substituir(item)
            return
        try:
            item["cpu"] = item["uso"].cpu_percent(None)
            item["memoria"] = item["uso"].memory_info().rss
        except psutil.Error:
            pass

    def substituir(self, item):
        codigo = item["processo"].exitcode
        job = item["job"]
        print(f"[gerente] worker {item['numero']} (pid {item['pid']}) morreu com código {codigo}", flush=True)
        self.reinicios += 1
        metricas.REINICIOS.inc()
        if item["estado"] == "transcrevendo":
            try:
                self.semaforo.release()
                print(f"[gerente] semáforo do motor devolvido em nome do worker {item['numero']}", flush=True)
            except ValueError:
                pass
        if job:
            if job["tentativas"] >= config.TENTATIVAS:
                self.banco.atualizar(job["id"], estado="falhou", fim=time.time(),
                                     erro=f"O worker parou nas {job['tentativas']} tentativas")
                print(f"[gerente] job {job['id']} falhou de vez", flush=True)
            else:
                self.banco.atualizar(job["id"], estado="na_fila", worker=None, pid=None, progresso=0)
                self.escalonador.adicionar(job)
                print(f"[gerente] job {job['id']} voltou para a fila", flush=True)
        item["conexao"].close()
        self.criar_worker(item["numero"])

    def matar(self, numero):
        with self.trava:
            item = self.workers.get(numero)
            if item is None:
                return None
            print(f"[gerente] matando o worker {numero} (pid {item['pid']}) a pedido", flush=True)
            item["processo"].kill()
            return item["pid"]

    def retrato(self):
        with self.trava:
            agora = time.time()
            workers = [{
                "numero": item["numero"], "pid": item["pid"], "estado": item["estado"],
                "job": item["job"]["id"] if item["job"] else None,
                "segundos_no_estado": round(agora - item["desde"], 1),
                "cpu": item["cpu"], "memoria": item["memoria"],
            } for item in sorted(self.workers.values(), key=lambda item: item["numero"])]
            return {
                "politica": self.escalonador.politica,
                "fila": [job["id"] for job in self.escalonador.fila],
                "dispositivo": self.dispositivo,
                "vagas": self.vagas,
                "ocupadas": sum(1 for item in self.workers.values() if item["estado"] == "transcrevendo"),
                "reinicios": self.reinicios,
                "gpu": self.gpu,
                "workers": workers,
            }

    def encerrar(self):
        self.rodando = False
        with self.trava:
            itens = list(self.workers.values())
        for item in itens:
            try:
                item["conexao"].send(None)
            except OSError:
                pass
        for item in itens:
            item["processo"].join(3)
            if item["processo"].is_alive():
                item["processo"].kill()
