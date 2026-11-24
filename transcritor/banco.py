import json
import sqlite3
import threading
import time

ESQUEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    duracao REAL NOT NULL,
    modelo TEXT NOT NULL,
    idioma TEXT,
    estado TEXT NOT NULL DEFAULT 'na_fila',
    worker INTEGER,
    pid INTEGER,
    tentativas INTEGER NOT NULL DEFAULT 0,
    progresso REAL NOT NULL DEFAULT 0,
    criado REAL NOT NULL,
    inicio REAL,
    fim REAL,
    idioma_detectado TEXT,
    trechos TEXT,
    erro TEXT
);
"""

CAMPOS_DA_LISTA = ("id, nome, duracao, modelo, idioma, estado, worker, pid, tentativas, progresso, criado, inicio, "
                   "fim, idioma_detectado, erro")


class Banco:
    def __init__(self, caminho):
        self.conexao = sqlite3.connect(caminho, check_same_thread=False)
        self.conexao.row_factory = sqlite3.Row
        self.trava = threading.Lock()
        with self.trava:
            self.conexao.executescript(ESQUEMA)

    def criar(self, nome, arquivo, duracao, modelo, idioma):
        with self.trava, self.conexao:
            cursor = self.conexao.execute(
                "INSERT INTO jobs (nome, arquivo, duracao, modelo, idioma, criado) VALUES (?, ?, ?, ?, ?, ?)",
                (nome, arquivo, duracao, modelo, idioma, time.time()))
            return cursor.lastrowid

    def atualizar(self, job_id, **campos):
        if "trechos" in campos:
            campos["trechos"] = json.dumps(campos["trechos"], ensure_ascii=False)
        colunas = ", ".join(f"{nome} = ?" for nome in campos)
        with self.trava, self.conexao:
            self.conexao.execute(f"UPDATE jobs SET {colunas} WHERE id = ?", (*campos.values(), job_id))

    def obter(self, job_id):
        with self.trava:
            linha = self.conexao.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if linha is None:
            return None
        job = dict(linha)
        job["trechos"] = json.loads(job["trechos"]) if job["trechos"] else []
        return job

    def obter_para_fila(self, job_id):
        with self.trava:
            linha = self.conexao.execute(
                "SELECT id, arquivo, duracao, modelo, idioma, criado, tentativas FROM jobs WHERE id = ?",
                (job_id,)).fetchone()
        return dict(linha)

    def listar(self, limite=200):
        with self.trava:
            linhas = self.conexao.execute(f"SELECT {CAMPOS_DA_LISTA} FROM jobs ORDER BY id DESC LIMIT ?",
                                          (limite,)).fetchall()
        return [dict(linha) for linha in linhas]

    def apagar(self, job_id):
        with self.trava, self.conexao:
            self.conexao.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def contar(self):
        with self.trava:
            linhas = self.conexao.execute("SELECT estado, COUNT(*) FROM jobs GROUP BY estado").fetchall()
        return {estado: total for estado, total in linhas}

    def recuperar_fila(self):
        with self.trava, self.conexao:
            self.conexao.execute(
                "UPDATE jobs SET estado = 'na_fila', worker = NULL, pid = NULL, progresso = 0 "
                "WHERE estado = 'processando'")
            linhas = self.conexao.execute(
                "SELECT id, arquivo, duracao, modelo, idioma, criado, tentativas FROM jobs WHERE estado = 'na_fila'"
            ).fetchall()
        return [dict(linha) for linha in linhas]
