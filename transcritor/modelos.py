import threading

from transcritor import config

situacoes = {}
trava = threading.Lock()


def pasta(nome):
    return config.PASTA_MODELOS / nome


def instalado(nome):
    return (pasta(nome) / "model.bin").exists()


def situacao(nome):
    if instalado(nome):
        return "instalado"
    with trava:
        return situacoes.get(nome, "nao_instalado")


def instalar(nome):
    with trava:
        if situacoes.get(nome) == "baixando" or instalado(nome):
            return
        situacoes[nome] = "baixando"
    threading.Thread(target=baixar, args=(nome,), daemon=True).start()


def baixar(nome):
    from faster_whisper import download_model

    print(f"[modelos] baixando {nome}", flush=True)
    try:
        download_model(nome, output_dir=str(pasta(nome)))
        resultado = "instalado"
    except Exception as erro:
        resultado = "erro"
        print(f"[modelos] falha ao baixar {nome}: {erro}", flush=True)
    with trava:
        situacoes[nome] = resultado
    print(f"[modelos] {nome}: {resultado}", flush=True)
