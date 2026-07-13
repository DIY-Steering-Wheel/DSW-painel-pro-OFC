const ui = {};
let state = null;
let pollTimer = null;
let activeSettingsTab = "general";
let fallbackOverridesDraft = {};
let equalizationRulesDraft = [];
let equalizationSelectedGameIds = [];
let mergeRulesDraft = [];
let mergeSelectedGameIds = [];
let adjacentDevicesDraft = [];
let installBusyState = null;
let qrPreviewVisible = false;
const deviceCommandDrafts = { panel: "", motion: "", "adjacent:1": "", "adjacent:2": "", "adjacent:3": "", "adjacent:4": "" };
const motionHistory = [];
const shownMessageIds = new Set();
const dialogQueue = [];
let dialogOpen = false;
let dialogResolver = null;
let aboutTemplateHtml = null;
let activeModal = null;
let pollInFlight = false;
let activeAdjacentEditorIndex = null;
let adjacentPreviewState = null;
let adjacentPreviewTimer = null;
let luaContextMenuState = null;
const MAIN_POLL_MS = 250;

// Sistema de logging com timestamp
let pollCount = 0;
let renderCount = 0;
const logWithTime = (message, data) => {
  const now = new Date().toLocaleTimeString("pt-BR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit", fractionalSecondDigits: 3 });
  console.log(`[${now}] ${message}`, data !== undefined ? data : "");
};

window.addEventListener("pywebviewready", async () => {
  bindUi();
  state = await window.pywebview.api.bootstrap();
  render();
  startPolling();
});

function startPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
  }
  scheduleNextPoll();
}

function scheduleNextPoll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    if (pollInFlight) {
      logWithTime(`[POLL #${pollCount}] BLOQUEADO: poll anterior ainda em voo`);
      scheduleNextPoll();
      return;
    }
    pollInFlight = true;
    pollCount++;
    const pollStartTime = performance.now();
    try {
      logWithTime(`[POLL #${pollCount}] Iniciando poll_state()...`);
      state = await window.pywebview.api.poll_state();
      const pollDuration = (performance.now() - pollStartTime).toFixed(1);
      logWithTime(`[POLL #${pollCount}] poll_state() retornou em ${pollDuration}ms, chamando render()...`);
      
      const renderStartTime = performance.now();
      render();
      const renderDuration = (performance.now() - renderStartTime).toFixed(1);
      logWithTime(`[POLL #${pollCount}] render() concluído em ${renderDuration}ms (poll total: ${(performance.now() - pollStartTime).toFixed(1)}ms)`);
    } catch (error) {
      logWithTime(`[POLL #${pollCount}] ERRO em poll_state():`, error);
    } finally {
      pollInFlight = false;
      scheduleNextPoll();
    }
  }, MAIN_POLL_MS);
}

function bindUi() {
  ui.gamesList = document.getElementById("gamesList");
  ui.gameLogo = document.getElementById("gameLogo");
  ui.gameTitle = document.getElementById("gameTitle");
  ui.gameState = document.getElementById("gameState");
  ui.mainActionBtn = document.getElementById("mainActionBtn");
  ui.mainActionBtnLabel = ui.mainActionBtn.querySelector("span");
  ui.mainActionBtnIcon = ui.mainActionBtn.querySelector("i");
  ui.autoStartToggle = document.getElementById("autoStartToggle");
  ui.telemetryList = document.getElementById("telemetryList");
  ui.overlay = document.getElementById("overlay");
  ui.panelConfigBtn = document.getElementById("panelConfigBtn");
  ui.motionConfigBtn = document.getElementById("motionConfigBtn");

  ui.panelModal = document.getElementById("panelModal");
  ui.motionModal = document.getElementById("motionModal");
  ui.installModal = document.getElementById("installModal");
  ui.basicSettingsModal = document.getElementById("basicSettingsModal");
  ui.webServerModal = document.getElementById("webServerModal");
  ui.luaEditorModal = document.getElementById("luaEditorModal");
  ui.dialogModal = document.getElementById("dialogModal");
  ui.githubPluginModal = document.getElementById("githubPluginModal");

  ui.panelMode = document.getElementById("panelMode");
  ui.panelPort = document.getElementById("panelPort");
  ui.panelBaudrate = document.getElementById("panelBaudrate");
  ui.panelFps = document.getElementById("panelFps");
  ui.panelAppendNewline = document.getElementById("panelAppendNewline");
  ui.panelSlots = document.getElementById("panelSlots");
  ui.motionMode = document.getElementById("motionMode");
  ui.motionPort = document.getElementById("motionPort");
  ui.motionBaudrate = document.getElementById("motionBaudrate");
  ui.motionFps = document.getElementById("motionFps");
  ui.motionAppendNewline = document.getElementById("motionAppendNewline");
  ui.motionMin = document.getElementById("motionMin");
  ui.motionMax = document.getElementById("motionMax");
  ui.motionPhaseX = document.getElementById("motionPhaseX");
  ui.motionPhaseY = document.getElementById("motionPhaseY");
  ui.motionPhaseZ = document.getElementById("motionPhaseZ");
  ui.motionEnableX = document.getElementById("motionEnableX");
  ui.motionEnableY = document.getElementById("motionEnableY");
  ui.motionEnableZ = document.getElementById("motionEnableZ");
  ui.motionOffsetX = document.getElementById("motionOffsetX");
  ui.motionOffsetY = document.getElementById("motionOffsetY");
  ui.motionOffsetZ = document.getElementById("motionOffsetZ");
  ui.motionOffsetXValue = document.getElementById("motionOffsetXValue");
  ui.motionOffsetYValue = document.getElementById("motionOffsetYValue");
  ui.motionOffsetZValue = document.getElementById("motionOffsetZValue");
  ui.motionPreviewCanvas = document.getElementById("motionPreviewCanvas");
  ui.motionPreviewValues = document.getElementById("motionPreviewValues");

  ui.installTitle = document.getElementById("installTitle");
  ui.installGameName = document.getElementById("installGameName");
  ui.installDescription = document.getElementById("installDescription");
  ui.installStatusBadge = document.getElementById("installStatusBadge");
  ui.installFolder = document.getElementById("installFolder");
  ui.installControlsBlock = document.getElementById("installControlsBlock");
  ui.installFolderActions = document.getElementById("installFolderActions");
  ui.installMainActions = document.getElementById("installMainActions");
  ui.installBusyIndicator = document.getElementById("installBusyIndicator");
  ui.installBusyText = document.getElementById("installBusyText");
  ui.installTutorialTitle = document.getElementById("installTutorialTitle");
  ui.installTutorialSummary = document.getElementById("installTutorialSummary");
  ui.installTutorialSteps = document.getElementById("installTutorialSteps");
  ui.installTutorialNotes = document.getElementById("installTutorialNotes");
  ui.removeInstallBtn = document.getElementById("removeInstallBtn");

  ui.speedUnit = document.getElementById("speedUnit");
  ui.pressureUnit = document.getElementById("pressureUnit");
  ui.temperatureUnit = document.getElementById("temperatureUnit");
  ui.launchWithWindows = document.getElementById("launchWithWindows");
  ui.detectOpenGameOnStart = document.getElementById("detectOpenGameOnStart");
  ui.applyGameUnitsBtn = document.getElementById("applyGameUnitsBtn");
  ui.selectedGameUnitsHint = document.getElementById("selectedGameUnitsHint");
  ui.fallbackField = document.getElementById("fallbackField");
  ui.fallbackValue = document.getElementById("fallbackValue");
  ui.addFallbackBtn = document.getElementById("addFallbackBtn");
  ui.clearFallbackValueBtn = document.getElementById("clearFallbackValueBtn");
  ui.fallbackList = document.getElementById("fallbackList");
  ui.equalizationField = document.getElementById("equalizationField");
  ui.equalizationSourceMin = document.getElementById("equalizationSourceMin");
  ui.equalizationSourceMax = document.getElementById("equalizationSourceMax");
  ui.equalizationTargetMin = document.getElementById("equalizationTargetMin");
  ui.equalizationTargetMax = document.getElementById("equalizationTargetMax");
  ui.equalizationApplyToAll = document.getElementById("equalizationApplyToAll");
  ui.equalizationGameList = document.getElementById("equalizationGameList");
  ui.equalizationList = document.getElementById("equalizationList");
  ui.mergeTargetField = document.getElementById("mergeTargetField");
  ui.mergeSourceField = document.getElementById("mergeSourceField");
  ui.mergeMode = document.getElementById("mergeMode");
  ui.mergeApplyToAll = document.getElementById("mergeApplyToAll");
  ui.mergeGameList = document.getElementById("mergeGameList");
  ui.mergeList = document.getElementById("mergeList");
  ui.pluginPackagePath = document.getElementById("pluginPackagePath");
  ui.pluginGithubUrl = document.getElementById("pluginGithubUrl");
  ui.pluginGithubSummary = document.getElementById("pluginGithubSummary");
  ui.pluginList = document.getElementById("pluginList");
  ui.githubReleaseList = document.getElementById("githubReleaseList");
  ui.templateZipPath = document.getElementById("templateZipPath");
  ui.templateZipSummary = document.getElementById("templateZipSummary");
  ui.settingsTemplateList = document.getElementById("settingsTemplateList");
  ui.adjacentDevicesList = document.getElementById("adjacentDevicesList");
  ui.usefulInfoList = document.getElementById("usefulInfoList");
  ui.deviceStatusList = document.getElementById("deviceStatusList");
  ui.aboutHtmlHost = document.getElementById("aboutHtmlHost");

  ui.webServerHost = document.getElementById("webServerHost");
  ui.webServerPort = document.getElementById("webServerPort");
  ui.webServerAutoStart = document.getElementById("webServerAutoStart");
  ui.webServerUrl = document.getElementById("webServerUrl");
  ui.networkIpLabel = document.getElementById("networkIpLabel");
  ui.webServerStatusChip = document.getElementById("webServerStatusChip");
  ui.webServerEnabled = document.getElementById("webServerEnabled");
  ui.toggleQrPreviewBtn = document.getElementById("toggleQrPreviewBtn");
  ui.qrPreviewWrap = document.getElementById("qrPreviewWrap");
  ui.qrPreviewImage = document.getElementById("qrPreviewImage");
  ui.activeTemplateLabel = document.getElementById("activeTemplateLabel");
  ui.udpServerHost = document.getElementById("udpServerHost");
  ui.udpServerPort = document.getElementById("udpServerPort");
  ui.udpServerAutoStart = document.getElementById("udpServerAutoStart");
  ui.udpServerStatusChip = document.getElementById("udpServerStatusChip");
  ui.udpServerEnabled = document.getElementById("udpServerEnabled");
  ui.udpPacketCount = document.getElementById("udpPacketCount");
  ui.udpMessageList = document.getElementById("udpMessageList");
  ui.telemetryShareStatusChip = document.getElementById("telemetryShareStatusChip");
  ui.telemetryShareName = document.getElementById("telemetryShareName");
  ui.telemetryShareUpdatedAt = document.getElementById("telemetryShareUpdatedAt");
  ui.telemetryShareBytes = document.getElementById("telemetryShareBytes");
  ui.telemetryShareMaxSize = document.getElementById("telemetryShareMaxSize");
  ui.telemetryShareHelp = document.getElementById("telemetryShareHelp");

  ui.luaEditorTitle = document.getElementById("luaEditorTitle");
  ui.luaEditorBackBtn = document.getElementById("luaEditorBackBtn");
  ui.luaEditorPreset = document.getElementById("luaEditorPreset");
  ui.luaEditorLoadPresetBtn = document.getElementById("luaEditorLoadPresetBtn");
  ui.luaEditorRefreshPreviewBtn = document.getElementById("luaEditorRefreshPreviewBtn");
  ui.luaEditorScript = document.getElementById("luaEditorScript");
  ui.luaEditorSlotBadge = document.getElementById("luaEditorSlotBadge");
  ui.luaEditorTelemetrySourceBadge = document.getElementById("luaEditorTelemetrySourceBadge");
  ui.luaPreviewStatusChip = document.getElementById("luaPreviewStatusChip");
  ui.luaPreviewHeading = document.getElementById("luaPreviewHeading");
  ui.luaPreviewSummary = document.getElementById("luaPreviewSummary");
  ui.luaPreviewOutput = document.getElementById("luaPreviewOutput");
  ui.luaPreviewErrorWrap = document.getElementById("luaPreviewErrorWrap");
  ui.luaPreviewError = document.getElementById("luaPreviewError");
  ui.luaPreviewTelemetry = document.getElementById("luaPreviewTelemetry");
  ui.luaEditorContextMenu = document.getElementById("luaEditorContextMenu");
  ui.luaContextVariables = document.getElementById("luaContextVariables");

  ui.dialogTitle = document.getElementById("dialogTitle");
  ui.dialogText = document.getElementById("dialogText");
  ui.dialogCancelBtn = document.getElementById("dialogCancelBtn");
  ui.dialogConfirmBtn = document.getElementById("dialogConfirmBtn");

  ui.settingsTabs = [...document.querySelectorAll("[data-settings-tab]")];
  ui.settingsPanes = {
    general: document.getElementById("settingsPaneGeneral"),
    fallbacks: document.getElementById("settingsPaneFallbacks"),
    equalization: document.getElementById("settingsPaneEqualization"),
    merge: document.getElementById("settingsPaneMerge"),
    plugins: document.getElementById("settingsPanePlugins"),
    useful: document.getElementById("settingsPaneUseful"),
    templates: document.getElementById("settingsPaneTemplates"),
    adjacent: document.getElementById("settingsPaneAdjacent"),
    devices: document.getElementById("settingsPaneDevices"),
    about: document.getElementById("settingsPaneAbout"),
  };

  [ui.motionOffsetX, ui.motionOffsetY, ui.motionOffsetZ].forEach((slider) => {
    slider.addEventListener("input", renderMotionOffsetLabels);
  });

  ui.mainActionBtn.addEventListener("click", handleMainAction);
  document.getElementById("panelConfigBtn").addEventListener("click", () => openModal("panel"));
  document.getElementById("motionConfigBtn").addEventListener("click", () => openModal("motion"));
  document.getElementById("installBtn").addEventListener("click", () => openModal("install"));
  document.getElementById("basicSettingsBtn").addEventListener("click", () => openModal("basic"));
  document.getElementById("webServerBtn").addEventListener("click", () => openModal("webServer"));

  document.getElementById("savePanelBtn").addEventListener("click", savePanelConfig);
  document.getElementById("saveMotionBtn").addEventListener("click", saveMotionConfig);
  document.getElementById("exportPanelConfigBtn").addEventListener("click", exportPanelConfig);
  document.getElementById("importPanelConfigBtn").addEventListener("click", importPanelConfig);
  document.getElementById("saveBasicSettingsBtn").addEventListener("click", saveBasicSettings);
  document.getElementById("saveWebServerBtn").addEventListener("click", saveWebServerConfig);

  document.getElementById("browsePluginPackageBtn").addEventListener("click", async () => {
    state = await window.pywebview.api.browse_plugin_package();
    render();
  });
  document.getElementById("importPluginPackageBtn").addEventListener("click", async () => {
    if (!state.plugin_manager.selected_package) {
      await showDialog({ title: "Plugin de jogo", text: "Selecione um ISO ou ZIP antes de importar." });
      return;
    }
    state = await window.pywebview.api.import_plugin_package();
    render();
  });
  document.getElementById("browseTemplateZipBtn").addEventListener("click", async () => {
    state = await window.pywebview.api.browse_web_bundle_zip();
    render();
  });
  document.getElementById("importTemplateZipBtn").addEventListener("click", async () => {
    if (!state.template_manager.selected_package) {
      await showDialog({ title: "Template HTML", text: "Selecione um arquivo ZIP antes de importar." });
      return;
    }
    state = await window.pywebview.api.import_web_bundle_zip();
    render();
  });
  document.getElementById("openGithubPluginModalBtn").addEventListener("click", () => openModal("githubPlugin"));
  document.getElementById("loadGithubReleasesBtn").addEventListener("click", async () => {
    state = await window.pywebview.api.set_plugin_github_url(ui.pluginGithubUrl.value || "");
    state = await window.pywebview.api.fetch_plugin_github_releases();
    render();
  });
  document.getElementById("clearGithubReleasesBtn").addEventListener("click", async () => {
    state = await window.pywebview.api.clear_plugin_github_releases();
    render();
  });

  document.getElementById("autoSearchInstallBtn").addEventListener("click", async () => {
    setInstallBusy("Buscando instalacao automaticamente...");
    state = await window.pywebview.api.auto_install_search();
    clearInstallBusy();
    render();
  });
  document.getElementById("browseInstallBtn").addEventListener("click", async () => {
    setInstallBusy("Abrindo seletor de pasta...");
    state = await window.pywebview.api.browse_install_folder();
    clearInstallBusy();
    render();
  });
  document.getElementById("confirmInstallBtn").addEventListener("click", installSelectedGame);
  ui.removeInstallBtn.addEventListener("click", uninstallSelectedGame);

  ui.autoStartToggle.addEventListener("change", async () => {
    state = await window.pywebview.api.set_auto_start(ui.autoStartToggle.checked);
    render();
  });
  ui.applyGameUnitsBtn.addEventListener("click", async () => {
    state = await window.pywebview.api.apply_selected_game_unit_defaults();
    render();
  });
  ui.addFallbackBtn.addEventListener("click", addOrUpdateFallbackOverride);
  ui.clearFallbackValueBtn.addEventListener("click", () => {
    ui.fallbackValue.value = "";
  });
  document.getElementById("addEqualizationBtn").addEventListener("click", addOrUpdateEqualizationRule);
  document.getElementById("clearEqualizationFormBtn").addEventListener("click", clearEqualizationForm);
  ui.equalizationApplyToAll.addEventListener("change", renderEqualizationGameSelector);
  document.getElementById("addMergeRuleBtn").addEventListener("click", addOrUpdateMergeRule);
  document.getElementById("clearMergeFormBtn").addEventListener("click", clearMergeForm);
  ui.mergeApplyToAll.addEventListener("change", renderMergeGameSelector);
  ui.webServerEnabled.addEventListener("change", toggleWebServer);
  ui.udpServerEnabled.addEventListener("change", toggleUdpServer);
  ui.toggleQrPreviewBtn.addEventListener("click", () => {
    qrPreviewVisible = !qrPreviewVisible;
    renderWebServerConfig();
  });
  ui.luaEditorLoadPresetBtn.addEventListener("click", loadActiveAdjacentPreset);
  ui.luaEditorBackBtn.addEventListener("click", (event) => {
    event.preventDefault();
    closeModals();
    activeSettingsTab = "adjacent";
    openModal("basic");
  });
  ui.luaEditorRefreshPreviewBtn.addEventListener("click", () => requestAdjacentPreview(true));
  ui.luaEditorPreset.addEventListener("change", () => {
    if (activeAdjacentEditorIndex == null || !adjacentDevicesDraft[activeAdjacentEditorIndex]) {
      return;
    }
    adjacentDevicesDraft[activeAdjacentEditorIndex].preset_id = ui.luaEditorPreset.value || "custom";
    renderAdjacentDevices();
  });
  ui.luaEditorScript.addEventListener("input", () => {
    syncActiveAdjacentScript();
    requestAdjacentPreview(false);
  });
  ui.luaEditorScript.addEventListener("contextmenu", openLuaContextMenu);
  document.addEventListener("click", hideLuaContextMenu);
  document.addEventListener("scroll", (event) => {
    if (ui.luaEditorContextMenu?.contains(event.target)) {
      return;
    }
    hideLuaContextMenu();
  }, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideLuaContextMenu();
    }
  });
  ui.luaEditorContextMenu.querySelectorAll("[data-lua-helper]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      insertLuaHelper(button.dataset.luaHelper || "");
    });
  });

  document.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", closeModals);
  });
  ui.overlay.addEventListener("click", closeModals);
  ui.settingsTabs.forEach((button) => {
    button.addEventListener("click", () => setSettingsTab(button.dataset.settingsTab));
  });

  ui.dialogConfirmBtn.addEventListener("click", () => resolveDialog(true));
  ui.dialogCancelBtn.addEventListener("click", () => resolveDialog(false));

  bindExternalLinks(document);
}

function render() {
  if (!state) {
    return;
  }
  renderCount++;
  logWithTime(`[RENDER #${renderCount}] Renderização iniciada`);
  renderGames();
  renderSelectedGame();
  renderTelemetry();
  const isEditing = isEditingConfigModal();
  logWithTime(`[RENDER #${renderCount}] isEditingConfigModal?:`, isEditing);
  if (!isEditing) {
    logWithTime(`[RENDER #${renderCount}] Chamando renderConfigs() (renderDeviceStatuses será incluído)`);
    renderConfigs();
  } else {
    logWithTime(`[RENDER #${renderCount}] Modo edição, chamando renderLiveSettingsPanels()`);
    renderLiveSettingsPanels();
  }
  renderInstallModal();
  renderMotionPreview();
  renderWebServerConfig();
  renderAdjacentEditorModal();
  renderAboutPane();
  drainMessages();
  logWithTime(`[RENDER #${renderCount}] Renderização concluída`);
}

function renderGames() {
  ui.gamesList.innerHTML = "";
  state.games.forEach((game) => {
    const button = document.createElement("button");
    const lockedByCollection = state.is_collecting && !game.selected;
    button.className = `game-item ${game.selected ? "selected" : ""} ${lockedByCollection ? "is-disabled" : ""}`;
    button.innerHTML = `
      <img src="../${game.icon}" alt="">
      <div>
        <strong>${game.name}</strong>
        <span>${game.installed === "yes" ? "instalado" : "precisa de integracao"} | ${game.is_active_process ? "aberto" : "fechado"}</span>
      </div>
    `;
    button.addEventListener("click", async () => {
      if (state.is_collecting && !game.selected) {
        await showDialog({ title: "Troca de jogo", text: "Pare a leitura atual antes de trocar de jogo." });
        return;
      }
      state = await window.pywebview.api.select_game(game.name);
      render();
    });
    ui.gamesList.appendChild(button);
  });
}

function renderSelectedGame() {
  const selected = getSelectedGame();
  if (!selected) {
    return;
  }
  ui.gameLogo.src = `../${selected.icon}`;
  ui.gameTitle.textContent = selected.name;
  ui.gameState.textContent = state.status_text;
  ui.autoStartToggle.checked = state.footer.auto_start_enabled;
  ui.panelConfigBtn.classList.toggle("is-live", state.device_status?.panel?.state === "sending");
  ui.motionConfigBtn.classList.toggle("is-live", state.device_status?.motion?.state === "sending");

  if (state.is_collecting) {
    ui.mainActionBtnLabel.textContent = "Parar";
    ui.mainActionBtnIcon.className = "bi bi-stop-fill";
  } else if (selected.installed === "no") {
    ui.mainActionBtnLabel.textContent = "Instalar";
    ui.mainActionBtnIcon.className = "bi bi-download";
  } else {
    ui.mainActionBtnLabel.textContent = "Iniciar";
    ui.mainActionBtnIcon.className = "bi bi-play-fill";
  }
}

function renderTelemetry() {
  ui.telemetryList.innerHTML = "";
  state.telemetry_rows.forEach((row) => {
    const item = document.createElement("div");
    item.className = "telemetry-row";
    item.innerHTML = `<span class="telemetry-label">${row.label}</span><span class="telemetry-value">${row.value}</span>`;
    ui.telemetryList.appendChild(item);
  });
}

function renderConfigs() {
  renderConfigInputs();
  renderLiveSettingsPanels();
}

function renderConfigInputs() {
  const ports = ['<option value="">Selecione...</option>']
    .concat(state.available_ports.map((port) => `<option value="${port}">${port}</option>`))
    .join("");

  ui.panelMode.innerHTML = '<option value="Disabled">Desligado</option><option value="Automatic">Automatico</option><option value="Manual">Manual</option>';
  ui.motionMode.innerHTML = '<option value="Disabled">Desligado</option><option value="Automatic">Automatico</option><option value="Manual">Manual</option>';
  ui.panelPort.innerHTML = ports;
  ui.motionPort.innerHTML = ports;
  ui.panelMode.value = state.panel_config.mode;
  ui.panelPort.value = state.panel_config.port || "";
  ui.panelBaudrate.value = state.panel_config.baudrate || 115200;
  ui.panelFps.value = state.panel_config.fps || 20;
  ui.panelAppendNewline.checked = !!state.panel_config.append_newline;
  ui.motionMode.value = state.motion_config.mode || "Disabled";
  ui.motionPort.value = state.motion_config.port || "";
  ui.motionBaudrate.value = state.motion_config.baudrate;
  ui.motionFps.value = state.motion_config.fps || 20;
  ui.motionAppendNewline.checked = !!state.motion_config.append_newline;
  ui.motionMin.value = state.motion_config.min_value;
  ui.motionMax.value = state.motion_config.max_value;
  ui.motionPhaseX.checked = !!state.motion_config.phase_invert_x;
  ui.motionPhaseY.checked = !!state.motion_config.phase_invert_y;
  ui.motionPhaseZ.checked = !!state.motion_config.phase_invert_z;
  ui.motionEnableX.checked = !!state.motion_config.onoff_invert_x;
  ui.motionEnableY.checked = !!state.motion_config.onoff_invert_y;
  ui.motionEnableZ.checked = !!state.motion_config.onoff_invert_z;
  ui.motionOffsetX.value = state.motion_config.offset_power_x;
  ui.motionOffsetY.value = state.motion_config.offset_power_y;
  ui.motionOffsetZ.value = state.motion_config.offset_power_z;
  renderMotionOffsetLabels();

  ui.speedUnit.value = state.basic_settings.speed_unit;
  ui.pressureUnit.value = state.basic_settings.pressure_unit;
  ui.temperatureUnit.value = state.basic_settings.temperature_unit;
  ui.launchWithWindows.checked = !!state.basic_settings.launch_with_windows;
  ui.detectOpenGameOnStart.checked = !!state.basic_settings.detect_open_game_on_start;
  fallbackOverridesDraft = { ...(state.basic_settings.fallback_overrides || {}) };
  equalizationRulesDraft = (state.basic_settings.value_equalization_rules || []).map((rule) => ({
    ...rule,
    game_ids: [...(rule.game_ids || [])],
  }));
  equalizationSelectedGameIds = [];
  mergeRulesDraft = (state.basic_settings.telemetry_merge_rules || []).map((rule) => ({
    ...rule,
    game_ids: [...(rule.game_ids || [])],
  }));
  mergeSelectedGameIds = [];
  adjacentDevicesDraft = (state.basic_settings.adjacent_devices || []).map((device, index) => normalizeAdjacentDeviceDraft(device, index));
  ui.pluginGithubUrl.value = state.plugin_manager.github_repo_url || "";

  ui.webServerHost.value = state.web_server.http_host || "0.0.0.0";
  ui.webServerPort.value = state.web_server.http_port || 8080;
  ui.webServerAutoStart.checked = !!state.web_server.http_auto_start;
  ui.webServerEnabled.checked = !!state.web_server.http_enabled;
  ui.udpServerHost.value = state.web_server.udp_host || "0.0.0.0";
  ui.udpServerPort.value = state.web_server.udp_port || 28000;
  ui.udpServerAutoStart.checked = !!state.web_server.udp_auto_start;
  ui.udpServerEnabled.checked = !!state.web_server.udp_enabled;

  renderPanelSlots();
  renderFallbackEditor();
  renderFallbackList();
  renderEqualizationEditor();
  clearEqualizationForm();
  renderEqualizationList();
  renderMergeEditor();
  clearMergeForm();
  renderMergeList();
  renderAdjacentDevices();
  renderSelectedGameUnitHint();
  renderUsefulInfoList();
  setSettingsTab(activeSettingsTab);
}

function renderLiveSettingsPanels() {
  ui.pluginPackagePath.value = state.plugin_manager.selected_package || "";
  ui.templateZipPath.value = state.template_manager.selected_package || "";
  renderPluginManager();
  renderTemplateCatalog();
  renderDeviceStatuses();
  renderSelectedGameUnitHint();
}

function renderPanelSlots() {
  // Preservar valores atuais antes de renderizar
  const currentValues = {};
  ui.panelSlots.querySelectorAll("select").forEach((select, index) => {
    currentValues[index] = select.value;
  });
  
  ui.panelSlots.innerHTML = "";
  state.panel_config.order.forEach((value, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "slot-item";
    wrapper.innerHTML = `<label class="form-label">Slot ${index + 1}</label>`;
    const select = document.createElement("select");
    select.className = "form-select";
    state.panel_fields.forEach((field) => {
      const option = document.createElement("option");
      option.value = field.key;
      option.textContent = field.label;
      // Usar valor preservado se existir, senão usar o padrão
      const selectedValue = currentValues[index] !== undefined ? currentValues[index] : value;
      option.selected = field.key === selectedValue;
      select.appendChild(option);
    });
    wrapper.appendChild(select);
    ui.panelSlots.appendChild(wrapper);
  });
}

function renderInstallModal() {
  const plugin = state.install_modal.plugin;
  const installed = !!state.install_modal.installed;
  const requiresInstall = !!plugin.requires_install;
  const installer = plugin.installer || {};
  const installMethod = installer.method || (requiresInstall ? "folder_required" : "tutorial_only");
  const tutorial = plugin.setup_tutorial || {};
  const defaultDescription = installMethod === "folder_required"
    ? `${plugin.name} usa integracao externa e precisa da pasta correta do jogo.`
    : `${plugin.name} nao usa selecao de pasta neste plugin. Veja somente as instrucoes abaixo.`;
  const installDescription = installer.description || tutorial.summary || defaultDescription;

  ui.installTitle.textContent = installer.title || `Integracao ${plugin.name}`;
  ui.installGameName.textContent = plugin.name;
  ui.installDescription.textContent = installDescription;
  ui.installStatusBadge.textContent = installed ? "Instalado" : requiresInstall ? "Pendente" : "Pronto";
  ui.installFolder.value = state.install_modal.selected_folder || "";
  ui.installBusyIndicator.classList.toggle("hidden", !installBusyState);
  ui.installBusyText.textContent = installBusyState || "";

  const needsFolder = installMethod === "folder_required";
  const showInstallButtons = installMethod === "folder_required";
  const canAutoSearch = installer.allow_auto_search !== false;
  const canManualSelect = installer.allow_manual_select !== false;
  const showFolderActions = needsFolder && (canAutoSearch || canManualSelect);
  ui.installControlsBlock.classList.toggle("hidden", !needsFolder && !showInstallButtons);
  ui.installFolder.classList.toggle("hidden", !needsFolder);
  ui.installFolder.previousElementSibling.classList.toggle("hidden", !needsFolder);
  ui.installFolderActions.classList.toggle("hidden", !showFolderActions);
  document.getElementById("autoSearchInstallBtn").classList.toggle("hidden", !canAutoSearch);
  document.getElementById("browseInstallBtn").classList.toggle("hidden", !canManualSelect);
  ui.installMainActions.classList.toggle("hidden", !showInstallButtons);
  ui.removeInstallBtn.classList.toggle("hidden", !showInstallButtons || !installed);
  ui.removeInstallBtn.disabled = !installed;

  ui.installTutorialTitle.textContent = tutorial.title || "Passo a passo";
  ui.installTutorialSummary.textContent = tutorial.summary || "Sem tutorial especifico para este jogo.";
  ui.installTutorialSteps.innerHTML = "";
  (tutorial.steps || []).forEach((step, index) => {
    const item = document.createElement("div");
    item.className = "tutorial-step";
    item.textContent = `${index + 1}. ${step}`;
    ui.installTutorialSteps.appendChild(item);
  });
  if (!ui.installTutorialSteps.children.length) {
    const empty = document.createElement("div");
    empty.className = "tutorial-step";
    empty.textContent = "1. Selecione o jogo, abra-o e inicie a coleta quando a telemetria estiver pronta.";
    ui.installTutorialSteps.appendChild(empty);
  }

  ui.installTutorialNotes.innerHTML = "";
  (tutorial.notes || []).forEach((note) => {
    const item = document.createElement("div");
    item.className = "tutorial-note";
    item.textContent = note;
    ui.installTutorialNotes.appendChild(item);
  });
}

function renderPluginManager() {
  ui.pluginList.innerHTML = "";
  ui.pluginGithubSummary.textContent = state.plugin_manager.selected_package
    ? `ZIP/ISO selecionado: ${basename(state.plugin_manager.selected_package)}`
    : "Você pode importar um pacote local ou buscar releases direto do GitHub.";
  state.plugin_manager.plugins.forEach((plugin) => {
    const item = document.createElement("div");
    const selected = state.selected_game === plugin.name;
    item.className = `plugin-item ${selected ? "is-selected" : ""}`;
    item.innerHTML = `
      <div class="plugin-meta">
        <strong>${plugin.name}</strong>
        <span>${plugin.built_in ? "plugin nativo" : "plugin importado"} | ${plugin.requires_install ? "com instalador" : "sem instalador"} | ${selected ? "selecionado" : "disponivel"}</span>
      </div>
    `;
    const button = document.createElement("button");
    button.className = plugin.built_in ? "btn btn-outline-light" : "btn btn-danger";
    button.textContent = plugin.built_in ? "Protegido" : "Excluir";
    button.disabled = plugin.built_in;
    if (!plugin.built_in) {
      button.addEventListener("click", async () => {
        const confirmed = await showDialog({
          title: "Excluir plugin",
          text: `Deseja excluir o plugin ${plugin.name}?`,
          confirmLabel: "Excluir",
          cancelLabel: "Cancelar",
        });
        if (!confirmed) {
          return;
        }
        state = await window.pywebview.api.remove_plugin(plugin.id);
        render();
      });
    }
    item.appendChild(button);
    ui.pluginList.appendChild(item);
  });
  renderGithubReleaseCatalog();
}

function renderTemplateCatalog() {
  ui.settingsTemplateList.innerHTML = "";
  ui.templateZipSummary.textContent = state.template_manager.selected_package
    ? `ZIP selecionado: ${basename(state.template_manager.selected_package)}`
    : "Selecione um ZIP para importar um novo painel HTML.";
  const templates = state.web_server.templates || [];
  if (!templates.length) {
    const empty = document.createElement("div");
    empty.className = "fallback-item";
    empty.innerHTML = `<div><strong>Nenhum template encontrado</strong><span>Importe um ZIP para adicionar novos layouts HTML.</span></div>`;
    ui.settingsTemplateList.appendChild(empty);
    return;
  }

  templates.forEach((template) => {
    const card = document.createElement("div");
    card.className = `template-card ${state.web_server.selected_template === template.id ? "is-active" : ""}`;
    const websiteMarkup = template.website_url
      ? `<a href="${template.website_url}" target="_blank" rel="noreferrer">${template.website_label}</a>`
      : "";
    card.innerHTML = `
      <div class="template-card-head">
        ${template.preview_uri ? `<img class="template-preview" src="${template.preview_uri}" alt="">` : `<div class="template-preview-fallback"><i class="bi bi-phone"></i></div>`}
        <div class="template-title-block">
          <strong>${template.name}</strong>
          <span>${template.author} | v${template.version}</span>
          <span>${template.supports_mobile ? "Pronto para celular" : "Uso geral"} | ${state.web_server.selected_template === template.id ? "Selecionado" : "Disponivel"}</span>
        </div>
      </div>
      <div class="template-meta">
        <p>${template.description}</p>
        ${websiteMarkup}
      </div>
    `;
    const actions = document.createElement("div");
    actions.className = "template-actions";

    const activateButton = document.createElement("button");
    activateButton.className = "btn btn-outline-light";
    activateButton.textContent = state.web_server.selected_template === template.id ? "Selecionado" : "Ativar";
    activateButton.addEventListener("click", async () => {
      if (state.web_server.http_enabled && state.web_server.selected_template !== template.id) {
        await showDialog({
          title: "Servidor web ligado",
          text: "Servidor ligado, desligue para depois alterar o template HTML.",
        });
        return;
      }
      state = await window.pywebview.api.save_web_server_config({ selected_template: template.id });
      render();
    });
    actions.appendChild(activateButton);

    if (template.can_delete) {
      const deleteButton = document.createElement("button");
      deleteButton.className = "btn btn-danger";
        deleteButton.textContent = "Excluir";
        deleteButton.addEventListener("click", async () => {
          if (state.web_server.http_enabled) {
            await showDialog({
              title: "Servidor web ligado",
              text: "Servidor ligado, desligue para depois alterar os templates HTML.",
            });
            return;
          }
          const confirmed = await showDialog({
            title: "Excluir template",
            text: `Deseja excluir o template ${template.name}?`,
          confirmLabel: "Excluir",
          cancelLabel: "Cancelar",
        });
        if (!confirmed) {
          return;
        }
        state = await window.pywebview.api.delete_template(template.id);
        render();
      });
      actions.appendChild(deleteButton);
    }

    card.appendChild(actions);
    ui.settingsTemplateList.appendChild(card);
  });
}

function renderGithubReleaseCatalog() {
  ui.githubReleaseList.innerHTML = "";
  const releaseData = state.plugin_manager.github_release_data || {};
  const releases = releaseData.releases || [];
  if (!releases.length) {
    const empty = document.createElement("div");
    empty.className = "fallback-item";
    empty.innerHTML = `<div><strong>Nenhuma release carregada</strong><span>Informe um repositório do GitHub para listar binários e pacotes.</span></div>`;
    ui.githubReleaseList.appendChild(empty);
    return;
  }

  ui.pluginGithubSummary.textContent = `${releaseData.repo_name} | ${releases.length} release(s) carregadas`;
  releases.forEach((release) => {
    const card = document.createElement("div");
    card.className = "release-card";
    const bodyPreview = (release.body || "").trim().split("\n").filter(Boolean).slice(0, 3).join(" ");
    card.innerHTML = `
      <div class="release-head">
        <div>
          <strong>${release.name}</strong>
          <span>${release.tag_name || "sem tag"} | ${formatDateLabel(release.published_at)}${release.prerelease ? " | prerelease" : ""}</span>
        </div>
        <a href="${release.html_url}" data-external-url="${release.html_url}" class="btn btn-outline-light btn-sm">Abrir release</a>
      </div>
      <p class="form-help">${bodyPreview || "Sem descrição resumida nesta release."}</p>
    `;
    const assetList = document.createElement("div");
    assetList.className = "release-assets";

    if (!release.assets.length) {
      const emptyAsset = document.createElement("div");
      emptyAsset.className = "fallback-item";
      emptyAsset.innerHTML = `<div><strong>Sem binários anexados</strong><span>Esta release não trouxe assets para download.</span></div>`;
      assetList.appendChild(emptyAsset);
    }

    release.assets.forEach((asset) => {
      const item = document.createElement("div");
      item.className = "release-asset-item";
      item.innerHTML = `
        <div>
          <strong>${asset.name}</strong>
          <span>${formatBytes(asset.size)} | ${asset.download_count} download(s) | ${asset.is_zip ? "ZIP" : asset.content_type || "arquivo"}</span>
        </div>
      `;
      const actions = document.createElement("div");
      actions.className = "template-actions";
      actions.appendChild(createReleaseActionButton("Baixar", asset, "download"));
      if (asset.is_zip) {
        actions.appendChild(createReleaseActionButton("Extrair", asset, "extract"));
        actions.appendChild(createReleaseActionButton("Baixar e importar", asset, "import", "btn btn-danger"));
      }
      item.appendChild(actions);
      assetList.appendChild(item);
    });

    card.appendChild(assetList);
    ui.githubReleaseList.appendChild(card);
  });

  bindExternalLinks(ui.githubReleaseList);
}

function createReleaseActionButton(label, asset, action, className = "btn btn-outline-light") {
  const button = document.createElement("button");
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", async () => {
    state = await window.pywebview.api.download_plugin_release_asset(asset.download_url, asset.name, action);
    if (action === "import") {
      closeModals();
    }
    render();
  });
  return button;
}

function renderDeviceStatuses() {
  const activeElement = document.activeElement;
  const isFocusedInDeviceList = activeElement?.closest?.("#deviceStatusList") === ui.deviceStatusList;
  
  if (isFocusedInDeviceList) {
    return;
  }
  
  const focusedKind = document.activeElement?.dataset?.commandKind;
  const currentDrafts = { ...deviceCommandDrafts };
  
  ui.deviceStatusList.innerHTML = "";
  const devices = [
    state.device_status?.panel,
    state.device_status?.motion,
    ...((state.device_status?.adjacent || [])),
  ].filter(Boolean);
  if (!devices.length) {
    return;
  }
  
  devices.forEach((device) => {
    const item = document.createElement("div");
    item.className = "device-status-card";
    item.innerHTML = `
      <div class="device-status-head">
        <strong>${device.label}</strong>
        <span class="telemetry-chip">${formatDeviceState(device.state)}</span>
      </div>
      <div class="device-status-meta">
        <span>Porta: ${device.port || "nao configurada"}</span>
        <span>Modo: ${formatSerialMode(device.mode)}</span>
        <span>Baudrate: ${device.baudrate || "-"}</span>
        <span>Pacotes enviados: ${device.packets_sent || 0}</span>
        <span>Ultimo OK: ${device.last_success_at || "-"}</span>
        <span>Ultimo erro: ${device.last_error_at || "-"}</span>
      </div>
      <p class="form-help">${device.message}</p>
    `;
    if (device.connected && device.kind) {
      const commandRow = document.createElement("div");
      commandRow.className = "device-command-row";
      const input = document.createElement("input");
      input.className = "form-control";
      input.type = "text";
      input.placeholder = device.kind === "panel" ? "/help ou /comando 10" : "x,y,z ou comando ASCII";
      input.autocomplete = "off";
      input.spellcheck = false;
      input.dataset.commandKind = device.kind;
      input.value = currentDrafts[device.kind] || "";

      const helper = document.createElement("p");
      helper.className = "form-help device-command-help";
      helper.textContent =
        device.kind === "panel"
          ? "Use comandos ASCII simples. O app envia CSV e linha final no mesmo protocolo do painel."
          : "Use somente caracteres ASCII simples. Para testes rápidos, envie valores CSV ou comandos do seu firmware.";
      
      input.addEventListener("input", () => {
        deviceCommandDrafts[device.kind] = input.value;
      });
      input.addEventListener("keydown", async (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          await sendDeviceCommand(device.kind, input.value);
        }
      });
      const button = document.createElement("button");
      button.className = "btn btn-outline-light";
      button.textContent = "Enviar";
      button.addEventListener("click", async () => sendDeviceCommand(device.kind, input.value));
      commandRow.appendChild(input);
      commandRow.appendChild(button);
      item.appendChild(commandRow);
      item.appendChild(helper);
      
      if (focusedKind === device.kind) {
        setTimeout(() => {
          input.focus();
        }, 0);
      }
    }
    ui.deviceStatusList.appendChild(item);
  });
}

function normalizeAdjacentDeviceDraft(device, index) {
  return {
    slot: Number(device?.slot || index + 1),
    enabled: !!device?.enabled,
    name: device?.name || `Dispositivo ${index + 1}`,
    port: device?.port || "",
    baudrate: Number(device?.baudrate || 115200),
    encoding: device?.encoding || "ascii",
    fps: Number(device?.fps || 20),
    append_newline: device?.append_newline !== false,
    preset_id: device?.preset_id || "custom",
    script: String(device?.script || ""),
  };
}

function getAdjacentPresetMap() {
  return Object.fromEntries((state.adjacent_device_presets || []).map((preset) => [preset.id, preset]));
}

function renderAdjacentDevices() {
  if (!ui.adjacentDevicesList) {
    return;
  }
  const statusMap = Object.fromEntries(((state.device_status?.adjacent) || []).map((item) => [item.slot, item]));
  const encodingsMarkup = (state.adjacent_device_encodings || []).map((encoding) => `<option value="${encoding.id}">${encoding.label}</option>`).join("");
  const portsMarkup = ['<option value="">Selecione...</option>']
    .concat(state.available_ports.map((port) => `<option value="${port}">${port}</option>`))
    .join("");

  ui.adjacentDevicesList.innerHTML = "";
  adjacentDevicesDraft.forEach((device, index) => {
    const slot = index + 1;
    const status = statusMap[slot] || {};
    const card = document.createElement("div");
    card.className = "adjacent-device-card";
    card.innerHTML = `
      <div class="device-status-head">
        <strong>Slot ${slot}</strong>
        <span class="telemetry-chip">${formatDeviceState(status.state || (device.enabled ? "ready" : "disabled"))}</span>
      </div>
      <div class="adjacent-compact-grid">
        <label class="form-check form-switch switch-card switch-card-wide adjacent-enable-row">
          <input class="form-check-input" type="checkbox" role="switch" data-adjacent-field="enabled" ${device.enabled ? "checked" : ""}>
          <span class="form-check-label">Ativar</span>
        </label>
        <label class="form-label">Nome</label>
        <input class="form-control" type="text" data-adjacent-field="name" value="${escapeHtml(device.name)}" maxlength="60">
        <label class="form-label">Porta serial</label>
        <select class="form-select" data-adjacent-field="port">${portsMarkup}</select>
        <label class="form-label">Serial</label>
        <input class="form-control" type="number" data-adjacent-field="baudrate" value="${device.baudrate}" min="300" max="3000000">
        <label class="form-label">Codificacao</label>
        <select class="form-select" data-adjacent-field="encoding">${encodingsMarkup}</select>
        <label class="form-label">FPS</label>
        <input class="form-control" type="number" data-adjacent-field="fps" value="${device.fps}" min="1" max="240">
        <label class="form-check form-switch switch-card switch-card-wide adjacent-enable-row">
          <input class="form-check-input" type="checkbox" role="switch" data-adjacent-field="append_newline" ${device.append_newline ? "checked" : ""}>
          <span class="form-check-label">Quebra final</span>
        </label>
      </div>
      <div class="adjacent-compact-actions">
        <button class="btn btn-danger" type="button" data-adjacent-action="open-editor">Editar Lua</button>
      </div>
      <div class="device-status-meta">
        <span>Porta: ${status.port || device.port || "nao configurada"}</span>
        <span>Serial: ${status.baudrate || device.baudrate}</span>
        <span>Pacotes enviados: ${status.packets_sent || 0}</span>
        <span>Ultimo OK: ${status.last_success_at || "-"}</span>
      </div>
      <p class="form-help">${escapeHtml(status.message || "Pronto para usar. O script deve atribuir o resultado final em exit.")}</p>
    `;

    const portSelect = card.querySelector('[data-adjacent-field="port"]');
    portSelect.value = device.port || "";
    const encodingSelect = card.querySelector('[data-adjacent-field="encoding"]');
    if (encodingSelect) {
      encodingSelect.value = device.encoding || "ascii";
    }

    card.querySelectorAll("[data-adjacent-field]").forEach((field) => {
      field.addEventListener("input", () => updateAdjacentDraft(index, field));
      field.addEventListener("change", () => updateAdjacentDraft(index, field));
    });
    card.querySelector('[data-adjacent-action="open-editor"]').addEventListener("click", () => openAdjacentEditor(index));

    ui.adjacentDevicesList.appendChild(card);
  });
}

function updateAdjacentDraft(index, field) {
  const key = field.dataset.adjacentField;
  if (!key || !adjacentDevicesDraft[index]) {
    return;
  }
  if (field.type === "checkbox") {
    adjacentDevicesDraft[index][key] = field.checked;
    return;
  }
  if (key === "baudrate" || key === "fps") {
    adjacentDevicesDraft[index][key] = Number(field.value || (key === "baudrate" ? 115200 : 20));
    return;
  }
  adjacentDevicesDraft[index][key] = field.value;
}

function insertIntoTextarea(textarea, text) {
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const current = textarea.value || "";
  textarea.value = current.slice(0, start) + text + current.slice(end);
  const nextPos = start + text.length;
  textarea.focus();
  textarea.setSelectionRange(nextPos, nextPos);
}

function renderLuaContextVariables() {
  if (!ui.luaContextVariables) {
    return;
  }
  ui.luaContextVariables.innerHTML = "";
  (state.panel_fields || []).forEach((field) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "lua-context-item";
    button.textContent = field.key;
    button.title = field.description || field.label || field.key;
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      insertIntoTextarea(ui.luaEditorScript, field.key);
      syncActiveAdjacentScript();
      requestAdjacentPreview(false);
      hideLuaContextMenu();
    });
    ui.luaContextVariables.appendChild(button);
  });
}

function openLuaContextMenu(event) {
  if (activeAdjacentEditorIndex == null || !ui.luaEditorContextMenu) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  luaContextMenuState = {
    x: Math.min(event.clientX, window.innerWidth - 336),
    y: Math.min(event.clientY, window.innerHeight - 40),
  };
  ui.luaEditorContextMenu.style.left = `${Math.max(12, luaContextMenuState.x)}px`;
  ui.luaEditorContextMenu.style.top = `${Math.max(12, luaContextMenuState.y)}px`;
  ui.luaEditorContextMenu.classList.remove("hidden");
}

function hideLuaContextMenu() {
  luaContextMenuState = null;
  if (ui.luaEditorContextMenu) {
    ui.luaEditorContextMenu.classList.add("hidden");
  }
}

function insertLuaHelper(helperId) {
  const snippets = {
    clamp: "clamp(valor, 0, 100)",
    map_range: "map_range(valor, 0, 100, 0, 255)",
    bool_num: "bool_num(condicao)",
    round: "round(valor)",
    block: "exit = \"\"\n\n-- monte a saida final aqui\nexit = tostring(speed or 0)\n",
  };
  const snippet = snippets[helperId];
  if (!snippet) {
    return;
  }
  insertIntoTextarea(ui.luaEditorScript, snippet);
  syncActiveAdjacentScript();
  requestAdjacentPreview(false);
  hideLuaContextMenu();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function openAdjacentEditor(index) {
  activeAdjacentEditorIndex = index;
  adjacentPreviewState = null;
  hideLuaContextMenu();
  activeModal = "luaEditor";
  ui.overlay.classList.remove("hidden");
  ui.luaEditorModal.classList.remove("hidden");
  renderAdjacentEditorModal();
  requestAdjacentPreview(true);
}

function syncActiveAdjacentScript() {
  if (activeAdjacentEditorIndex == null || !adjacentDevicesDraft[activeAdjacentEditorIndex]) {
    return;
  }
  adjacentDevicesDraft[activeAdjacentEditorIndex].script = ui.luaEditorScript.value;
  renderAdjacentDevices();
}

function loadActiveAdjacentPreset() {
  if (activeAdjacentEditorIndex == null || !adjacentDevicesDraft[activeAdjacentEditorIndex]) {
    return;
  }
  const presetMap = getAdjacentPresetMap();
  const preset = presetMap[ui.luaEditorPreset.value || "custom"];
  if (!preset) {
    return;
  }
  const device = adjacentDevicesDraft[activeAdjacentEditorIndex];
  device.preset_id = preset.id;
  device.script = preset.script;
  if (!device.name || device.name.startsWith("Dispositivo")) {
    device.name = preset.name;
  }
  renderAdjacentDevices();
  renderAdjacentEditorModal();
  requestAdjacentPreview(true);
}

function renderAdjacentEditorModal() {
  if (!ui.luaEditorModal || activeAdjacentEditorIndex == null || !adjacentDevicesDraft[activeAdjacentEditorIndex]) {
    return;
  }
  const device = adjacentDevicesDraft[activeAdjacentEditorIndex];
  ui.luaEditorTitle.textContent = `${device.name || `Dispositivo ${activeAdjacentEditorIndex + 1}`}`;
  ui.luaEditorSlotBadge.textContent = `Slot ${activeAdjacentEditorIndex + 1}`;
  if (document.activeElement !== ui.luaEditorScript) {
    ui.luaEditorScript.value = device.script || "";
  }
  ui.luaEditorPreset.innerHTML = (state.adjacent_device_presets || []).map((preset) => `
    <option value="${preset.id}" ${preset.id === device.preset_id ? "selected" : ""}>${preset.name}</option>
  `).join("");
  renderLuaContextVariables();
  renderAdjacentPreview();
}

function renderAdjacentPreview() {
  if (!ui.luaPreviewStatusChip) {
    return;
  }
  const preview = adjacentPreviewState;
  const statusClass = preview?.ok ? "is-success" : (preview?.status === "compile_error" ? "is-error" : "is-warning");
  ui.luaPreviewStatusChip.className = `telemetry-chip ${statusClass}`;
  ui.luaPreviewStatusChip.textContent = preview?.ok ? "Compilado" : (preview?.status === "compile_error" ? "Erro" : "Aguardando");
  ui.luaEditorTelemetrySourceBadge.textContent = preview
    ? (preview.telemetry_source === "live" ? "telemetria ao vivo" : "ultimo pacote salvo")
    : "Sem telemetria";
  ui.luaPreviewSummary.textContent = preview
    ? `${preview.selected_game || "Jogo"}${preview.ok ? "" : " com erro no script"}.`
    : "A saida abaixo usa a telemetria mais recente.";
  ui.luaPreviewHeading.textContent = preview?.ok ? "Telemetria atual" : "Verifique o script";
  ui.luaPreviewOutput.textContent = preview?.output || "--";
  ui.luaPreviewErrorWrap.classList.toggle("hidden", !preview?.error);
  ui.luaPreviewError.textContent = preview?.error || "";
  ui.luaPreviewTelemetry.innerHTML = "";
  const items = preview?.telemetry_items || [];
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "lua-telemetry-pill";
    empty.innerHTML = `<strong>Sem telemetria</strong><span>Abra um jogo ou inicie a coleta.</span>`;
    ui.luaPreviewTelemetry.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "lua-telemetry-pill";
    row.innerHTML = `<strong>${escapeHtml(item.key)}</strong><span>${escapeHtml(item.value)}</span>`;
    ui.luaPreviewTelemetry.appendChild(row);
  });
}

async function requestAdjacentPreview(immediate) {
  if (activeAdjacentEditorIndex == null || !adjacentDevicesDraft[activeAdjacentEditorIndex]) {
    return;
  }
  clearTimeout(adjacentPreviewTimer);
  const run = async () => {
    const device = adjacentDevicesDraft[activeAdjacentEditorIndex];
    try {
      adjacentPreviewState = await window.pywebview.api.preview_adjacent_device({
        ...device,
        slot: activeAdjacentEditorIndex + 1,
        port: device.port || null,
      });
    } catch (error) {
      adjacentPreviewState = {
        ok: false,
        status: "compile_error",
        error: error.message || "Falha ao gerar preview.",
        output: "",
        packet: "",
        telemetry_items: [],
      };
    }
    renderAdjacentPreview();
  };
  if (immediate) {
    await run();
    return;
  }
  adjacentPreviewTimer = setTimeout(run, 180);
}

function renderFallbackEditor() {
  ui.fallbackField.innerHTML = "";
  state.panel_fields.forEach((field) => {
    const option = document.createElement("option");
    option.value = field.key;
    option.textContent = `${field.label} (${field.key})`;
    ui.fallbackField.appendChild(option);
  });
}

function renderFallbackList() {
  ui.fallbackList.innerHTML = "";
  const entries = Object.entries(fallbackOverridesDraft);
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "fallback-item";
    empty.innerHTML = `<div><strong>Nenhum fallback configurado</strong><span>O padrao atual continua sendo zero ou o default do campo.</span></div>`;
    ui.fallbackList.appendChild(empty);
    return;
  }
  entries.forEach(([fieldKey, value]) => {
    const field = state.panel_fields.find((item) => item.key === fieldKey);
    const item = document.createElement("div");
    item.className = "fallback-item";
    item.innerHTML = `
      <div>
        <strong>${field ? field.label : fieldKey}</strong>
        <span>${fieldKey} -> ${String(value)}</span>
      </div>
    `;
    const button = document.createElement("button");
    button.className = "btn btn-outline-light";
    button.textContent = "Remover";
    button.addEventListener("click", () => {
      delete fallbackOverridesDraft[fieldKey];
      renderFallbackList();
    });
    item.appendChild(button);
    ui.fallbackList.appendChild(item);
  });
}

function renderSelectedGameUnitHint() {
  const selected = getSelectedGame();
  const preferred = state.install_modal.plugin.preferred_units || state.install_modal.plugin.emitted_units || {};
  ui.selectedGameUnitsHint.textContent = `${selected.name}: velocidade ${preferred.speed || "-"}, pressao ${preferred.pressure || "-"}, temperatura ${preferred.temperature || "-"}.`;
}

function renderMotionOffsetLabels() {
  ui.motionOffsetXValue.textContent = ui.motionOffsetX.value;
  ui.motionOffsetYValue.textContent = ui.motionOffsetY.value;
  ui.motionOffsetZValue.textContent = ui.motionOffsetZ.value;
}

function renderUsefulInfoList() {
  ui.usefulInfoList.innerHTML = "";
  const fields = [...(state.panel_fields || [])].sort((left, right) => left.label.localeCompare(right.label, "pt-BR"));
  fields.forEach((field) => {
    const item = document.createElement("div");
    item.className = "fallback-item";
    item.innerHTML = `
      <div>
        <strong>${field.label}</strong>
        <span><code>${field.key}</code> | ${field.description || "Sem descricao."}</span>
      </div>
    `;
    ui.usefulInfoList.appendChild(item);
  });
}

function renderMotionPreview() {
  if (!state.motion_preview) {
    return;
  }
  motionHistory.push({ ...state.motion_preview.normalized });
  while (motionHistory.length > 48) {
    motionHistory.shift();
  }

  const preview = state.motion_preview;
  ui.motionPreviewValues.textContent = `X ${preview.normalized.x.toFixed(1)} | Y ${preview.normalized.y.toFixed(1)} | Z ${preview.normalized.z.toFixed(1)}`;
  const canvas = ui.motionPreviewCanvas;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i += 1) {
    const y = (canvas.height / 4) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  drawMotionLine(ctx, motionHistory.map((item) => item.x), "#7CFFB2", canvas.width, canvas.height);
  drawMotionLine(ctx, motionHistory.map((item) => item.y), "#6BC4FF", canvas.width, canvas.height);
  drawMotionLine(ctx, motionHistory.map((item) => item.z), "#FF8A9D", canvas.width, canvas.height);
}

function renderWebServerConfig() {
  ui.webServerStatusChip.textContent = state.web_server.http_enabled ? "Ligado" : "Desligado";
  ui.udpServerStatusChip.textContent = state.web_server.udp_enabled ? "Ligado" : "Desligado";
  ui.webServerUrl.value = state.web_server.network_url || state.web_server.http_url || "";
  ui.networkIpLabel.textContent = state.web_server.network_ip || "127.0.0.1";
  ui.udpPacketCount.textContent = String(state.web_server.udp_packets || 0);
  ui.activeTemplateLabel.textContent = state.web_server.selected_template_name || "Nenhum";
  ui.qrPreviewWrap.classList.toggle("hidden", !qrPreviewVisible || !state.web_server.qr_data_url);
  ui.qrPreviewImage.src = state.web_server.qr_data_url || "";
  ui.toggleQrPreviewBtn.disabled = !state.web_server.qr_available || !state.web_server.http_enabled;
  ui.toggleQrPreviewBtn.textContent = !state.web_server.qr_available
    ? "QR indisponivel"
    : qrPreviewVisible
      ? "Ocultar QR Code"
      : "Gerar QR Code";
  const share = state.telemetry_share || {};
  ui.telemetryShareStatusChip.textContent = share.available ? "Ativo" : (share.supported ? "Erro" : "Nao suportado");
  ui.telemetryShareName.textContent = share.map_name || "-";
  ui.telemetryShareUpdatedAt.textContent = share.last_updated_at || "-";
  ui.telemetryShareBytes.textContent = String(share.last_bytes || 0);
  ui.telemetryShareMaxSize.textContent = String(share.max_size || 0);
  ui.telemetryShareHelp.textContent = share.last_error
    ? `Ultimo erro: ${share.last_error}`
    : "Use o nome acima para abrir a memoria compartilhada em outro app Windows.";

  ui.udpMessageList.innerHTML = "";
  const messages = state.web_server.udp_messages || [];
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "fallback-item";
    empty.innerHTML = `<div><strong>Nenhum pacote recebido</strong><span>Assim que chegar algo no UDP ele aparece aqui.</span></div>`;
    ui.udpMessageList.appendChild(empty);
    return;
  }
  messages.forEach((message) => {
    const item = document.createElement("div");
    item.className = "fallback-item";
    item.innerHTML = `<div><strong>${message.from}</strong><span>${message.received_at || ""} | ${message.payload}</span></div>`;
    ui.udpMessageList.appendChild(item);
  });
}

async function renderAboutPane() {
  if (!ui.aboutHtmlHost || !state.about_info) {
    return;
  }
  if (!aboutTemplateHtml) {
    aboutTemplateHtml = state.about_info.template_html || "";
  }
  if (!aboutTemplateHtml) {
    ui.aboutHtmlHost.innerHTML = `<div class="about-card"><h3>DSW</h3><p>Falha ao carregar o arquivo HTML de apresentacao.</p></div>`;
    return;
  }
  const replacements = {
    "{{OWNER_NAME}}": state.about_info.owner_name || "DSW Simuladores",
    "{{OWNER_TEAM}}": state.about_info.owner_team || "Equipe DSW de Simuladores",
    "{{DISCORD_URL}}": state.about_info.discord_url || "#",
    "{{DISCORD_LABEL}}": state.about_info.discord_label || "Discord oficial em breve",
    "{{PROJECT_STATUS}}": state.about_info.project_status || "Projeto open source",
    "{{PIX_KEY}}": state.about_info.pix_key || "",
    "{{DONATION_QR}}": state.about_info.donation_qr_data_url || "",
    "{{DONATION_MESSAGE}}": state.about_info.donation_message || "",
  };
  let html = aboutTemplateHtml;
  Object.entries(replacements).forEach(([placeholder, value]) => {
    html = html.split(placeholder).join(String(value));
  });
  ui.aboutHtmlHost.innerHTML = html;
}

function drawMotionLine(ctx, values, color, width, height) {
  if (!values.length) {
    return;
  }
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  values.forEach((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * width;
    const y = height / 2 - (value / 100) * (height * 0.38);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
}

function bindExternalLinks(root) {
  root.querySelectorAll("[data-external-url]").forEach((link) => {
    if (link.dataset.externalBound === "true") {
      return;
    }
    link.dataset.externalBound = "true";
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      const url = link.dataset.externalUrl;
      if (!url || !window.pywebview?.api?.open_external_url) {
        return;
      }
      await window.pywebview.api.open_external_url(url);
    });
  });
}

function renderEqualizationEditor() {
  const selectedField = ui.equalizationField.value;
  ui.equalizationField.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Selecione uma variavel...";
  placeholder.selected = !selectedField;
  ui.equalizationField.appendChild(placeholder);
  state.panel_fields.forEach((field) => {
    const option = document.createElement("option");
    option.value = field.key;
    option.textContent = `${field.label} (${field.key})`;
    option.selected = field.key === selectedField;
    ui.equalizationField.appendChild(option);
  });
  renderEqualizationGameSelector();
}

function renderEqualizationGameSelector() {
  ui.equalizationGameList.innerHTML = "";
  const disabled = ui.equalizationApplyToAll.checked;
  state.games.forEach((game) => {
    const label = document.createElement("label");
    label.className = `form-check switch-card equalization-game-item ${disabled ? "is-disabled" : ""}`;
    const checked = disabled || equalizationSelectedGameIds.includes(game.id);
    label.innerHTML = `
      <input class="form-check-input" type="checkbox" value="${game.id}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>
      <span class="form-check-label">${game.name}</span>
    `;
    const input = label.querySelector("input");
    input.addEventListener("change", () => {
      if (input.checked) {
        if (!equalizationSelectedGameIds.includes(game.id)) {
          equalizationSelectedGameIds.push(game.id);
        }
      } else {
        equalizationSelectedGameIds = equalizationSelectedGameIds.filter((gameId) => gameId !== game.id);
      }
    });
    ui.equalizationGameList.appendChild(label);
  });
}

function renderEqualizationList() {
  ui.equalizationList.innerHTML = "";
  if (!equalizationRulesDraft.length) {
    const empty = document.createElement("div");
    empty.className = "fallback-item";
    empty.innerHTML = `<div><strong>Nenhuma equalizacao configurada</strong><span>Crie uma regra por variavel e escopo de jogos.</span></div>`;
    ui.equalizationList.appendChild(empty);
    return;
  }

  equalizationRulesDraft.forEach((rule, index) => {
    const field = state.panel_fields.find((item) => item.key === rule.field_key);
    const gameNames = rule.apply_to_all
      ? "Todos os jogos"
      : (rule.game_ids || [])
        .map((gameId) => state.games.find((game) => game.id === gameId)?.name || gameId)
        .join(", ");
    const item = document.createElement("div");
    item.className = "fallback-item";
    item.innerHTML = `
      <div>
        <strong>${field ? field.label : rule.field_key}</strong>
        <span>${rule.source_min}..${rule.source_max} -> ${rule.target_min}..${rule.target_max} | ${gameNames || "Nenhum jogo"}</span>
      </div>
    `;
    const button = document.createElement("button");
    button.className = "btn btn-outline-light";
    button.textContent = "Remover";
    button.addEventListener("click", () => {
      equalizationRulesDraft.splice(index, 1);
      renderEqualizationList();
    });
    item.appendChild(button);
    ui.equalizationList.appendChild(item);
  });
}

function renderMergeEditor() {
  const selectedTargetField = ui.mergeTargetField.value;
  const selectedSourceField = ui.mergeSourceField.value;
  [ui.mergeTargetField, ui.mergeSourceField].forEach((select, index) => {
    const selectedValue = index === 0 ? selectedTargetField : selectedSourceField;
    select.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = index === 0 ? "Selecione a variavel de destino..." : "Selecione a variavel de origem...";
    placeholder.selected = !selectedValue;
    select.appendChild(placeholder);
    state.panel_fields.forEach((field) => {
      const option = document.createElement("option");
      option.value = field.key;
      option.textContent = `${field.label} (${field.key})`;
      option.selected = field.key === selectedValue;
      select.appendChild(option);
    });
  });
  renderMergeGameSelector();
}

function renderMergeGameSelector() {
  ui.mergeGameList.innerHTML = "";
  const disabled = ui.mergeApplyToAll.checked;
  state.games.forEach((game) => {
    const label = document.createElement("label");
    label.className = `form-check switch-card equalization-game-item ${disabled ? "is-disabled" : ""}`;
    const checked = disabled || mergeSelectedGameIds.includes(game.id);
    label.innerHTML = `
      <input class="form-check-input" type="checkbox" value="${game.id}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>
      <span class="form-check-label">${game.name}</span>
    `;
    const input = label.querySelector("input");
    input.addEventListener("change", () => {
      if (input.checked) {
        if (!mergeSelectedGameIds.includes(game.id)) {
          mergeSelectedGameIds.push(game.id);
        }
      } else {
        mergeSelectedGameIds = mergeSelectedGameIds.filter((gameId) => gameId !== game.id);
      }
    });
    ui.mergeGameList.appendChild(label);
  });
}

function renderMergeList() {
  ui.mergeList.innerHTML = "";
  if (!mergeRulesDraft.length) {
    const empty = document.createElement("div");
    empty.className = "fallback-item";
    empty.innerHTML = `<div><strong>Nenhuma regra configurada</strong><span>Substituicao e mescla so entram em acao quando voce criar uma regra.</span></div>`;
    ui.mergeList.appendChild(empty);
    return;
  }

  mergeRulesDraft.forEach((rule, index) => {
    const targetField = state.panel_fields.find((item) => item.key === rule.target_field_key);
    const sourceField = state.panel_fields.find((item) => item.key === rule.source_field_key);
    const gameNames = rule.apply_to_all
      ? "Todos os jogos"
      : (rule.game_ids || [])
        .map((gameId) => state.games.find((game) => game.id === gameId)?.name || gameId)
        .join(", ");
    const item = document.createElement("div");
    item.className = "fallback-item";
    item.innerHTML = `
      <div>
        <strong>${targetField ? targetField.label : rule.target_field_key} <= ${sourceField ? sourceField.label : rule.source_field_key}</strong>
        <span>${rule.mode === "merge" ? "Mesclar" : "Substituir"} | ${gameNames || "Nenhum jogo"}</span>
      </div>
    `;
    const button = document.createElement("button");
    button.className = "btn btn-outline-light";
    button.textContent = "Remover";
    button.addEventListener("click", () => {
      mergeRulesDraft.splice(index, 1);
      renderMergeList();
    });
    item.appendChild(button);
    ui.mergeList.appendChild(item);
  });
}

async function handleMainAction() {
  const selected = getSelectedGame();
  if (selected.installed === "no") {
    openModal("install");
    return;
  }
  state = await window.pywebview.api.toggle_action();
  render();
}

async function installSelectedGame() {
  const confirmed = await showDialog({
    title: "Instalar integracao",
    text: "Deseja instalar ou marcar esta integracao para uso?",
    confirmLabel: "Instalar",
    cancelLabel: "Cancelar",
  });
  if (!confirmed) {
    return;
  }
  setInstallBusy("Instalando integracao...");
  state = await window.pywebview.api.install_selected_game_modal();
  clearInstallBusy();
  render();
}

async function uninstallSelectedGame() {
  const confirmed = await showDialog({
    title: "Remover integracao",
    text: "Deseja remover a integracao do jogo selecionado?",
    confirmLabel: "Remover",
    cancelLabel: "Cancelar",
  });
  if (!confirmed) {
    return;
  }
  setInstallBusy("Removendo integracao...");
  state = await window.pywebview.api.uninstall_selected_game_modal();
  clearInstallBusy();
  render();
}

async function savePanelConfig() {
  const order = [...ui.panelSlots.querySelectorAll("select")].map((select) => select.value);
  state = await window.pywebview.api.save_panel_config({
    mode: ui.panelMode.value,
    port: ui.panelPort.value || null,
    baudrate: Number(ui.panelBaudrate.value || 115200),
    fps: Number(ui.panelFps.value || 20),
    append_newline: ui.panelAppendNewline.checked,
    order,
  });
  closeModals();
  render();
}

async function saveMotionConfig() {
  state = await window.pywebview.api.save_motion_config({
    mode: ui.motionMode.value,
    port: ui.motionPort.value || null,
    baudrate: Number(ui.motionBaudrate.value || 115200),
    fps: Number(ui.motionFps.value || 20),
    append_newline: ui.motionAppendNewline.checked,
    min_value: Number(ui.motionMin.value || -100),
    max_value: Number(ui.motionMax.value || 100),
    phase_invert_x: ui.motionPhaseX.checked,
    phase_invert_y: ui.motionPhaseY.checked,
    phase_invert_z: ui.motionPhaseZ.checked,
    onoff_invert_x: ui.motionEnableX.checked,
    onoff_invert_y: ui.motionEnableY.checked,
    onoff_invert_z: ui.motionEnableZ.checked,
    offset_power_x: Number(ui.motionOffsetX.value || 0),
    offset_power_y: Number(ui.motionOffsetY.value || 0),
    offset_power_z: Number(ui.motionOffsetZ.value || 0),
  });
  closeModals();
  render();
}

async function saveBasicSettings() {
  try {
    state = await window.pywebview.api.save_basic_settings({
      speed_unit: ui.speedUnit.value,
      pressure_unit: ui.pressureUnit.value,
      temperature_unit: ui.temperatureUnit.value,
      launch_with_windows: ui.launchWithWindows.checked,
      detect_open_game_on_start: ui.detectOpenGameOnStart.checked,
      fallback_overrides: fallbackOverridesDraft,
      value_equalization_rules: equalizationRulesDraft,
      telemetry_merge_rules: mergeRulesDraft,
      adjacent_devices: adjacentDevicesDraft.map((device, index) => ({
        ...device,
        slot: index + 1,
        port: device.port || null,
      })),
    });
    closeModals();
    render();
  } catch (error) {
    await showDialog({ title: "Lua / Serial", text: error.message || "Falha ao salvar os dispositivos adjacentes." });
  }
}

async function exportPanelConfig() {
  state = await window.pywebview.api.export_panel_config_json();
  render();
}

async function importPanelConfig() {
  state = await window.pywebview.api.import_panel_config_json();
  render();
}

async function saveWebServerConfig(closeAfter = true) {
  state = await window.pywebview.api.save_web_server_config({
    http_auto_start: ui.webServerAutoStart.checked,
    http_host: ui.webServerHost.value || "0.0.0.0",
    http_port: Number(ui.webServerPort.value || 8080),
    udp_auto_start: ui.udpServerAutoStart.checked,
    udp_host: ui.udpServerHost.value || "0.0.0.0",
    udp_port: Number(ui.udpServerPort.value || 28000),
    selected_template: state.web_server.selected_template || "simple-dashboard",
  });
  if (closeAfter) {
    closeModals();
  }
  render();
}

async function toggleWebServer() {
  await setWebServerEnabled(ui.webServerEnabled.checked);
}

async function toggleUdpServer() {
  await setUdpServerEnabled(ui.udpServerEnabled.checked);
}

async function setWebServerEnabled(enabled) {
  ui.webServerEnabled.checked = enabled;
  await saveWebServerConfig(false);
  state = enabled
    ? await window.pywebview.api.start_web_server()
    : await window.pywebview.api.stop_web_server();
  render();
}

async function setUdpServerEnabled(enabled) {
  ui.udpServerEnabled.checked = enabled;
  await saveWebServerConfig(false);
  state = enabled
    ? await window.pywebview.api.start_udp_server()
    : await window.pywebview.api.stop_udp_server();
  render();
}

function addOrUpdateFallbackOverride() {
  const fieldKey = ui.fallbackField.value;
  const field = state.panel_fields.find((item) => item.key === fieldKey);
  if (!field) {
    return;
  }
  const rawValue = ui.fallbackValue.value.trim();
  if (!rawValue) {
    delete fallbackOverridesDraft[fieldKey];
    renderFallbackList();
    return;
  }
  fallbackOverridesDraft[fieldKey] = coerceFallbackValue(field.default, rawValue);
  ui.fallbackValue.value = "";
  renderFallbackList();
}

function coerceFallbackValue(defaultValue, rawValue) {
  if (typeof defaultValue === "boolean") {
    return ["1", "true", "sim", "yes", "on"].includes(rawValue.toLowerCase());
  }
  if (typeof defaultValue === "number") {
    const numeric = Number(rawValue.replace(",", "."));
    return Number.isFinite(numeric) ? numeric : 0;
  }
  return rawValue;
}

function addOrUpdateEqualizationRule() {
  if (!ui.equalizationField.value) {
    return;
  }
  const sourceMin = Number(ui.equalizationSourceMin.value);
  const sourceMax = Number(ui.equalizationSourceMax.value);
  const targetMin = Number(ui.equalizationTargetMin.value);
  const targetMax = Number(ui.equalizationTargetMax.value);
  if (![sourceMin, sourceMax, targetMin, targetMax].every(Number.isFinite)) {
    return;
  }
  const applyToAll = ui.equalizationApplyToAll.checked;
  const gameIds = applyToAll ? [] : [...equalizationSelectedGameIds].sort();
  if (!applyToAll && !gameIds.length) {
    return;
  }

  const rule = {
    field_key: ui.equalizationField.value,
    source_min: sourceMin,
    source_max: sourceMax,
    target_min: targetMin,
    target_max: targetMax,
    apply_to_all: applyToAll,
    game_ids: gameIds.sort(),
  };
  const signature = `${rule.field_key}|${rule.apply_to_all ? "*" : rule.game_ids.join(",")}`;
  const existingIndex = equalizationRulesDraft.findIndex((item) => {
    const itemSignature = `${item.field_key}|${item.apply_to_all ? "*" : [...(item.game_ids || [])].sort().join(",")}`;
    return itemSignature === signature;
  });
  if (existingIndex >= 0) {
    equalizationRulesDraft[existingIndex] = rule;
  } else {
    equalizationRulesDraft.push(rule);
  }
  renderEqualizationList();
  clearEqualizationForm(false);
}

function clearEqualizationForm(resetApplyToAll = true) {
  ui.equalizationField.value = "";
  ui.equalizationSourceMin.value = "";
  ui.equalizationSourceMax.value = "";
  ui.equalizationTargetMin.value = "";
  ui.equalizationTargetMax.value = "";
  equalizationSelectedGameIds = [];
  ui.equalizationApplyToAll.checked = resetApplyToAll ? false : ui.equalizationApplyToAll.checked;
  renderEqualizationGameSelector();
}

function addOrUpdateMergeRule() {
  const targetFieldKey = ui.mergeTargetField.value;
  const sourceFieldKey = ui.mergeSourceField.value;
  if (!targetFieldKey || !sourceFieldKey || targetFieldKey === sourceFieldKey) {
    return;
  }
  const applyToAll = ui.mergeApplyToAll.checked;
  const gameIds = applyToAll ? [] : [...mergeSelectedGameIds].sort();
  if (!applyToAll && !gameIds.length) {
    return;
  }

  const rule = {
    target_field_key: targetFieldKey,
    source_field_key: sourceFieldKey,
    mode: ui.mergeMode.value === "merge" ? "merge" : "replace",
    apply_to_all: applyToAll,
    game_ids: gameIds,
  };
  const signature = `${rule.target_field_key}|${rule.source_field_key}|${rule.apply_to_all ? "*" : rule.game_ids.join(",")}`;
  const existingIndex = mergeRulesDraft.findIndex((item) => {
    const itemSignature = `${item.target_field_key}|${item.source_field_key}|${item.apply_to_all ? "*" : [...(item.game_ids || [])].sort().join(",")}`;
    return itemSignature === signature;
  });
  if (existingIndex >= 0) {
    mergeRulesDraft[existingIndex] = rule;
  } else {
    mergeRulesDraft.push(rule);
  }
  renderMergeList();
  clearMergeForm(false);
}

function clearMergeForm(resetApplyToAll = true) {
  ui.mergeTargetField.value = "";
  ui.mergeSourceField.value = "";
  ui.mergeMode.value = "replace";
  mergeSelectedGameIds = [];
  ui.mergeApplyToAll.checked = resetApplyToAll ? false : ui.mergeApplyToAll.checked;
  renderMergeGameSelector();
}

function setInstallBusy(text) {
  installBusyState = text;
  renderInstallModal();
}

function clearInstallBusy() {
  installBusyState = null;
  renderInstallModal();
}

function setSettingsTab(tabName) {
  activeSettingsTab = tabName;
  ui.settingsTabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.settingsTab === tabName);
  });
  Object.entries(ui.settingsPanes).forEach(([name, pane]) => {
    pane.classList.toggle("active", name === tabName);
  });
}

function openModal(type) {
  closeModals();
  activeModal = type;
  ui.overlay.classList.remove("hidden");
  if (type === "panel") {
    renderConfigs();
    ui.panelModal.classList.remove("hidden");
  }
  if (type === "motion") {
    renderConfigs();
    ui.motionModal.classList.remove("hidden");
  }
  if (type === "install") {
    ui.installModal.classList.remove("hidden");
  }
  if (type === "basic") {
    renderConfigs();
    ui.basicSettingsModal.classList.remove("hidden");
  }
  if (type === "webServer") {
    renderConfigs();
    ui.webServerModal.classList.remove("hidden");
  }
  if (type === "luaEditor") {
    renderAdjacentEditorModal();
    ui.luaEditorModal.classList.remove("hidden");
  }
  if (type === "githubPlugin") {
    renderConfigs();
    ui.githubPluginModal.classList.remove("hidden");
  }
}

function closeModals() {
  activeModal = null;
  installBusyState = null;
  hideLuaContextMenu();
  ui.overlay.classList.add("hidden");
  ui.panelModal.classList.add("hidden");
  ui.motionModal.classList.add("hidden");
  ui.installModal.classList.add("hidden");
  ui.basicSettingsModal.classList.add("hidden");
  ui.webServerModal.classList.add("hidden");
  ui.luaEditorModal.classList.add("hidden");
  ui.githubPluginModal.classList.add("hidden");
  activeAdjacentEditorIndex = null;
  adjacentPreviewState = null;
  clearTimeout(adjacentPreviewTimer);
}

function isEditingConfigModal() {
  return ["panel", "motion", "basic", "webServer", "githubPlugin", "luaEditor"].includes(activeModal);
}

function getSelectedGame() {
  return state.games.find((game) => game.selected);
}

function formatDeviceState(stateName) {
  const labels = {
    sending: "Enviando",
    ready: "Pronto",
    waiting: "Aguardando",
    disabled: "Desligado",
    not_configured: "Sem porta",
    port_missing: "Porta ausente",
    serial_unavailable: "Sem PySerial",
    lua_unavailable: "Sem Lua",
    error: "Erro",
  };
  return labels[stateName] || stateName;
}

function formatSerialMode(modeName) {
  const labels = {
    Disabled: "Desligado",
    Automatic: "Automatico",
    Manual: "Manual",
  };
  return labels[modeName] || modeName || "-";
}

async function sendDeviceCommand(deviceKind, rawValue = null) {
  const sourceValue = rawValue == null ? deviceCommandDrafts[deviceKind] || "" : rawValue;
  const command = String(sourceValue).trim().replace(/\r?\n/g, " ");

  if (!command) {
    await showDialog({ title: "Comando serial", text: "Digite um comando antes de enviar." });
    return;
  }
  
  deviceCommandDrafts[deviceKind] = command;
  try {
    state = await window.pywebview.api.send_device_command(deviceKind, command);
    deviceCommandDrafts[deviceKind] = "";
    render();
  } catch (error) {
    await showDialog({ title: "Erro", text: `Erro ao enviar comando: ${error.message}` });
  }
}

function basename(filePath) {
  return String(filePath || "").split(/[\\/]/).pop() || "";
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (!value) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let index = 0;
  let current = value;
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }
  return `${current.toFixed(current >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDateLabel(value) {
  if (!value) {
    return "sem data";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("pt-BR");
}

function drainMessages() {
  (state.messages || []).forEach((message) => {
    if (!shownMessageIds.has(message.id)) {
      shownMessageIds.add(message.id);
      dialogQueue.push(message);
    }
  });
  pumpDialogQueue();
}

function pumpDialogQueue() {
  if (dialogOpen || !dialogQueue.length) {
    return;
  }
  const message = dialogQueue.shift();
  showDialog({
    title: message.title || "Mensagem",
    text: message.text || "",
    confirmLabel: "OK",
  });
}

function showDialog({ title, text, confirmLabel = "OK", cancelLabel = "" }) {
  return new Promise((resolve) => {
    dialogOpen = true;
    dialogResolver = resolve;
    ui.dialogTitle.textContent = title;
    ui.dialogText.textContent = text;
    ui.dialogConfirmBtn.textContent = confirmLabel;
    ui.dialogCancelBtn.textContent = cancelLabel || "Cancelar";
    ui.dialogCancelBtn.classList.toggle("hidden", !cancelLabel);
    ui.dialogModal.classList.remove("hidden");
  });
}

function resolveDialog(result) {
  if (!dialogOpen) {
    return;
  }
  ui.dialogModal.classList.add("hidden");
  dialogOpen = false;
  const resolver = dialogResolver;
  dialogResolver = null;
  if (resolver) {
    resolver(result);
  }
  setTimeout(pumpDialogQueue, 0);
}
