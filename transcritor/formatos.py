def tempo_srt(segundos):
    milissegundos = int(round(segundos * 1000))
    horas, resto = divmod(milissegundos, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segundos, milissegundos = divmod(resto, 1000)
    return f"{horas:02d}:{minutos:02d}:{segundos:02d},{milissegundos:03d}"


def tempo_curto(segundos):
    minutos, segundos = divmod(int(segundos), 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segundos:02d}"
    return f"{minutos:02d}:{segundos:02d}"


def para_txt(trechos):
    return "\n".join(f"[{tempo_curto(t['inicio'])}] {t['texto']}" for t in trechos) + "\n"


def para_srt(trechos):
    blocos = []
    for numero, trecho in enumerate(trechos, start=1):
        blocos.append(f"{numero}\n{tempo_srt(trecho['inicio'])} --> {tempo_srt(trecho['fim'])}\n{trecho['texto']}\n")
    return "\n".join(blocos)
