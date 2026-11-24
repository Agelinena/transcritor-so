import sys
import time

from comum import enviar, esperar, gerar_audio, jobs, mostrar_workers, pedir, titulo

segundos = int(sys.argv[1]) if len(sys.argv) > 1 else 600

titulo("Tolerância a falhas: matar um worker no meio do trabalho")
job_id = enviar([("reportagem-longa.wav", gerar_audio(segundos))])[0]
print(f"Job {job_id} criado com {segundos} s de áudio. Esperando um worker começar a transcrever...\n")

while True:
    retrato = mostrar_workers()
    alvo = next((w for w in retrato["workers"] if w["job"] == job_id and w["estado"] == "transcrevendo"), None)
    if alvo:
        break
    time.sleep(0.5)

print(f"\n>>> Matando o worker {alvo['numero']} (pid {alvo['pid']}) com o job {job_id} na mão\n")
pedir(f"/api/workers/{alvo['numero']}/matar", {}, "POST")

for _ in range(4):
    time.sleep(1)
    mostrar_workers()
    situacao = jobs([job_id])[0]
    print(f"          job {job_id}: {situacao['estado']}, tentativa {situacao['tentativas']}")

resultado = esperar([job_id])[0]

titulo("Resultado")
print(f"Job {job_id}: {resultado['estado']} na tentativa {resultado['tentativas']}, "
      f"pelo worker {resultado['worker']} (pid {resultado['pid']})")
print(f"Workers recriados até agora: {pedir('/api/workers')['reinicios']}")
print("O gerente percebeu a morte do processo, devolveu o semáforo do motor, recolocou o job na fila "
      "e criou um worker novo no lugar.")
