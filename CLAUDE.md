# Regras para conversas neste repositório

Fale sempre em português.

Projeto final de Sistemas Operacionais: o código tem que ser simples, do jeito que um aluno escreveria, **sem comentários**. Nomes em português. Cada conceito de SO precisa continuar visível no código e no painel do Grafana.

## Antes

- `git pull`. Se houver mudança local que não é sua, pare e pergunte.
- Este repositório é **público**: nada de domínio, IP, e-mail ou segredo reais.

## Testes com Docker

- Projeto `teste-transcritor-so` (`docker compose -p teste-transcritor-so ...`), portas altas (`PORTA=15500 PORTA_GRAFANA=13000`).
- Sem Docker: `TRANSCRITOR_DADOS=~/.cache/bergatrix-teste/transcritor-so/nativo TRANSCRITOR_PORTA=15000 python app.py`.
- Depois: `docker compose -p teste-transcritor-so -f docker-compose.yml -f docker-compose.monitor.yml down -v --rmi local` e apagar a pasta de teste. Limpe só este projeto.

## Depois

1. `pytest` passando.
2. Rode os scripts de `demo/` contra o app se mexeu no gerente, no worker ou no escalonador.
3. Atualize o README e o relatório (`docs/relatorio/`) que a mudança deixou errados, no mesmo commit.
4. Diga o que foi e o que não foi testado (GPU no Docker, Windows, Mac).

## Commits

- Só com autorização de quem pediu a mudança.
- E-mail pessoal, nunca o do trabalho: confira `git config user.email` contra `git log -3 --format=%ae`.
