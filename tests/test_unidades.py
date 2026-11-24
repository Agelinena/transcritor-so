from transcritor import formatos, sistema
from transcritor.banco import Banco
from transcritor.escalonador import Escalonador


def job(numero, duracao, criado):
    return {"id": numero, "duracao": duracao, "criado": criado, "tentativas": 0}


def test_fifo_respeita_a_ordem_de_chegada():
    escalonador = Escalonador("fifo")
    for item in (job(1, 300, 1), job(2, 10, 2), job(3, 60, 3)):
        escalonador.adicionar(item)
    assert [escalonador.proximo()["id"] for _ in range(3)] == [1, 2, 3]
    assert escalonador.proximo() is None


def test_sjf_escolhe_o_mais_curto():
    escalonador = Escalonador("sjf")
    for item in (job(1, 300, 1), job(2, 10, 2), job(3, 60, 3), job(4, 10, 4)):
        escalonador.adicionar(item)
    assert [escalonador.proximo()["id"] for _ in range(4)] == [2, 4, 3, 1]


def test_job_devolvido_volta_para_o_lugar_dele():
    escalonador = Escalonador("fifo")
    escalonador.adicionar(job(2, 10, 2))
    escalonador.adicionar(job(1, 10, 1))
    assert escalonador.proximo()["id"] == 1


def test_politica_desconhecida_vira_fifo():
    assert Escalonador("aleatoria").politica == "fifo"


def test_remover_da_fila():
    escalonador = Escalonador()
    escalonador.adicionar(job(1, 10, 1))
    assert escalonador.remover(1)
    assert not escalonador.remover(1)
    assert len(escalonador) == 0


def test_srt():
    trechos = [{"inicio": 0, "fim": 2.5, "texto": "Olá"}, {"inicio": 3661.2, "fim": 3662, "texto": "Tchau"}]
    assert formatos.para_srt(trechos) == (
        "1\n00:00:00,000 --> 00:00:02,500\nOlá\n\n2\n01:01:01,200 --> 01:01:02,000\nTchau\n")
    assert formatos.para_txt(trechos) == "[00:00] Olá\n[1:01:01] Tchau\n"


def test_modelos_na_cpu_com_pouca_memoria():
    lista = {m["id"]: m for m in sistema.modelos_compativeis("cpu", ram_gb=2.5, vram_gb=0)}
    assert lista["tiny"]["cabe"] and lista["base"]["cabe"]
    assert not lista["small"]["cabe"] and not lista["turbo"]["cabe"]
    assert lista["base"]["recomendado"]


def test_modelos_na_gpu():
    lista = {m["id"]: m for m in sistema.modelos_compativeis("cuda", ram_gb=16, vram_gb=4)}
    assert lista["turbo"]["cabe"] and lista["turbo"]["recomendado"]
    assert not lista["large-v3"]["cabe"]


def test_cpu_forcada_mesmo_com_gpu():
    assert sistema.escolher_dispositivo("cpu", {"nome": "GPU"}) == "cpu"
    assert sistema.escolher_dispositivo("auto", None) == "cpu"


def test_banco_recupera_a_fila_depois_de_reiniciar(tmp_path):
    banco = Banco(tmp_path / "teste.db")
    primeiro = banco.criar("a.mp3", "/tmp/a.mp3", 30, "small", None)
    segundo = banco.criar("b.mp3", "/tmp/b.mp3", 60, "small", "pt")
    banco.atualizar(primeiro, estado="processando", worker=1, pid=123)
    banco.atualizar(segundo, estado="concluido", trechos=[{"inicio": 0, "fim": 1, "texto": "oi"}])
    fila = banco.recuperar_fila()
    assert [item["id"] for item in fila] == [primeiro]
    assert banco.obter(primeiro)["estado"] == "na_fila"
    assert banco.obter(segundo)["trechos"][0]["texto"] == "oi"
    assert banco.contar() == {"na_fila": 1, "concluido": 1}
