const $ = (seletor) => document.querySelector(seletor);

const NOMES_SITUACAO = { na_fila: "Na fila", processando: "Transcrevendo", concluido: "Pronto", falhou: "Falhou" };
const NOMES_ESTADO = {
  iniciando: "iniciando",
  livre: "livre",
  convertendo: "convertendo o áudio (ffmpeg)",
  esperando: "esperando o motor (semáforo)",
  transcrevendo: "transcrevendo",
};

let modeloEscolhido = "";

function tempo(segundos) {
  segundos = Math.round(segundos || 0);
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const s = segundos % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function megabytes(bytes) {
  return `${Math.round(bytes / 1024 / 1024)} MB`;
}

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

async function pedir(url, opcoes) {
  const resposta = await fetch(url, opcoes);
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(corpo.erro || `Erro ${resposta.status}`);
  return corpo;
}

async function atualizarSistema() {
  const info = await pedir("/api/sistema");
  const gpu = info.gpu ? `${info.gpu.nome} (${Math.round(info.gpu.vram_total_mb / 1024)} GB)` : "nenhuma NVIDIA";
  $("#chip-dispositivo").textContent = info.dispositivo === "cuda" ? `GPU · ${info.gpu.nome}` : "CPU";
  $("#info-sistema").innerHTML = `
    <dt>Sistema</dt><dd>${escapar(info.so)} ${escapar(info.versao)}</dd>
    <dt>Processador</dt><dd>${info.nucleos} núcleos (${escapar(info.arquitetura)})</dd>
    <dt>Memória</dt><dd>${info.ram_gb} GB</dd>
    <dt>Placa de vídeo</dt><dd>${escapar(gpu)}</dd>
    <dt>Transcreve na</dt><dd>${info.dispositivo === "cuda" ? "GPU" : "CPU"} · ${escapar(info.tipo_de_calculo)}</dd>`;

  $("#lista-modelos").innerHTML = info.modelos.map((modelo) => {
    let acao = `<button type="button" data-instalar="${modelo.id}">Instalar · ${modelo.download_gb} GB</button>`;
    if (modelo.situacao === "instalado") acao = `<span class="etiqueta instalado">Instalado</span>`;
    if (modelo.situacao === "baixando") acao = `<span class="etiqueta baixando">Baixando…</span>`;
    if (modelo.situacao === "erro") acao = `<button type="button" data-instalar="${modelo.id}">Tentar de novo</button>`;
    if (!modelo.cabe) acao = `<span class="etiqueta">Não cabe</span>`;
    const classes = [modelo.cabe ? "" : "nao-cabe", modelo.recomendado ? "recomendado" : ""].join(" ");
    const selo = modelo.recomendado ? " · recomendado" : "";
    return `<li class="${classes}"><div><strong>${escapar(modelo.nome)}</strong>
      <small>${escapar(modelo.descricao)}${selo}</small></div>${acao}</li>`;
  }).join("");

  const instalados = info.modelos.filter((modelo) => modelo.situacao === "instalado");
  const recomendado = instalados.find((modelo) => modelo.recomendado);
  if (!instalados.some((modelo) => modelo.id === modeloEscolhido)) {
    modeloEscolhido = (recomendado || instalados[0] || {}).id || "";
  }
  $("#modelo").innerHTML = instalados.length
    ? instalados.map((modelo) => `<option value="${modelo.id}" ${modelo.id === modeloEscolhido ? "selected" : ""}>${escapar(modelo.nome)}</option>`).join("")
    : `<option value="">Instale um modelo ao lado</option>`;
  $("#botao-enviar").disabled = !instalados.length;
}

async function atualizarJobs() {
  const jobs = await pedir("/api/jobs");
  const naFila = jobs.filter((job) => job.estado === "na_fila").length;
  const rodando = jobs.filter((job) => job.estado === "processando").length;
  $("#resumo-fila").textContent = jobs.length ? `${rodando} transcrevendo · ${naFila} na fila` : "";
  if (!jobs.length) {
    $("#lista-jobs").innerHTML = `<tr><td colspan="6" class="vazio">Nenhuma transcrição ainda</td></tr>`;
    return;
  }
  $("#lista-jobs").innerHTML = jobs.map((job) => {
    const barra = job.estado === "processando"
      ? `<div class="barra"><span style="width:${Math.round(job.progresso * 100)}%"></span></div>` : "";
    const nota = job.estado === "falhou" ? `<div class="discreto">${escapar(job.erro)}</div>` : "";
    const worker = job.worker ? `#${job.worker} · pid ${job.pid}` : "—";
    const apagar = job.estado === "processando" ? "" : `<button type="button" class="apagar" data-apagar="${job.id}" title="Apagar">×</button>`;
    return `<tr class="${job.estado === "concluido" ? "clicavel" : ""}" data-job="${job.id}">
      <td title="${escapar(job.nome)}">${escapar(job.nome)}</td>
      <td>${tempo(job.duracao)}</td>
      <td>${escapar(job.modelo)}</td>
      <td><span class="situacao ${job.estado}">${NOMES_SITUACAO[job.estado] || job.estado}</span>${barra}${nota}</td>
      <td>${worker}</td>
      <td>${apagar}</td></tr>`;
  }).join("");
}

async function atualizarWorkers() {
  const retrato = await pedir("/api/workers");
  $("#info-motor").textContent =
    `Motor: ${retrato.ocupadas} de ${retrato.vagas} vaga(s) em uso · ${retrato.fila.length} na fila · ${retrato.reinicios} reinício(s)`;
  document.querySelectorAll("#politica button").forEach((botao) => {
    botao.classList.toggle("ativo", botao.dataset.politica === retrato.politica);
  });
  $("#lista-workers").innerHTML = retrato.workers.map((worker) => {
    const job = worker.job ? ` · job ${worker.job}` : "";
    return `<li class="${worker.estado}"><span class="bolinha"></span>
      <strong>Worker ${worker.numero} <span class="discreto">pid ${worker.pid}</span></strong>
      <button type="button" data-matar="${worker.numero}" title="Encerra o processo à força (demonstração)">matar</button>
      <small>${NOMES_ESTADO[worker.estado] || worker.estado}${job} · CPU ${Math.round(worker.cpu)}% · ${megabytes(worker.memoria)}</small></li>`;
  }).join("");
}

async function abrirDetalhe(id) {
  const job = await pedir(`/api/jobs/${id}`);
  $("#detalhe-titulo").textContent = job.nome;
  const gasto = job.fim && job.inicio ? tempo(job.fim - job.inicio) : "—";
  $("#detalhe-info").textContent =
    `${tempo(job.duracao)} de áudio · modelo ${job.modelo} · idioma ${job.idioma_detectado || "?"} · transcrito em ${gasto}`;
  $("#baixar-txt").href = `/api/jobs/${id}.txt`;
  $("#baixar-srt").href = `/api/jobs/${id}.srt`;
  $("#detalhe-trechos").innerHTML = job.trechos.length
    ? job.trechos.map((trecho) => `<li><time>${tempo(trecho.inicio)}</time><span>${escapar(trecho.texto)}</span></li>`).join("")
    : `<li><span></span><span class="discreto">Nenhuma fala encontrada no áudio.</span></li>`;
  $("#copiar").onclick = () => navigator.clipboard.writeText(job.trechos.map((trecho) => trecho.texto).join("\n"));
  $("#detalhe").showModal();
}

function mostrarMensagem(texto, erro = false) {
  $("#mensagem").textContent = texto;
  $("#mensagem").classList.toggle("erro", erro);
}

$("#arquivos").addEventListener("change", () => {
  const quantidade = $("#arquivos").files.length;
  $("#escolhidos").textContent = quantidade ? `${quantidade} arquivo(s) escolhido(s)` : "";
});

["dragenter", "dragover"].forEach((evento) => $("#area-arquivos").addEventListener(evento, (e) => {
  e.preventDefault();
  $("#area-arquivos").classList.add("arrastando");
}));
["dragleave", "drop"].forEach((evento) => $("#area-arquivos").addEventListener(evento, () => {
  $("#area-arquivos").classList.remove("arrastando");
}));
$("#area-arquivos").addEventListener("drop", (e) => {
  e.preventDefault();
  $("#arquivos").files = e.dataTransfer.files;
  $("#arquivos").dispatchEvent(new Event("change"));
});

$("#modelo").addEventListener("change", () => { modeloEscolhido = $("#modelo").value; });

$("#form-envio").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!$("#arquivos").files.length) return mostrarMensagem("Escolha pelo menos um arquivo.", true);
  $("#botao-enviar").disabled = true;
  mostrarMensagem("Enviando…");
  try {
    const resposta = await pedir("/api/jobs", { method: "POST", body: new FormData($("#form-envio")) });
    const recusados = resposta.recusados.length ? ` Recusados (não são áudio/vídeo): ${resposta.recusados.join(", ")}` : "";
    mostrarMensagem(`${resposta.criados.length} arquivo(s) na fila.${recusados}`);
    $("#form-envio").reset();
    $("#escolhidos").textContent = "";
    atualizarJobs();
  } catch (erro) {
    mostrarMensagem(erro.message, true);
  } finally {
    $("#botao-enviar").disabled = false;
  }
});

document.addEventListener("click", async (e) => {
  const alvo = e.target.closest("[data-instalar], [data-apagar], [data-matar], [data-politica], tr[data-job]");
  if (!alvo) return;
  if (alvo.dataset.instalar) {
    await pedir(`/api/modelos/${alvo.dataset.instalar}`, { method: "POST" });
    atualizarSistema();
  } else if (alvo.dataset.apagar) {
    e.stopPropagation();
    await pedir(`/api/jobs/${alvo.dataset.apagar}`, { method: "DELETE" }).catch((erro) => alert(erro.message));
    atualizarJobs();
  } else if (alvo.dataset.matar) {
    await pedir(`/api/workers/${alvo.dataset.matar}/matar`, { method: "POST" });
    atualizarWorkers();
  } else if (alvo.dataset.politica) {
    await pedir("/api/politica", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ politica: alvo.dataset.politica }),
    });
    atualizarWorkers();
  } else if (alvo.classList.contains("clicavel")) {
    abrirDetalhe(alvo.dataset.job);
  }
});

$("#fechar-detalhe").addEventListener("click", () => $("#detalhe").close());
$("#link-grafana").href = `${location.protocol}//${location.hostname}:3000/d/transcritor`;

function repetir(funcao, intervalo) {
  const rodar = () => funcao().catch(() => {}).finally(() => setTimeout(rodar, intervalo));
  rodar();
}

repetir(atualizarSistema, 3000);
repetir(atualizarJobs, 1500);
repetir(atualizarWorkers, 1000);
