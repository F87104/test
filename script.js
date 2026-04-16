const STORAGE_KEY = "story-stock-lab-weekly-state-v1";
const AUTO_FEED_INTERVAL_MS = 6500;
const MAX_TICKER_ITEMS = 20;

const starterMembers = [
  { name: "田中さん", points: 64 },
  { name: "佐藤さん", points: 58 },
  { name: "高橋さん", points: 46 },
  { name: "鈴木さん", points: 44 },
  { name: "中村さん", points: 39 },
];

const randomNames = [
  "山田さん",
  "井上さん",
  "木村さん",
  "加藤さん",
  "小林さん",
  "清水さん",
  "松本さん",
  "森さん",
];

const randomReasons = [
  "デイリー報告",
  "週次課題提出",
  "初案件獲得",
  "他メンバー支援",
  "公開フィードバック登壇",
];

const randomPointTable = [1, 3, 5, 8, 10, 12, 20];

const rankingList = document.getElementById("rankingList");
const tickerTrack = document.getElementById("tickerTrack");
const awardForm = document.getElementById("awardForm");
const nameInput = document.getElementById("nameInput");
const pointsInput = document.getElementById("pointsInput");
const reasonInput = document.getElementById("reasonInput");
const resetButton = document.getElementById("resetButton");
const autoFeedButton = document.getElementById("toggleAutoFeedButton");
const lastUpdated = document.getElementById("lastUpdated");

let state = loadState();
let autoFeedEnabled = true;
let autoFeedTimer = null;

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (error) {
    console.warn("Failed to load saved state:", error);
  }

  return {
    members: starterMembers,
    tickerEvents: [
      createEvent("田中さん", 10, "週次課題提出"),
      createEvent("佐藤さん", 8, "他メンバー支援"),
      createEvent("中村さん", 20, "初案件獲得"),
    ],
    updatedAt: Date.now(),
  };
}

function persistState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function createEvent(name, points, reason) {
  const id =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return {
    id,
    name,
    points,
    reason,
    timestamp: Date.now(),
  };
}

function addPoints(name, points, reason) {
  const normalizedName = name.trim();
  const existing = state.members.find((member) => member.name === normalizedName);

  if (existing) {
    existing.points += points;
  } else {
    state.members.push({ name: normalizedName, points });
  }

  state.tickerEvents.unshift(createEvent(normalizedName, points, reason));
  state.tickerEvents = state.tickerEvents.slice(0, MAX_TICKER_ITEMS);
  state.updatedAt = Date.now();
  persistState();
  render();
}

function formatTimestamp(timestamp) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp);
}

function renderRanking() {
  rankingList.innerHTML = "";

  const sorted = [...state.members].sort((a, b) => b.points - a.points);

  sorted.forEach((member, index) => {
    const row = document.createElement("li");
    row.className = `ranking-row ${index < 3 ? "top3" : ""}`;
    row.innerHTML = `
      <span class="ranking-position">${index + 1}</span>
      <span class="ranking-name">${member.name}</span>
      <span class="ranking-points">${member.points} pt</span>
    `;
    rankingList.appendChild(row);
  });
}

function renderTicker() {
  tickerTrack.innerHTML = "";

  const repeatedEvents = [...state.tickerEvents, ...state.tickerEvents];
  repeatedEvents.forEach((event) => {
    const item = document.createElement("li");
    item.className = "ticker-item";
    item.textContent = `${event.name}が${event.reason}で${event.points}pt獲得しました（${formatTimestamp(
      event.timestamp
    )}）`;
    tickerTrack.appendChild(item);
  });
}

function renderUpdatedAt() {
  lastUpdated.textContent = `最終更新: ${formatTimestamp(state.updatedAt)}`;
}

function render() {
  renderRanking();
  renderTicker();
  renderUpdatedAt();
}

awardForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = nameInput.value.trim();
  const points = Number(pointsInput.value);
  const reason = reasonInput.value;

  if (!name || !Number.isFinite(points) || points < 1) {
    return;
  }

  addPoints(name, points, reason);
  awardForm.reset();
  pointsInput.value = "10";
  nameInput.focus();
});

resetButton.addEventListener("click", () => {
  if (!window.confirm("今週のランキングを本当にリセットしますか？")) {
    return;
  }

  state = {
    members: starterMembers.map((member) => ({ ...member, points: 0 })),
    tickerEvents: [createEvent("システム", 0, "週間ランキングをリセット")],
    updatedAt: Date.now(),
  };
  persistState();
  render();
});

function randomItem(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function runAutoFeedTick() {
  const name = randomItem(randomNames);
  const points = randomItem(randomPointTable);
  const reason = randomItem(randomReasons);
  addPoints(name, points, reason);
}

function setAutoFeed(enabled) {
  autoFeedEnabled = enabled;
  autoFeedButton.textContent = `自動速報: ${enabled ? "ON" : "OFF"}`;
  autoFeedButton.classList.toggle("button-danger", !enabled);

  if (enabled) {
    autoFeedTimer = window.setInterval(runAutoFeedTick, AUTO_FEED_INTERVAL_MS);
  } else if (autoFeedTimer) {
    window.clearInterval(autoFeedTimer);
    autoFeedTimer = null;
  }
}

autoFeedButton.addEventListener("click", () => {
  setAutoFeed(!autoFeedEnabled);
});

render();
setAutoFeed(true);
