from prometheus_client import Counter, Histogram
from prometheus_client.core import GaugeMetricFamily

ESTADOS = {"iniciando": 0, "livre": 1, "convertendo": 2, "esperando": 3, "transcrevendo": 4}

ESPERA = Histogram("transcritor_job_espera_segundos", "Tempo do job na fila até um worker pegar",
                   ["politica"], buckets=(1, 5, 10, 20, 30, 60, 120, 300, 600, 1800))
PROCESSAMENTO = Histogram("transcritor_job_processamento_segundos", "Tempo do worker para transcrever um job",
                          ["modelo", "dispositivo"], buckets=(1, 5, 10, 20, 30, 60, 120, 300, 600, 1800))
CONCLUIDOS = Counter("transcritor_jobs_concluidos", "Jobs transcritos", ["modelo"])
AUDIO = Counter("transcritor_audio_transcrito_segundos", "Segundos de áudio transcritos")
REINICIOS = Counter("transcritor_worker_reinicios", "Workers recriados depois de morrer")


class Coletor:
    def __init__(self, gerente, banco):
        self.gerente = gerente
        self.banco = banco

    def collect(self):
        retrato = self.gerente.retrato()

        fila = GaugeMetricFamily("transcritor_fila_jobs", "Jobs esperando um worker")
        fila.add_metric([], len(retrato["fila"]))
        yield fila

        jobs = GaugeMetricFamily("transcritor_jobs", "Jobs por estado", labels=["estado"])
        contagem = self.banco.contar()
        for estado in ("na_fila", "processando", "concluido", "falhou"):
            jobs.add_metric([estado], contagem.get(estado, 0))
        yield jobs

        estado = GaugeMetricFamily("transcritor_worker_estado",
                                   "0 iniciando, 1 livre, 2 convertendo, 3 esperando o motor, 4 transcrevendo",
                                   labels=["worker"])
        info = GaugeMetricFamily("transcritor_worker_info", "Worker atual", labels=["worker", "pid", "estado", "trabalho"])
        cpu = GaugeMetricFamily("transcritor_worker_cpu_percent", "CPU do processo do worker", labels=["worker"])
        memoria = GaugeMetricFamily("transcritor_worker_memoria_bytes", "Memória (RSS) do worker", labels=["worker"])
        for item in retrato["workers"]:
            nome = f"worker-{item['numero']}"
            estado.add_metric([nome], ESTADOS.get(item["estado"], 0))
            info.add_metric([nome, str(item["pid"]), item["estado"], str(item["job"] or "-")], 1)
            cpu.add_metric([nome], item["cpu"])
            memoria.add_metric([nome], item["memoria"])
        yield estado
        yield info
        yield cpu
        yield memoria

        vagas = GaugeMetricFamily("transcritor_motor_vagas", "Vagas do semáforo do motor")
        vagas.add_metric([], retrato["vagas"])
        yield vagas
        ocupadas = GaugeMetricFamily("transcritor_motor_ocupadas", "Workers dentro do motor (seção crítica)")
        ocupadas.add_metric([], retrato["ocupadas"])
        yield ocupadas

        politica = GaugeMetricFamily("transcritor_politica", "Política de escalonamento em uso", labels=["politica"])
        politica.add_metric([retrato["politica"]], 1)
        yield politica

        dispositivo = GaugeMetricFamily("transcritor_dispositivo", "Onde a transcrição roda", labels=["dispositivo"])
        dispositivo.add_metric([retrato["dispositivo"]], 1)
        yield dispositivo

        if retrato["gpu"]:
            total = GaugeMetricFamily("transcritor_gpu_memoria_total_bytes", "VRAM total",
                                      labels=["gpu"])
            usada = GaugeMetricFamily("transcritor_gpu_memoria_usada_bytes", "VRAM usada", labels=["gpu"])
            total.add_metric([retrato["gpu"]["nome"]], retrato["gpu"]["vram_total_mb"] * 1024 * 1024)
            usada.add_metric([retrato["gpu"]["nome"]], retrato["gpu"]["vram_usada_mb"] * 1024 * 1024)
            yield total
            yield usada
