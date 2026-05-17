const statePill = document.getElementById("statePill");
const stateLabel = document.getElementById("stateLabel");
const statusText = document.getElementById("statusText");
const cameraImage = document.getElementById("cameraImage");
const cameraEmpty = document.getElementById("cameraEmpty");
const wakeWord = document.getElementById("wakeWord");
const manualStatus = document.getElementById("manualStatus");
const continuousStatus = document.getElementById("continuousStatus");
const listenButton = document.getElementById("listenButton");
const endButton = document.getElementById("endButton");
const clearButton = document.getElementById("clearButton");
const textForm = document.getElementById("textForm");
const textInput = document.getElementById("textInput");
const sessionText = document.getElementById("sessionText");
const sessionTime = document.getElementById("sessionTime");
const sessionFill = document.getElementById("sessionFill");
const messages = document.getElementById("messages");

let lastMessageKey = "";
let latestState = null;

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
  statePill.className = `state-pill state-${state.state}`;
  stateLabel.textContent = state.stateLabel;
  statusText.textContent = state.error || state.statusText;
  wakeWord.textContent = state.wakeWord;
  manualStatus.textContent = state.manualArmed
    ? `発話待ち ${state.manualRemainingSec.toFixed(1)}秒`
    : "待機なし";
  continuousStatus.textContent =
    state.continuousRemainingSec > 0
      ? `残り ${state.continuousRemainingSec.toFixed(1)}秒`
      : "待機なし";

  const busy = state.state === "THINKING" || state.state === "SPEAKING";
  listenButton.disabled = !state.ready || state.manualArmed || busy;
  endButton.disabled = !state.ready;
  clearButton.disabled = !state.ready;
  textInput.disabled = !state.ready || busy;

  updateMeter(state);
  renderMessages(state.messages || []);
}

async function refreshState() {
  try {
    const state = await api("/api/state");
    renderState(state);
  } catch (error) {
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
