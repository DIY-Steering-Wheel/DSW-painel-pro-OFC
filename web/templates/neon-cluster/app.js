const node = {
  gameName: document.getElementById("gameName"),
  gameState: document.getElementById("gameState"),
  collectChip: document.getElementById("collectChip"),
  speedValue: document.getElementById("speedValue"),
  speedBar: document.getElementById("speedBar"),
  gearValue: document.getElementById("gearValue"),
  lapValue: document.getElementById("lapValue"),
  rpmValue: document.getElementById("rpmValue"),
  rpmBar: document.getElementById("rpmBar"),
  tempValue: document.getElementById("tempValue"),
  fuelValue: document.getElementById("fuelValue"),
  turboValue: document.getElementById("turboValue"),
  positionValue: document.getElementById("positionValue"),
  throttleValue: document.getElementById("throttleValue"),
  throttleBar: document.getElementById("throttleBar"),
  brakeValue: document.getElementById("brakeValue"),
  brakeBar: document.getElementById("brakeBar"),
  clutchValue: document.getElementById("clutchValue"),
  clutchBar: document.getElementById("clutchBar"),
  signalEngine: document.getElementById("signalEngine"),
  signalLights: document.getElementById("signalLights"),
  signalBrake: document.getElementById("signalBrake"),
  signalCruise: document.getElementById("signalCruise"),
  signalLeft: document.getElementById("signalLeft"),
  signalRight: document.getElementById("signalRight"),
};

function telemetryMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.key, row.value]));
}

function toPercent(value, max = 1) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || max <= 0) return 0;
  return Math.max(0, Math.min(100, (number / max) * 100));
}

function gearText(value) {
  const number = Number(value || 0);
  if (number < 0) return "R";
  if (number === 0) return "N";
  return String(number);
}

function setSignal(element, active) {
  element.classList.toggle("is-on", !!active);
}

async function loadState() {
  try {
    const response = await fetch("/api/state");
    const data = await response.json();
    render(data);
  } catch (error) {
    console.error(error);
  }
}

function render(data) {
  const values = telemetryMap(data.telemetry_rows);
  node.gameName.textContent = data.selected_game || "Aguardando jogo";
  node.gameState.textContent = data.status_text || "Sem coleta ativa";
  node.collectChip.textContent = data.is_collecting ? "LIVE" : "OFFLINE";
  node.speedValue.textContent = values.speed ?? 0;
  node.gearValue.textContent = gearText(values.current_gear);
  node.lapValue.textContent = `Lap ${values.lap_number ?? 0}`;
  node.rpmValue.textContent = values.engine_rpm ?? 0;
  node.tempValue.textContent = `${values.water_temperature ?? 0}`;
  node.fuelValue.textContent = `${values.fuel_percent ?? 0}%`;
  node.turboValue.textContent = `${values.turbo ?? 0}`;
  node.positionValue.textContent = `${values.race_position ?? values.current_day ?? 0}`;
  node.throttleValue.textContent = `${Math.round(toPercent(values.throttle))}%`;
  node.brakeValue.textContent = `${Math.round(toPercent(values.brake))}%`;
  node.clutchValue.textContent = `${Math.round(toPercent(values.clutch))}%`;

  node.speedBar.style.width = `${Math.max(0, Math.min(100, Number(values.speed || 0) / 3))}%`;
  node.rpmBar.style.width = `${toPercent(values.engine_rpm, Math.max(Number(values.engine_rpm_max || 9000), 1))}%`;
  node.throttleBar.style.width = `${toPercent(values.throttle)}%`;
  node.brakeBar.style.width = `${toPercent(values.brake)}%`;
  node.clutchBar.style.width = `${toPercent(values.clutch)}%`;

  setSignal(node.signalEngine, values.engine_enabled);
  setSignal(node.signalLights, values.lights_low_beam || values.lights_high_beam || values.lights_parking);
  setSignal(node.signalBrake, values.park_brake || values.brake > 0.05);
  setSignal(node.signalCruise, values.cruise_control);
  setSignal(node.signalLeft, values.blinker_left_active);
  setSignal(node.signalRight, values.blinker_right_active);
}

loadState();
setInterval(loadState, 300);
