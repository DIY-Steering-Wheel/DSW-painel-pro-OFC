const node = {
  gameName: document.getElementById("gameName"),
  gameState: document.getElementById("gameState"),
  collectChip: document.getElementById("collectChip"),
  openSettings: document.getElementById("openSettings"),
  closeSettings: document.getElementById("closeSettings"),
  settingsModal: document.getElementById("settingsModal"),
  modalBackdrop: document.getElementById("modalBackdrop"),
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
  shiftLite: document.getElementById("shiftLite"),
  shiftLiteSummary: document.getElementById("shiftLiteSummary"),
  shiftLiteEnabled: document.getElementById("shiftLiteEnabled"),
  shiftLiteStart: document.getElementById("shiftLiteStart"),
  shiftLiteEnd: document.getElementById("shiftLiteEnd"),
};

const SHIFT_LITE_COOKIE = "dsw_neon_cluster_shift_lite";
const SHIFT_LITE_LED_CLASSES = [
  "is-cyan",
  "is-cyan",
  "is-lime",
  "is-lime",
  "is-lime",
  "is-amber",
  "is-amber",
  "is-red",
  "is-red",
  "is-red",
];

const desiredFps = Math.max(1, Math.min(100, Number(window.DSW_PULL_FPS || 30)));
const shiftLiteState = loadShiftLiteConfig();
let pollHandle = null;

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

function signalValue(values, ...keys) {
  return keys.some((key) => !!values[key]);
}

function readCookie(name) {
  const prefix = `${name}=`;
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix))
    ?.slice(prefix.length) || "";
}

function writeCookie(name, value) {
  document.cookie = `${name}=${value}; path=/; max-age=${60 * 60 * 24 * 365}`;
}

function loadShiftLiteConfig() {
  try {
    const raw = readCookie(SHIFT_LITE_COOKIE);
    if (!raw) {
      return { enabled: true, startRpm: 6500, endRpm: 8500 };
    }
    const parsed = JSON.parse(decodeURIComponent(raw));
    return {
      enabled: parsed.enabled !== false,
      startRpm: Number(parsed.startRpm) || 6500,
      endRpm: Number(parsed.endRpm) || 8500,
    };
  } catch (error) {
    console.error(error);
    return { enabled: true, startRpm: 6500, endRpm: 8500 };
  }
}

function persistShiftLiteConfig() {
  writeCookie(SHIFT_LITE_COOKIE, encodeURIComponent(JSON.stringify(shiftLiteState)));
}

function syncShiftLiteControls() {
  node.shiftLiteEnabled.checked = !!shiftLiteState.enabled;
  node.shiftLiteStart.value = String(shiftLiteState.startRpm);
  node.shiftLiteEnd.value = String(shiftLiteState.endRpm);
  node.shiftLiteSummary.textContent = shiftLiteState.enabled
    ? `Ativo de ${shiftLiteState.startRpm} ate ${shiftLiteState.endRpm} RPM`
    : "Shift light desligado";
}

function buildShiftLite() {
  node.shiftLite.innerHTML = "";
  SHIFT_LITE_LED_CLASSES.forEach((className) => {
    const led = document.createElement("div");
    led.className = `shift-lite-led ${className}`;
    node.shiftLite.appendChild(led);
  });
}

function renderShiftLite(currentRpm) {
  const leds = [...node.shiftLite.children];
  const start = Math.min(shiftLiteState.startRpm, shiftLiteState.endRpm);
  const end = Math.max(shiftLiteState.startRpm, shiftLiteState.endRpm);
  const rpm = Number(currentRpm || 0);
  const normalized = end <= start ? (rpm >= end ? 1 : 0) : Math.max(0, Math.min(1, (rpm - start) / (end - start)));
  const activeCount = shiftLiteState.enabled ? Math.round(normalized * leds.length) : 0;
  const isOverLimit = shiftLiteState.enabled && rpm >= end;

  leds.forEach((led, index) => {
    led.classList.toggle("is-on", index < activeCount);
    led.classList.toggle("is-flash", isOverLimit);
  });
}

function openSettings() {
  node.settingsModal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeSettings() {
  node.settingsModal.hidden = true;
  document.body.classList.remove("modal-open");
}

function scheduleNextPoll() {
  clearTimeout(pollHandle);
  pollHandle = setTimeout(loadState, Math.round(1000 / desiredFps));
}

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

function render(data) {
  const values = telemetryMap(data.telemetry_rows);
  node.gameName.textContent = data.selected_game || "Aguardando jogo";
  node.gameState.textContent = data.status_text || "Sem coleta ativa";
  node.collectChip.textContent = data.is_collecting ? "LIVE" : "OFFLINE";
  node.collectChip.classList.toggle("is-live", !!data.is_collecting);

  node.speedValue.textContent = values.speed ?? 0;
  node.gearValue.textContent = gearText(values.current_gear);
  node.lapValue.textContent = `Lap ${values.lap_number ?? 0}`;
  node.positionValue.textContent = `Pos ${values.race_position ?? values.current_day ?? 0}`;
  node.rpmValue.textContent = values.engine_rpm ?? 0;
  node.tempValue.textContent = `${values.water_temperature ?? 0}`;
  node.fuelValue.textContent = `${values.fuel_percent ?? 0}%`;
  node.turboValue.textContent = `${values.turbo ?? 0}`;
  node.throttleValue.textContent = `${Math.round(toPercent(values.throttle))}%`;
  node.brakeValue.textContent = `${Math.round(toPercent(values.brake))}%`;
  node.clutchValue.textContent = `${Math.round(toPercent(values.clutch))}%`;

  node.speedBar.style.width = `${Math.max(0, Math.min(100, Number(values.speed || 0) / 3))}%`;
  node.rpmBar.style.width = `${toPercent(values.engine_rpm, Math.max(Number(values.engine_rpm_max || values.engine_rpm_max_current || 9000), 1))}%`;
  node.throttleBar.style.width = `${toPercent(values.throttle)}%`;
  node.brakeBar.style.width = `${toPercent(values.brake)}%`;
  node.clutchBar.style.width = `${toPercent(values.clutch)}%`;

  setSignal(node.signalEngine, signalValue(values, "engine_enabled", "electric_enabled"));
  setSignal(node.signalLights, signalValue(values, "lights_low_beam", "lights_high_beam", "lights_parking"));
  setSignal(node.signalBrake, signalValue(values, "park_brake") || Number(values.brake || 0) > 0.05);
  setSignal(node.signalCruise, signalValue(values, "cruise_control"));
  setSignal(node.signalLeft, signalValue(values, "blinker_left_active", "blinker_left_enabled", "hazard_warning_lights", "hazard_on"));
  setSignal(node.signalRight, signalValue(values, "blinker_right_active", "blinker_right_enabled", "hazard_warning_lights", "hazard_on"));
  renderShiftLite(values.engine_rpm ?? 0);
}

buildShiftLite();
syncShiftLiteControls();

node.openSettings.addEventListener("click", openSettings);
node.closeSettings.addEventListener("click", closeSettings);
node.modalBackdrop.addEventListener("click", closeSettings);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !node.settingsModal.hidden) {
    closeSettings();
  }
});

node.shiftLiteEnabled.addEventListener("change", () => {
  shiftLiteState.enabled = node.shiftLiteEnabled.checked;
  persistShiftLiteConfig();
  syncShiftLiteControls();
});
node.shiftLiteStart.addEventListener("change", () => {
  shiftLiteState.startRpm = Number(node.shiftLiteStart.value || 6500);
  persistShiftLiteConfig();
  syncShiftLiteControls();
});
node.shiftLiteEnd.addEventListener("change", () => {
  shiftLiteState.endRpm = Number(node.shiftLiteEnd.value || 8500);
  persistShiftLiteConfig();
  syncShiftLiteControls();
});

loadState();
