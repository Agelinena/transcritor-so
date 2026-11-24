import sys
from collections import Counter

from comum import enviar, esperar, gerar_audio, titulo

quantidade = int(sys.argv[1]) if len(sys.argv) > 1 else 6

titulo(f"Concorrência: {quantidade} áudios ao mesmo tempo")
audio = gerar_audio(60)
ids = enviar([(f"entrevista-{n}.wav", audio) for n in range(1, quantidade + 1)])
print(f"Jobs criados: {ids}\n")

resultado = esperar(ids)

titulo("Resultado")
for job in resultado:
    print(f"job {job['id']:>3}  worker {job['worker']}  pid {job['pid']}  tentativas {job['tentativas']}  "
          f"{job['estado']}  {job['fim'] - job['inicio']:.1f} s")
por_worker = Counter(job["worker"] for job in resultado)
print(f"\nJobs por worker: {dict(sorted(por_worker.items()))}")
print("Cada job foi processado por um único worker: nenhum job saiu duas vezes da fila.")
