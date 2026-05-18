const statePill = document.getElementById("statePill");
const stateLabel = document.getElementById("stateLabel");
const statusText = document.getElementById("statusText");
const cameraImage = document.getElementById("cameraImage");
const cameraEmpty = document.getElementById("cameraEmpty");
const wakeWord = document.getElementById("wakeWord");
const manualStatus = document.getElementById("manualStatus");
const continuousStatus = document.getElementById("continuousStatus");
const safetyStatus = document.getElementById("safetyStatus");
const missionStatus = document.getElementById("missionStatus");
const cleaningStatus = document.getElementById("cleaningStatus");
const connectionStatus = document.getElementById("connectionStatus");
const connectionDetail = document.getElementById("connectionDetail");
const connectButton = document.getElementById("connectButton");
const estopButton = document.getElementById("estopButton");
const resetEstopButton = document.getElementById("resetEstopButton");
const listenButton = document.getElementById("listenButton");
const endButton = document.getElementById("endButton");
const clearButton = document.getElementById("clearButton");
const forwardButton = document.getElementById("forwardButton");
const reverseButton = document.getElementById("reverseButton");
const leftButton = document.getElementById("leftButton");
const rightButton = document.getElementById("rightButton");
const stopButton = document.getElementById("stopButton");
const cleanOnButton = document.getElementById("cleanOnButton");
const cleanOffButton = document.getElementById("cleanOffButton");
const lightsButton = document.getElementById("lightsButton");
const missionStartButton = document.getElementById("missionStartButton");
const missionPauseButton = document.getElementById("missionPauseButton");
const missionResumeButton = document.getElementById("missionResumeButton");
const missionFinishButton = document.getElementById("missionFinishButton");
const driveStatus = document.getElementById("driveStatus");
const missionNote = document.getElementById("missionNote");
const planIntent = document.getElementById("planIntent");
const observationText = document.getElementById("observationText");
const hazardsText = document.getElementById("hazardsText");
const actionPlanText = document.getElementById("actionPlanText");
const chatDrawer = document.getElementById("chatDrawer");
const chatBadge = document.getElementById("chatBadge");
const textForm = document.getElementById("textForm");
const textInput = document.getElementById("textInput");
const sessionText = document.getElementById("sessionText");
const sessionTime = document.getElementById("sessionTime");
const sessionFill = document.getElementById("sessionFill");
const messages = document.getElementById("messages");

let lastMessageKey = "";
let latestState = null;
let operatorConnected = false;
let connectionMessageUntil = 0;

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function post(path) {
  return api(path, { method: "POST" });
}

function postJson(path, payload) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function formatLatency(latency) {
  if (!latency) return "";
  const items = [];
  if (Number.isFinite(latency.stt)) items.push(`STT ${latency.stt}ms`);
  if (Number.isFinite(latency.llm)) items.push(`LLM ${latency.llm}ms`);
  if (Number.isFinite(latency.tts)) items.push(`TTS ${latency.tts}ms`);
  return items.join(" / ");
}

function renderMessages(items) {
  const key = items.map((item) => item.id).join(",");
  if (key === lastMessageKey) return;
  lastMessageKey = key;
  chatBadge.textContent = `${items.length}件`;

  messages.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    li.className = `message ${item.role}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = item.text;

    const latency = formatLatency(item.latencyMs);
    if (latency) {
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = latency;
      bubble.appendChild(meta);
    }

    li.appendChild(bubble);
    messages.appendChild(li);
  }
  messages.scrollTop = messages.scrollHeight;
}

function formatList(items, fallback = "なし") {
  if (!Array.isArray(items) || items.length === 0) return fallback;
  return items.join(" / ");
}

function formatActionPlan(plan) {
  const actions = plan?.actions || [];
  if (!actions.length) return "なし";
  return actions
    .map((action) => {
      const params = action.params || {};
      const command = params.command || params.state || params.tool || "";
      return command ? `${action.type}:${command}` : action.type;
    })
    .join(" / ");
}

function renderRobot(robot) {
  if (!robot) return;
  const telemetry = robot.telemetry || {};
  const safety = robot.safety || {};
  const mission = robot.mission || {};
  const worldState = robot.worldState || {};
  const plan = robot.actionPlan || {};

  const estopActive = Boolean(safety.estopActive || safety.estop_active);
  const safeLabel = estopActive
    ? "緊急停止中"
    : safety.ok
      ? "監視中"
      : "警告";
  safetyStatus.textContent = safeLabel;
  missionStatus.textContent = mission.phase || "idle";
  cleaningStatus.textContent = telemetry.cleaningState || telemetry.cleaning_state || "off";
  driveStatus.textContent = telemetry.driveState || telemetry.drive_state || "stopped";
  missionNote.textContent = mission.note || "待機中";
  planIntent.textContent = plan.intent || "待機中";
  observationText.textContent = robot.lastObservation || "まだ観察メモはありません";
  hazardsText.textContent = formatList(worldState.hazards);
  actionPlanText.textContent = formatActionPlan(plan);
  if (window.robotTwin) {
    window.robotTwin.updateFromRobot(robot);
  }

  const estop = estopActive;
  resetEstopButton.disabled = !estop;
  const motionDisabled = estop || !latestState?.ready;
  for (const button of [
    forwardButton,
    reverseButton,
    leftButton,
    rightButton,
    cleanOnButton,
    cleanOffButton,
    lightsButton,
  ]) {
    button.disabled = motionDisabled;
  }
  stopButton.disabled = !latestState?.ready;
  missionStartButton.disabled = !latestState?.ready || estop;
  missionPauseButton.disabled = !latestState?.ready;
  missionResumeButton.disabled = !latestState?.ready || estop;
  missionFinishButton.disabled = !latestState?.ready;
}

function updateMeter(state) {
  sessionFill.className = "meter-fill";

  if (state.manualArmed) {
    const remaining = state.manualRemainingSec;
    const pct = Math.max(0, Math.min(100, (remaining / 20) * 100));
    sessionText.textContent = "ボタン起動: 発話待ち";
    sessionTime.textContent = `${remaining.toFixed(1)}秒`;
    sessionFill.style.width = `${pct}%`;
    sessionFill.classList.add("manual");
    return;
  }

  if (state.state === "SPEAKING") {
    sessionText.textContent = "読み上げ中";
    sessionTime.textContent = "";
    sessionFill.style.width = "100%";
    sessionFill.classList.add("speaking");
    return;
  }

  if (state.continuousRemainingSec > 0) {
    const remaining = state.continuousRemainingSec;
    const limit = Math.max(1, state.continuousLimitSec);
    const pct = Math.max(0, Math.min(100, (remaining / limit) * 100));
    sessionText.textContent = "Wake Wordなしで続けて話せます";
    sessionTime.textContent = `${remaining.toFixed(1)}秒`;
    sessionFill.style.width = `${pct}%`;
    return;
  }

  sessionText.textContent = "次はWake Wordまたはボタンで開始";
  sessionTime.textContent = "0.0秒";
  sessionFill.style.width = "0%";
}

function renderState(state) {
  latestState = state;
  operatorConnected = Boolean(state.ready);
  statePill.className = `state-pill state-${state.state}`;
  stateLabel.textContent = state.stateLabel;
  statusText.textContent = state.error || state.statusText;
  connectionStatus.textContent = state.ready ? "接続済み" : "接続待ち";
  if (Date.now() >= connectionMessageUntil) {
    connectionDetail.textContent = state.error
      ? state.error
      : state.ready
        ? `カメラ ${state.cameraRunning ? "ON" : "OFF"} / 状態 ${state.stateLabel}`
        : "モデルとデバイスの起動を待っています";
  }
  connectButton.textContent = state.ready ? "再接続" : "接続";
  wakeWord.textContent = state.wakeWord;
  manualStatus.textContent = state.manualArmed
    ? `発話待ち ${state.manualRemainingSec.toFixed(1)}秒`
    : "待機なし";
  continuousStatus.textContent =
    state.continuousRemainingSec > 0
      ? `残り ${state.continuousRemainingSec.toFixed(1)}秒`
      : "待機なし";

  const busy = state.state === "THINKING" || state.state === "SPEAKING";
  connectButton.disabled = false;
  listenButton.disabled = !operatorConnected || state.manualArmed || busy;
  endButton.disabled = !state.ready;
  clearButton.disabled = !state.ready;
  textInput.disabled = !state.ready || busy;

  updateMeter(state);
  renderMessages(state.messages || []);
  renderRobot(state.robot);
}

async function refreshState() {
  try {
    const state = await api("/api/state");
    renderState(state);
  } catch (error) {
    operatorConnected = false;
    connectionStatus.textContent = "未接続";
    connectionDetail.textContent = `接続待ち: ${error.message}`;
    statusText.textContent = `接続待ち: ${error.message}`;
  }
}

function refreshCamera() {
  const next = new Image();
  next.onload = () => {
    cameraImage.src = next.src;
    cameraEmpty.classList.add("hidden");
  };
  next.onerror = () => {
    if (!latestState || !latestState.cameraRunning) {
      cameraEmpty.classList.remove("hidden");
    }
  };
  next.src = `/api/frame.jpg?t=${Date.now()}`;
}

listenButton.addEventListener("click", async () => {
  listenButton.disabled = true;
  try {
    renderState(await post("/api/listen"));
  } catch (error) {
    statusText.textContent = `話しかけ開始に失敗: ${error.message}`;
  }
});

connectButton.addEventListener("click", async () => {
  connectButton.disabled = true;
  try {
    await refreshState();
    if (operatorConnected) {
      connectionMessageUntil = Date.now() + 2500;
      connectionDetail.textContent = "操作卓に接続しました";
    }
  } finally {
    connectButton.disabled = false;
  }
});

estopButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/estop"));
  } catch (error) {
    statusText.textContent = `緊急停止に失敗: ${error.message}`;
  }
});

resetEstopButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/estop/reset"));
  } catch (error) {
    statusText.textContent = `緊急停止解除に失敗: ${error.message}`;
  }
});

function wireManual(button, command) {
  button.addEventListener("click", async () => {
    try {
      renderState(await postJson("/api/manual-control", { command }));
    } catch (error) {
      statusText.textContent = `操作に失敗: ${error.message}`;
    }
  });
}

wireManual(forwardButton, "forward");
wireManual(reverseButton, "reverse");
wireManual(leftButton, "turn_left");
wireManual(rightButton, "turn_right");
wireManual(stopButton, "stop");
wireManual(cleanOnButton, "clean_on");
wireManual(cleanOffButton, "clean_off");
wireManual(lightsButton, "lights_toggle");

missionStartButton.addEventListener("click", async () => {
  try {
    renderState(await postJson("/api/mission/start", { targetDistanceM: 0 }));
  } catch (error) {
    statusText.textContent = `ミッション開始に失敗: ${error.message}`;
  }
});

missionPauseButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/mission/pause"));
  } catch (error) {
    statusText.textContent = `ミッション一時停止に失敗: ${error.message}`;
  }
});

missionResumeButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/mission/resume"));
  } catch (error) {
    statusText.textContent = `ミッション再開に失敗: ${error.message}`;
  }
});

missionFinishButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/mission/finish"));
  } catch (error) {
    statusText.textContent = `ミッション完了に失敗: ${error.message}`;
  }
});

endButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/end-session"));
  } catch (error) {
    statusText.textContent = `会話終了に失敗: ${error.message}`;
  }
});

clearButton.addEventListener("click", async () => {
  try {
    renderState(await post("/api/clear"));
    if (chatDrawer.open) {
      messages.scrollTop = messages.scrollHeight;
    }
  } catch (error) {
    statusText.textContent = `消去に失敗: ${error.message}`;
  }
});

textForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = textInput.value.trim();
  if (!text) return;
  textInput.value = "";
  try {
    renderState(await postJson("/api/text", { text }));
  } catch (error) {
    statusText.textContent = `送信に失敗: ${error.message}`;
  }
});

refreshState();
refreshCamera();
setInterval(refreshState, 500);
setInterval(refreshCamera, 180);
