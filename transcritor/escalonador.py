POLITICAS = ("fifo", "sjf")


class Escalonador:
    def __init__(self, politica="fifo"):
        self.politica = politica if politica in POLITICAS else "fifo"
        self.fila = []

    def adicionar(self, job):
        self.fila.append(job)

    def proximo(self):
        if not self.fila:
            return None
        if self.politica == "sjf":
            escolhido = min(self.fila, key=lambda job: (job["duracao"], job["criado"]))
        else:
            escolhido = min(self.fila, key=lambda job: job["criado"])
        self.fila.remove(escolhido)
        return escolhido

    def remover(self, job_id):
        tamanho = len(self.fila)
        self.fila = [job for job in self.fila if job["id"] != job_id]
        return len(self.fila) != tamanho

    def __len__(self):
        return len(self.fila)
