import sys

from comum import enviar, esperar, gerar_audio, pedir, titulo

longo = int(sys.argv[1]) if len(sys.argv) > 1 else 300
curto = 15

titulo(f"Escalonamento: 3 áudios de {longo} s chegam antes de 5 de {curto} s")
arquivo_longo = gerar_audio(longo)
arquivo_curto = gerar_audio(curto)
lote = [(f"longo-{n}.wav", arquivo_longo) for n in range(1, 4)] + [(f"curto-{n}.wav", arquivo_curto) for n in range(1, 6)]

medias = {}
for politica in ("fifo", "sjf"):
    titulo(f"Política {politica.upper()}")
    pedir("/api/politica", {"politica": politica}, "POST")
    ids = enviar(lote)
    resultado = esperar(ids)
    curtos = [job for job in resultado if job["nome"].startswith("curto")]
    espera = sum(job["inicio"] - job["criado"] for job in curtos) / len(curtos)
    retorno = sum(job["fim"] - job["criado"] for job in curtos) / len(curtos)
    total = max(job["fim"] for job in resultado) - min(job["criado"] for job in resultado)
    medias[politica] = (espera, retorno, total)

titulo("Comparação (média dos áudios curtos)")
print(f"{'Política':<10}{'Espera na fila':>18}{'Até ficar pronto':>20}{'Lote inteiro':>16}")
for politica, (espera, retorno, total) in medias.items():
    print(f"{politica.upper():<10}{espera:>16.1f} s{retorno:>18.1f} s{total:>14.1f} s")
print("\nNo FIFO os curtos esperam os longos (efeito comboio). No SJF eles passam na frente:")
print("a espera média cai, mas um longo pode esperar muito se não pararem de chegar curtos (inanição).")
pedir("/api/politica", {"politica": "fifo"}, "POST")
