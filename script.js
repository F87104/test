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
    vimeoId: "76979871",
  },
  {
    id: "lec-2",
    title: "講座2: ターゲット設定",
    points: 15,
    minWatchSeconds: 45,
    vimeoId: "22439234",
  },
  {
    id: "lec-3",
    title: "講座3: オファー設計",
    points: 20,
    minWatchSeconds: 50,
    vimeoId: "146022717",
  },
  {
    id: "lec-4",
    title: "講座4: LP作成の基本",
    points: 18,
    minWatchSeconds: 50,
    vimeoId: "357274789",
  },
  {
    id: "lec-5",
    title: "講座5: 初提案の作り方",
    points: 22,
    minWatchSeconds: 55,
    vimeoId: "76979871",
  },
  {
    id: "lec-6",
    title: "講座6: 改善ループ運用",
    points: 25,
    minWatchSeconds: 60,
    vimeoId: "22439234",
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
const nicknamePool = [
  "StarFox",
  "BlueNova",
  "PixelWolf",
  "SkyBeat",
  "MintRider",
  "NeoSpark",
  "RubyDash",
  "LunaCore",
  "CloudAce",
  "FlashKey",
  "AquaRay",
  "CosmoLink",
  "VioletArc",
  "EchoMint",
  "GlintRoad",
];

const rewardCatalog = [
  { id: "priority-review", title: "優先レビュー権", cost: 40, description: "次回レビューの優先枠" },
  { id: "special-template", title: "限定テンプレ解放", cost: 70, description: "上位会員向けテンプレを開放" },
  { id: "mentor-qa", title: "メンターQ&Aチケット", cost: 120, description: "個別質問を1回送信可能" },
];

const leagueTable = [
  { id: "bronze", title: "Bronze League", min: 0, max: 99, nextMin: 100 },
  { id: "silver", title: "Silver League", min: 100, max: 249, nextMin: 250 },
  { id: "gold", title: "Gold League", min: 250, max: null, nextMin: null },
];

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
const playerLevel = document.getElementById("playerLevel");
const playerXp = document.getElementById("playerXp");
const playerStreak = document.getElementById("playerStreak");
const playerXpBar = document.getElementById("playerXpBar");
const questList = document.getElementById("questList");
const badgeList = document.getElementById("badgeList");
const currentLeagueLabel = document.getElementById("currentLeagueLabel");
const leagueProgressBar = document.getElementById("leagueProgressBar");
const leagueProgressText = document.getElementById("leagueProgressText");
const badgeBronze = document.getElementById("badgeBronze");
const badgeSilver = document.getElementById("badgeSilver");
const badgeGold = document.getElementById("badgeGold");
const rewardBalance = document.getElementById("rewardBalance");
const rewardList = document.getElementById("rewardList");
const learnerForm = document.getElementById("learnerForm");
const learnerNameInput = document.getElementById("learnerNameInput");
const resetLearningButton = document.getElementById("resetLearningButton");

let state = loadState();
let autoFeedEnabled = true;
let autoFeedTimer = null;
const playbackState = new Map();
let learningViewInitialized = false;
const vimeoPlayers = new Map();

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
    nicknameMap: baseState.nicknameMap ?? {},
    rewardInventory: baseState.rewardInventory ?? {},
    gamification: {
      streak: baseState.gamification?.streak ?? 0,
      lastActivityDate: baseState.gamification?.lastActivityDate ?? null,
      completedQuests: baseState.gamification?.completedQuests ?? {},
    },
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
  ensureNickname(normalizedName);
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

function getRandomNickname() {
  const used = new Set(Object.values(state.nicknameMap));
  const available = nicknamePool.filter((name) => !used.has(name));
  const base = available[Math.floor(Math.random() * available.length)] ?? "Player";
  if (!used.has(base)) {
    return base;
  }
  return `${base}${Math.floor(Math.random() * 900 + 100)}`;
}

function ensureNickname(realName) {
  if (!realName) {
    return "Player";
  }
  if (!state.nicknameMap[realName]) {
    state.nicknameMap[realName] = getRandomNickname();
  }
  return state.nicknameMap[realName];
}

function getDisplayName(realName) {
  return ensureNickname(realName);
}

function formatTickerMessage(event) {
  const displayName = getDisplayName(event.name);
  if (event.points < 0) {
    return `${displayName}が${event.reason}で${Math.abs(event.points)}pt消費しました（${formatTimestamp(
      event.timestamp
    )}）`;
  }
  return `${displayName}が${event.reason}で${event.points}pt獲得しました（${formatTimestamp(
    event.timestamp
  )}）`;
}

function getLeagueByPoints(points) {
  return leagueTable.find((league) => points >= league.min && (league.max === null || points <= league.max));
}

function renderRanking() {
  rankingList.innerHTML = "";

  const sorted = [...state.members].sort((a, b) => b.points - a.points);

  sorted.forEach((member, index) => {
    const nickname = getDisplayName(member.name);
    const row = document.createElement("li");
    row.className = `ranking-row ${index < 3 ? "top3" : ""}`;
    row.innerHTML = `
      <span class="ranking-position">${index + 1}</span>
      <span class="ranking-name">${nickname}</span>
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
    item.textContent = formatTickerMessage(event);
    tickerTrack.appendChild(item);
  });
}

function renderUpdatedAt() {
  lastUpdated.textContent = `最終更新: ${formatTimestamp(state.updatedAt)}`;
}

function ensureNicknamesForMembers() {
  let changed = false;
  state.members.forEach((member) => {
    if (!state.nicknameMap[member.name]) {
      state.nicknameMap[member.name] = getRandomNickname();
      changed = true;
    }
  });
  if (changed) {
    persistState();
  }
}

function render() {
  ensureNicknamesForMembers();
  renderRanking();
  renderTicker();
  renderUpdatedAt();
  renderLearning();
  renderGamification();
  renderLeagueAndRewards();
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
        <iframe
          class="lecture-player"
          data-lecture-id="${lecture.id}"
          src="https://player.vimeo.com/video/${lecture.vimeoId}?title=0&byline=0&portrait=0&dnt=1"
          allow="autoplay; fullscreen; picture-in-picture; clipboard-write; encrypted-media; web-share"
          title="${lecture.title}"
          frameborder="0"
          allowfullscreen
        ></iframe>
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

    bindLecturePlayerEvents();
    learningViewInitialized = true;
  }

  updateLearningCards();
}

function getTotalPointsByLearner(name) {
  const found = state.members.find((member) => member.name === name);
  return found ? found.points : 0;
}

function calculateLevel(points) {
  const level = Math.floor(points / 100) + 1;
  const currentLevelBase = (level - 1) * 100;
  const nextLevelBase = level * 100;
  const progress = points - currentLevelBase;
  const required = nextLevelBase - currentLevelBase;
  return { level, progress, required };
}

function getTodayKey() {
  return new Date().toISOString().slice(0, 10);
}

function getYesterdayKey() {
  const date = new Date();
  date.setDate(date.getDate() - 1);
  return date.toISOString().slice(0, 10);
}

function getQuestDefinitions() {
  const watchedCount = getCompletedLectureCount();
  const quests = [
    {
      id: "watch-1",
      title: "講座を1本視聴完了",
      progress: Math.min(watchedCount, 1),
      target: 1,
      reward: 5,
    },
    {
      id: "earn-30",
      title: "本日30pt獲得",
      progress: Math.min(getTodayEarnedPoints(), 30),
      target: 30,
      reward: 8,
    },
    {
      id: "submit-once",
      title: "ポイント投稿を1回実行",
      progress: getTodayActionCount("manual-submit") > 0 ? 1 : 0,
      target: 1,
      reward: 5,
    },
  ];
  return quests;
}

function getTodayEarnedPoints() {
  const today = getTodayKey();
  return state.tickerEvents
    .filter((event) => {
      const key = new Date(event.timestamp).toISOString().slice(0, 10);
      return key === today && event.name === state.learnerName;
    })
    .reduce((sum, event) => sum + event.points, 0);
}

function getTodayActionCount(actionType) {
  const today = getTodayKey();
  return state.tickerEvents.filter((event) => {
    const key = new Date(event.timestamp).toISOString().slice(0, 10);
    return key === today && event.reason === actionType;
  }).length;
}

function updateStreak() {
  const today = getTodayKey();
  const yesterday = getYesterdayKey();
  const last = state.gamification.lastActivityDate;
  if (last === today) {
    return;
  }
  if (last === yesterday) {
    state.gamification.streak += 1;
  } else {
    state.gamification.streak = 1;
  }
  state.gamification.lastActivityDate = today;
}

function grantQuestRewards() {
  const quests = getQuestDefinitions();
  quests.forEach((quest) => {
    const done = quest.progress >= quest.target;
    if (!done || state.gamification.completedQuests[quest.id]) {
      return;
    }
    state.gamification.completedQuests[quest.id] = true;
    addPoints(state.learnerName, quest.reward, `クエスト達成:${quest.title}`);
  });
}

function renderGamification() {
  const totalPoints = getTotalPointsByLearner(state.learnerName);
  const levelState = calculateLevel(totalPoints);
  playerLevel.textContent = `Lv.${levelState.level}`;
  playerXp.textContent = `${levelState.progress} / ${levelState.required} XP`;
  playerStreak.textContent = `${state.gamification.streak} 日`;
  playerXpBar.style.width = `${Math.round((levelState.progress / levelState.required) * 100)}%`;

  const quests = getQuestDefinitions();
  questList.innerHTML = "";
  quests.forEach((quest) => {
    const done = quest.progress >= quest.target;
    const item = document.createElement("li");
    item.className = `quest-item ${done ? "done" : ""}`;
    item.innerHTML = `
      <div>
        <p class="quest-title">${quest.title}</p>
        <p class="quest-meta">${quest.progress}/${quest.target} ・報酬 ${quest.reward}pt</p>
      </div>
      <span class="quest-state">${done ? "達成" : "進行中"}</span>
    `;
    questList.appendChild(item);
  });

  const badges = [
    { id: "first-lecture", title: "First Clear", unlocked: getCompletedLectureCount() >= 1 },
    { id: "three-lecture", title: "Learning Runner", unlocked: getCompletedLectureCount() >= 3 },
    { id: "streak-3", title: "3 Days Streak", unlocked: state.gamification.streak >= 3 },
    { id: "xp-300", title: "XP 300+", unlocked: totalPoints >= 300 },
  ];
  badgeList.innerHTML = "";
  badges.forEach((badge) => {
    const item = document.createElement("li");
    item.className = `badge-item ${badge.unlocked ? "unlocked" : ""}`;
    item.textContent = badge.title;
    badgeList.appendChild(item);
  });
}

function renderLeagueAndRewards() {
  const userPoints = getTotalPointsByLearner(state.learnerName);
  const league = getLeagueByPoints(userPoints) ?? leagueTable[0];
  currentLeagueLabel.textContent = `${league.title} (${userPoints}pt)`;

  badgeBronze.classList.toggle("active", league.id === "bronze");
  badgeSilver.classList.toggle("active", league.id === "silver");
  badgeGold.classList.toggle("active", league.id === "gold");

  if (league.nextMin === null) {
    leagueProgressBar.style.width = "100%";
    leagueProgressText.textContent = "最高リーグ到達中";
  } else {
    const range = league.nextMin - league.min;
    const current = Math.max(0, Math.min(range, userPoints - league.min));
    const percent = Math.round((current / range) * 100);
    leagueProgressBar.style.width = `${percent}%`;
    leagueProgressText.textContent = `次のリーグまで ${Math.max(0, league.nextMin - userPoints)}pt`;
  }

  rewardBalance.textContent = `交換可能ポイント: ${userPoints}pt`;
  rewardList.innerHTML = "";
  rewardCatalog.forEach((reward) => {
    const claimed = state.rewardInventory[reward.id] ?? 0;
    const canBuy = userPoints >= reward.cost;
    const item = document.createElement("article");
    item.className = "reward-item";
    item.innerHTML = `
      <div>
        <p class="reward-title">${reward.title}</p>
        <p class="reward-meta">必要: ${reward.cost}pt / 所持: ${claimed}個</p>
      </div>
      <button class="button button-small" type="button" data-reward-id="${reward.id}" ${
        canBuy ? "" : "disabled"
      }>
        交換
      </button>
    `;
    rewardList.appendChild(item);
  });
}

function spendPoints(name, points, reason) {
  const existing = state.members.find((member) => member.name === name);
  if (!existing || existing.points < points) {
    return false;
  }
  existing.points -= points;
  state.tickerEvents.unshift(createEvent(name, -points, reason));
  state.tickerEvents = state.tickerEvents.slice(0, MAX_TICKER_ITEMS);
  state.updatedAt = Date.now();
  persistState();
  render();
  return true;
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

  updateStreak();
  addPoints(name, points, reason);
  addPoints("システム", 0, "manual-submit");
  grantQuestRewards();
  persistState();
  awardForm.reset();
  pointsInput.value = "10";
  nameInput.focus();
});

rewardList.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }
  const rewardId = target.dataset.rewardId;
  const reward = rewardCatalog.find((item) => item.id === rewardId);
  if (!reward) {
    return;
  }
  const success = spendPoints(state.learnerName, reward.cost, `報酬交換:${reward.title}`);
  if (!success) {
    return;
  }
  state.rewardInventory[reward.id] = (state.rewardInventory[reward.id] ?? 0) + 1;
  persistState();
  render();
});

function getOrCreatePlayback(lectureId) {
  if (!playbackState.has(lectureId)) {
    playbackState.set(lectureId, {
      maxWatchedTime: 0,
      trackedSeconds: 0,
      lastKnownSeconds: null,
      safetyReady: false,
    });
  }
  return playbackState.get(lectureId);
}

function bindLecturePlayerEvents() {
  if (!window.Vimeo || typeof window.Vimeo.Player !== "function") {
    console.warn("Vimeo Player API not loaded");
    return;
  }

  const frames = lectureList.querySelectorAll("iframe[data-lecture-id]");
  frames.forEach((frame) => {
    const lectureId = frame.dataset.lectureId;
    if (!lectureId || frame.dataset.bound === "true") {
      return;
    }
    frame.dataset.bound = "true";

    const lecture = lectureCatalog.find((item) => item.id === lectureId);
    if (!lecture) {
      return;
    }
    const playback = getOrCreatePlayback(lectureId);
    const player = new window.Vimeo.Player(frame);
    vimeoPlayers.set(lectureId, player);

    player.on("timeupdate", (data) => {
      const seconds = Number(data.seconds);
      const duration = Number(data.duration);
      if (!Number.isFinite(seconds) || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      const previous = playback.lastKnownSeconds;
      if (typeof previous === "number") {
        const delta = seconds - previous;
        if (delta >= 0 && delta <= 1.6) {
          playback.trackedSeconds += delta;
          playback.maxWatchedTime = Math.max(playback.maxWatchedTime, seconds);
        }
      } else {
        playback.maxWatchedTime = Math.max(playback.maxWatchedTime, seconds);
      }
      playback.lastKnownSeconds = seconds;

      if (playback.trackedSeconds >= lecture.minWatchSeconds) {
        playback.safetyReady = true;
      }

      maybeAwardLectureCompletion(lecture, playback, duration, seconds, false);
      updateLearningCards();
    });

    player.on("seeked", (data) => {
      const seconds = Number(data.seconds);
      const previous = playback.lastKnownSeconds;
      if (typeof previous === "number" && seconds - previous > SEEK_TOLERANCE_SECONDS) {
        // Jump detected: do not count jumped range as watched.
        playback.lastKnownSeconds = seconds;
        return;
      }
      playback.lastKnownSeconds = seconds;
    });

    player.on("ended", async () => {
      let duration = playback.maxWatchedTime;
      try {
        duration = Number(await player.getDuration()) || duration;
      } catch (error) {
        console.warn("Failed to read Vimeo duration:", error);
      }
      maybeAwardLectureCompletion(lecture, playback, duration, duration, true);
      updateLearningCards();
    });
  });
}

function maybeAwardLectureCompletion(lecture, playback, duration, currentSeconds, endedEvent = false) {
  if (state.learningProgress[lecture.id]) {
    return;
  }
  if (!Number.isFinite(duration) || duration <= 0) {
    return;
  }

  const ratio = playback.maxWatchedTime / duration;
  const thresholdReached = ratio >= VIDEO_COMPLETE_THRESHOLD;
  const minWatchReached = playback.trackedSeconds >= lecture.minWatchSeconds;
  const nearEnd = currentSeconds >= duration - 1;

  const canAward = thresholdReached && minWatchReached && (nearEnd || endedEvent);
  if (!canAward) {
    return;
  }

  state.learningProgress[lecture.id] = true;
  updateStreak();
  addPoints(state.learnerName, lecture.points, `${lecture.title}を視聴完了`);
  grantQuestRewards();
  persistState();
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
  vimeoPlayers.clear();
  learningViewInitialized = false;
  lectureList.innerHTML = "";
  state.gamification.completedQuests = {};
  state.gamification.streak = 0;
  state.gamification.lastActivityDate = null;
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
