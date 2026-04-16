const STORAGE_KEY = "story-stock-lab-weekly-state-v1";
const AUTO_FEED_INTERVAL_MS = 6500;
const MAX_TICKER_ITEMS = 20;
const DEFAULT_LEARNER_NAME = "あなた";

const VIDEO_COMPLETE_THRESHOLD = 0.95;
const SEEK_TOLERANCE_SECONDS = 8;

const lectureCatalog = [
  {
    id: "lec-1",
    title: "講座1: 強みの棚卸し",
    points: 12,
    minWatchSeconds: 45,
    src:
      "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
  {
    id: "lec-2",
    title: "講座2: ターゲット設定",
    points: 15,
    minWatchSeconds: 45,
    src:
      "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
  {
    id: "lec-3",
    title: "講座3: オファー設計",
    points: 20,
    minWatchSeconds: 50,
    src:
      "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
  {
    id: "lec-4",
    title: "講座4: LP作成の基本",
    points: 18,
    minWatchSeconds: 50,
    src:
      "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
  {
    id: "lec-5",
    title: "講座5: 初提案の作り方",
    points: 22,
    minWatchSeconds: 55,
    src:
      "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
  {
    id: "lec-6",
    title: "講座6: 改善ループ運用",
    points: 25,
    minWatchSeconds: 60,
    src:
      "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  },
];

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
const learningSummary = document.getElementById("learningSummary");
const learningProgressBar = document.getElementById("learningProgressBar");
const learningPoints = document.getElementById("learningPoints");
const lectureList = document.getElementById("lectureList");
const learnerForm = document.getElementById("learnerForm");
const learnerNameInput = document.getElementById("learnerNameInput");
const resetLearningButton = document.getElementById("resetLearningButton");

let state = loadState();
let autoFeedEnabled = true;
let autoFeedTimer = null;
const playbackState = new Map();
let learningViewInitialized = false;

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return migrateState(parsed);
    }
  } catch (error) {
    console.warn("Failed to load saved state:", error);
  }

  return migrateState({
    members: starterMembers,
    tickerEvents: [
      createEvent("田中さん", 10, "週次課題提出"),
      createEvent("佐藤さん", 8, "他メンバー支援"),
      createEvent("中村さん", 20, "初案件獲得"),
    ],
    updatedAt: Date.now(),
  });
}

function migrateState(baseState) {
  const mergedProgress = {};
  lectureCatalog.forEach((lecture) => {
    mergedProgress[lecture.id] = Boolean(baseState.learningProgress?.[lecture.id]);
  });

  return {
    members: baseState.members ?? starterMembers,
    tickerEvents: baseState.tickerEvents ?? [],
    updatedAt: baseState.updatedAt ?? Date.now(),
    learnerName: baseState.learnerName ?? DEFAULT_LEARNER_NAME,
    learningProgress: mergedProgress,
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
  renderLearning();
}

function getCompletedLectureCount() {
  return lectureCatalog.filter((lecture) => state.learningProgress[lecture.id]).length;
}

function getLearningPointsTotal() {
  return lectureCatalog
    .filter((lecture) => state.learningProgress[lecture.id])
    .reduce((sum, lecture) => sum + lecture.points, 0);
}

function renderLearning() {
  learnerNameInput.value = state.learnerName;

  const completed = getCompletedLectureCount();
  const total = lectureCatalog.length;
  const progressPercent = Math.round((completed / total) * 100);
  const earnedPoints = getLearningPointsTotal();

  learningSummary.textContent = `${completed}/${total} 講座を完了（${progressPercent}%）`;
  learningProgressBar.style.width = `${progressPercent}%`;
  learningPoints.textContent = `${state.learnerName}の講座視聴ポイント: ${earnedPoints} pt`;

  if (!learningViewInitialized) {
    lectureList.innerHTML = "";
    lectureCatalog.forEach((lecture) => {
      const done = state.learningProgress[lecture.id];
      const card = document.createElement("article");
      card.className = `lecture-card ${done ? "done" : ""}`;
      card.dataset.lectureCardId = lecture.id;
      const tracking = playbackState.get(lecture.id);
      const trackedSeconds = tracking ? Math.floor(tracking.trackedSeconds) : 0;
      const safetyReady = tracking?.safetyReady ?? false;
      card.innerHTML = `
        <p class="lecture-card-title">${lecture.title}</p>
        <p class="lecture-card-meta">完了で ${lecture.points}pt 獲得（自動判定）</p>
        <video
          class="lecture-player"
          controls
          preload="metadata"
          playsinline
          data-lecture-id="${lecture.id}"
          src="${lecture.src}"
        ></video>
        <p class="lecture-status" data-watch-progress>
          視聴進捗: ${trackedSeconds}秒 / 最低${lecture.minWatchSeconds}秒
          ${safetyReady ? "・判定条件OK" : "・判定条件待ち"}
        </p>
        <p class="lecture-status">
          判定条件: 95%以上視聴 + 最低再生時間を満たす + 早送りのみで終わらせない
        </p>
        <p class="lecture-status ${done ? "done" : ""}" data-auto-status>
          ${done ? "この講座は自動付与済みです" : "再生完了時に自動でポイント付与されます"}
        </p>
      `;
      lectureList.appendChild(card);
    });

    bindLectureVideoEvents();
    learningViewInitialized = true;
  }

  updateLearningCards();
}

function updateLearningCards() {
  lectureCatalog.forEach((lecture) => {
    const card = lectureList.querySelector(`[data-lecture-card-id="${lecture.id}"]`);
    if (!card) {
      return;
    }

    const done = state.learningProgress[lecture.id];
    const tracking = playbackState.get(lecture.id);
    const trackedSeconds = tracking ? Math.floor(tracking.trackedSeconds) : 0;
    const safetyReady = tracking?.safetyReady ?? false;
    const progressNode = card.querySelector("[data-watch-progress]");
    const autoStatusNode = card.querySelector("[data-auto-status]");

    card.classList.toggle("done", done);
    if (progressNode) {
      progressNode.textContent = `視聴進捗: ${trackedSeconds}秒 / 最低${lecture.minWatchSeconds}秒 ${
        safetyReady ? "・判定条件OK" : "・判定条件待ち"
      }`;
    }
    if (autoStatusNode) {
      autoStatusNode.textContent = done
        ? "この講座は自動付与済みです"
        : "再生完了時に自動でポイント付与されます";
      autoStatusNode.classList.toggle("done", done);
    }
  });
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

function getOrCreatePlayback(lectureId) {
  if (!playbackState.has(lectureId)) {
    playbackState.set(lectureId, {
      maxWatchedTime: 0,
      trackedSeconds: 0,
      lastTickAt: null,
      wasPlaying: false,
      safetyReady: false,
    });
  }
  return playbackState.get(lectureId);
}

function bindLectureVideoEvents() {
  const videos = lectureList.querySelectorAll("video[data-lecture-id]");
  videos.forEach((video) => {
    const lectureId = video.dataset.lectureId;
    if (!lectureId || video.dataset.bound === "true") {
      return;
    }
    video.dataset.bound = "true";
    const playback = getOrCreatePlayback(lectureId);

    video.addEventListener("play", () => {
      playback.wasPlaying = true;
      playback.lastTickAt = Date.now();
    });

    video.addEventListener("pause", () => {
      playback.wasPlaying = false;
      playback.lastTickAt = null;
    });

    video.addEventListener("timeupdate", () => {
      const lecture = lectureCatalog.find((item) => item.id === lectureId);
      if (!lecture || !Number.isFinite(video.duration) || video.duration <= 0) {
        return;
      }

      const now = Date.now();
      if (playback.wasPlaying && playback.lastTickAt) {
        const deltaSeconds = Math.max(0, (now - playback.lastTickAt) / 1000);
        if (deltaSeconds <= 1.2) {
          playback.trackedSeconds += deltaSeconds;
        }
      }
      playback.lastTickAt = now;

      const seekDetected = video.currentTime - playback.maxWatchedTime > SEEK_TOLERANCE_SECONDS;
      if (!seekDetected) {
        playback.maxWatchedTime = Math.max(playback.maxWatchedTime, video.currentTime);
      }

      if (playback.trackedSeconds >= lecture.minWatchSeconds) {
        playback.safetyReady = true;
      }

      maybeAwardLectureCompletion(lecture, video, playback);
      updateLearningCards();
    });

    video.addEventListener("ended", () => {
      const lecture = lectureCatalog.find((item) => item.id === lectureId);
      if (!lecture) {
        return;
      }
      maybeAwardLectureCompletion(lecture, video, playback, true);
      updateLearningCards();
    });
  });
}

function maybeAwardLectureCompletion(lecture, video, playback, endedEvent = false) {
  if (state.learningProgress[lecture.id]) {
    return;
  }
  if (!Number.isFinite(video.duration) || video.duration <= 0) {
    return;
  }

  const ratio = playback.maxWatchedTime / video.duration;
  const thresholdReached = ratio >= VIDEO_COMPLETE_THRESHOLD;
  const minWatchReached = playback.trackedSeconds >= lecture.minWatchSeconds;
  const nearEnd = video.currentTime >= video.duration - 0.7;

  const canAward = thresholdReached && minWatchReached && (nearEnd || endedEvent);
  if (!canAward) {
    return;
  }

  state.learningProgress[lecture.id] = true;
  addPoints(state.learnerName, lecture.points, `${lecture.title}を視聴完了`);
}

learnerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const candidate = learnerNameInput.value.trim();
  if (!candidate) {
    return;
  }
  state.learnerName = candidate;
  state.updatedAt = Date.now();
  persistState();
  render();
});

resetLearningButton.addEventListener("click", () => {
  if (!window.confirm("学習進捗をリセットしますか？")) {
    return;
  }

  const emptyProgress = {};
  lectureCatalog.forEach((lecture) => {
    emptyProgress[lecture.id] = false;
  });
  state.learningProgress = emptyProgress;
  playbackState.clear();
  state.updatedAt = Date.now();
  state.tickerEvents.unshift(createEvent("システム", 0, "学習進捗をリセット"));
  state.tickerEvents = state.tickerEvents.slice(0, MAX_TICKER_ITEMS);
  persistState();
  render();
});

resetButton.addEventListener("click", () => {
  if (!window.confirm("今週のランキングを本当にリセットしますか？")) {
    return;
  }

  state = {
    members: starterMembers.map((member) => ({ ...member, points: 0 })),
    tickerEvents: [createEvent("システム", 0, "週間ランキングをリセット")],
    updatedAt: Date.now(),
    learnerName: state.learnerName,
    learningProgress: state.learningProgress,
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
