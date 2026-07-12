const fields = {
  speed: document.getElementById("speedValue"),
  engine_rpm: document.getElementById("rpmValue"),
  current_gear: document.getElementById("gearValue"),
  water_temperature: document.getElementById("tempValue"),
};

const desiredFps = Math.max(1, Math.min(100, Number(window.DSW_PULL_FPS || 30)));
let pollHandle = null;

async function loadState() {
  try {
    const response = await fetch("/api/state");
    const data = await response.json();
    render(data);
  } catch (error) {
    console.error(error);
  } finally {
    scheduleNextPoll();
  }
}

function scheduleNextPoll() {
  clearTimeout(pollHandle);
  pollHandle = setTimeout(loadState, Math.round(1000 / desiredFps));
}

function render(data) {
  document.getElementById("gameName").textContent = data.selected_game || "Aguardando jogo";
  document.getElementById("gameState").textContent = data.status_text || "Sem coleta ativa";
  document.getElementById("collectChip").textContent = data.is_collecting ? "Coletando" : "Offline";
  document.getElementById("updatedAt").textContent = new Date().toLocaleTimeString("pt-BR");

  const values = Object.fromEntries((data.telemetry_rows || []).map((row) => [row.key, row.value]));
  Object.entries(fields).forEach(([key, node]) => {
    node.textContent = values[key] ?? 0;
  });

  const list = document.getElementById("telemetryList");
  list.innerHTML = "";
  (data.telemetry_rows || []).slice(0, 12).forEach((row) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `<span class="label">${row.label}</span><strong>${row.value}</strong>`;
    list.appendChild(item);
  });
}

loadState();
