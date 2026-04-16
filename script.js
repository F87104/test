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
  "なっちゃん",
  "みーちゃん",
  "ゆいぴ",
  "あやのん",
  "りーちゃん",
  "ももちゃん",
  "ここちゃん",
  "さくちゃん",
  "ひなぴ",
  "まいまい",
  "あおちゃん",
  "るなちゃん",
  "ゆきりん",
  "かなちゃん",
  "みおりん",
  "りんちゃん",
  "はるちゃん",
  "のんちゃん",
  "ちーちゃん",
  "しおりん",
  "ななちゃん",
  "いちかちゃん",
  "ふうちゃん",
  "こはるん",
  "えまちゃん",
  "すずちゃん",
  "あかりん",
  "きらちゃん",
  "みくちゃん",
  "ゆめちゃん",
];

const rewardCatalog = [
  { id: "priority-review", title: "優先レビュー権", cost: 40, description: "次回レビューの優先枠" },
  {
    id: "special-template",
    title: "限定テンプレ解放",
    cost: 70,
    description: "上位会員向けテンプレを開放",
    requiredLeagues: ["silver", "gold"],
  },
  {
    id: "mentor-qa",
    title: "メンターQ&Aチケット",
    cost: 120,
    description: "個別質問を1回送信可能",
    requiredLeagues: ["gold"],
  },
];

const leagueTable = [
  { id: "bronze", title: "ブロンズリーグ", min: 0, max: 99, nextMin: 100 },
  { id: "silver", title: "シルバーリーグ", min: 100, max: 249, nextMin: 250 },
  { id: "gold", title: "ゴールドリーグ", min: 250, max: null, nextMin: null },
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
const mvpCard = document.getElementById("mvpCard");
const mvpNickname = document.getElementById("mvpNickname");
const mvpPoints = document.getElementById("mvpPoints");
const mvpTitle = document.getElementById("mvpTitle");
const mvpMessage = document.getElementById("mvpMessage");
const dailyFocusTitle = document.getElementById("dailyFocusTitle");
const dailyFocusDescription = document.getElementById("dailyFocusDescription");
const dailyFocusStatus = document.getElementById("dailyFocusStatus");
const dailyFocusAction = document.getElementById("dailyFocusAction");
const reactivationCard = document.getElementById("reactivationCard");
const reactivationMessage = document.getElementById("reactivationMessage");
const reactivationActionButton = document.getElementById("reactivationActionButton");
const weeklyReviewSummary = document.getElementById("weeklyReviewSummary");
const weeklyMetricProgress = document.getElementById("weeklyMetricProgress");
const weeklyMetricConsistency = document.getElementById("weeklyMetricConsistency");
const weeklyMetricNext = document.getElementById("weeklyMetricNext");
const rankingTabButtons = document.querySelectorAll("[data-ranking-tab]");
const learnerForm = document.getElementById("learnerForm");
const learnerNameInput = document.getElementById("learnerNameInput");
const resetLearningButton = document.getElementById("resetLearningButton");

let state = loadState();
let autoFeedEnabled = true;
let autoFeedTimer = null;
const playbackState = new Map();
let learningViewInitialized = false;
const vimeoPlayers = new Map();
let currentRankingTab = "overall";

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
      lastActivityTimestamp: baseState.gamification?.lastActivityTimestamp ?? null,
      completedQuests: baseState.gamification?.completedQuests ?? {},
    },
    joinedAtMap: baseState.joinedAtMap ?? {},
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
  if (normalizedName === state.learnerName) {
    state.gamification.lastActivityTimestamp = Date.now();
  }
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
  if (!state.joinedAtMap[realName]) {
    state.joinedAtMap[realName] = Date.now();
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

function getCurrentLeagueId() {
  const userPoints = getTotalPointsByLearner(state.learnerName);
  const league = getLeagueByPoints(userPoints);
  return league?.id ?? "bronze";
}

function getLeagueOrder(leagueId) {
  const map = { bronze: 1, silver: 2, gold: 3 };
  return map[leagueId] ?? 1;
}

function isRewardUnlockedForLeague(reward, leagueId) {
  if (!reward.requiredLeagues || reward.requiredLeagues.length === 0) {
    return true;
  }
  return reward.requiredLeagues.includes(leagueId);
}

function getCurrentWeekRange() {
  return getWeekRange(0);
}

function getMemberPointsInRange(memberName, range) {
  return state.tickerEvents
    .filter((event) => event.name === memberName && event.timestamp >= range.start.getTime() && event.timestamp <= range.end.getTime())
    .reduce((sum, event) => sum + event.points, 0);
}

function getGrowthRate(memberName) {
  const thisWeek = getPointsInRange(memberName, getWeekRange(0));
  const prevWeek = getPointsInRange(memberName, getWeekRange(-1));
  if (prevWeek <= 0) {
    return thisWeek > 0 ? 999 : 0;
  }
  return ((thisWeek - prevWeek) / prevWeek) * 100;
}

function getContributionScore(memberName) {
  const range = getCurrentWeekRange();
  return state.tickerEvents
    .filter(
      (event) =>
        event.name === memberName &&
        event.timestamp >= range.start.getTime() &&
        event.timestamp <= range.end.getTime() &&
        (event.reason.includes("支援") || event.reason.includes("クエスト達成"))
    )
    .reduce((sum, event) => sum + event.points, 0);
}

function getSortedMembersByTab(tabId) {
  const members = [...state.members];
  if (tabId === "rookie" || tabId === "newcomer") {
    const now = Date.now();
    const fourteenDaysMs = 14 * 24 * 60 * 60 * 1000;
    const newcomers = members.filter((member) => now - (state.joinedAtMap[member.name] ?? now) <= fourteenDaysMs);
    return newcomers.sort((a, b) => b.points - a.points);
  }
  if (tabId === "growth") {
    return members.sort((a, b) => getGrowthRate(b.name) - getGrowthRate(a.name));
  }
  if (tabId === "contribution") {
    return members.sort((a, b) => getContributionScore(b.name) - getContributionScore(a.name));
  }
  return members.sort((a, b) => b.points - a.points);
}

function renderRanking() {
  rankingList.innerHTML = "";

  const sorted = getSortedMembersByTab(currentRankingTab);

  sorted.forEach((member, index) => {
    const nickname = getDisplayName(member.name);
    let scoreLabel = `${member.points} pt`;
    if (currentRankingTab === "growth") {
      const rate = getGrowthRate(member.name);
      scoreLabel = `${rate >= 0 ? "+" : ""}${Math.round(rate)}%`;
    } else if (currentRankingTab === "contribution") {
      scoreLabel = `${getContributionScore(member.name)} pt`;
    }
    const row = document.createElement("li");
    row.className = `ranking-row ${index < 3 ? "top3" : ""}`;
    row.innerHTML = `
      <span class="ranking-position">${index + 1}</span>
      <span class="ranking-name">${nickname}</span>
      <span class="ranking-points">${scoreLabel}</span>
    `;
    rankingList.appendChild(row);
  });

  rankingTabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.rankingTab === currentRankingTab);
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
  renderMvpCard();
  renderTicker();
  renderUpdatedAt();
  renderDailyFocus();
  renderWeeklyReview();
  renderReactivation();
  renderLearning();
  renderGamification();
  renderLeagueAndRewards();
}

function getTopMember() {
  if (!state.members.length) {
    return null;
  }
  const sorted = [...state.members].sort((a, b) => b.points - a.points);
  return sorted[0] ?? null;
}

function getMvpTitle(points) {
  if (points >= 300) {
    return "レジェンド開拓者";
  }
  if (points >= 200) {
    return "スターランナー";
  }
  if (points >= 100) {
    return "今週の急成長株";
  }
  return "今週のファーストブースト";
}

function renderMvpCard() {
  if (!mvpCard || !mvpNickname || !mvpPoints || !mvpTitle || !mvpMessage) {
    return;
  }
  const topMember = getTopMember();
  if (!topMember) {
    mvpNickname.textContent = "未定";
    mvpPoints.textContent = "0 pt";
    mvpTitle.textContent = "MVP準備中";
    mvpMessage.textContent = "今週の行動で最初のMVPを目指そう";
    mvpCard.classList.remove("is-gold", "is-silver", "is-bronze");
    return;
  }

  const nickname = getDisplayName(topMember.name);
  mvpNickname.textContent = nickname;
  mvpPoints.textContent = `${topMember.points} pt`;
  mvpTitle.textContent = getMvpTitle(topMember.points);
  mvpMessage.textContent = `${nickname}さんが今週トップを走っています。追い上げで逆転を狙おう。`;

  mvpCard.classList.remove("is-gold", "is-silver", "is-bronze");
  if (topMember.points >= 250) {
    mvpCard.classList.add("is-gold");
  } else if (topMember.points >= 100) {
    mvpCard.classList.add("is-silver");
  } else {
    mvpCard.classList.add("is-bronze");
  }
}

function refreshMvpCardVisual(topMember) {
  if (!mvpCard || !mvpNickname || !mvpPoints || !mvpTitle) {
    return;
  }
  if (!topMember) {
    mvpNickname.textContent = "未定";
    mvpTitle.textContent = "MVP準備中";
    mvpPoints.textContent = "0 pt";
    mvpCard.classList.remove("is-gold", "is-silver", "is-bronze");
    return;
  }
  const nickname = getDisplayName(topMember.name);
  mvpNickname.textContent = nickname;
  mvpTitle.textContent = getMvpTitle(topMember.points);
  mvpPoints.textContent = `${topMember.points} pt`;
  mvpCard.classList.remove("is-gold", "is-silver", "is-bronze");
  if (topMember.points >= 250) {
    mvpCard.classList.add("is-gold");
  } else if (topMember.points >= 100) {
    mvpCard.classList.add("is-silver");
  } else {
    mvpCard.classList.add("is-bronze");
  }
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

function getTodayCompletedLectureCount() {
  const today = getTodayKey();
  return state.tickerEvents.filter((event) => {
    const key = new Date(event.timestamp).toISOString().slice(0, 10);
    return key === today && event.name === state.learnerName && event.reason.includes("視聴完了");
  }).length;
}

function getMemberGrowthMap() {
  const thisWeek = getWeekRange(0);
  const prevWeek = getWeekRange(-1);
  const map = {};
  state.members.forEach((member) => {
    const current = getPointsInRange(member.name, thisWeek);
    const previous = getPointsInRange(member.name, prevWeek);
    map[member.name] = current - previous;
  });
  return map;
}

function getContributionScoreMap() {
  const thisWeek = getWeekRange(0);
  const map = {};
  state.members.forEach((member) => {
    const supportCount = state.tickerEvents.filter((event) => {
      if (event.name !== member.name) return false;
      if (event.timestamp < thisWeek.start.getTime() || event.timestamp > thisWeek.end.getTime()) return false;
      return event.reason.includes("支援");
    }).length;
    map[member.name] = supportCount * 10 + getPointsInRange(member.name, thisWeek);
  });
  return map;
}

function getRankingViewMembers() {
  const all = [...state.members];
  if (currentRankingTab === "all") {
    return all.sort((a, b) => b.points - a.points);
  }
  if (currentRankingTab === "rookie") {
    const thisWeek = getWeekRange(0);
    return all
      .filter((member) => {
        const firstEvent = state.tickerEvents
          .filter((event) => event.name === member.name)
          .sort((a, b) => a.timestamp - b.timestamp)[0];
        return firstEvent ? firstEvent.timestamp >= thisWeek.start.getTime() : false;
      })
      .sort((a, b) => b.points - a.points);
  }
  if (currentRankingTab === "growth") {
    const growthMap = getMemberGrowthMap();
    return all.sort((a, b) => (growthMap[b.name] ?? -9999) - (growthMap[a.name] ?? -9999));
  }
  if (currentRankingTab === "contribution") {
    const contributionMap = getContributionScoreMap();
    return all.sort((a, b) => (contributionMap[b.name] ?? -9999) - (contributionMap[a.name] ?? -9999));
  }
  return all.sort((a, b) => b.points - a.points);
}

function getFocusTask() {
  const completedTotal = getCompletedLectureCount();
  const todayPoints = getTodayEarnedPoints();
  const hasManualSubmit = getTodayActionCount("manual-submit") > 0;
  const userPoints = getTotalPointsByLearner(state.learnerName);
  const cheapestReward = Math.min(...rewardCatalog.map((item) => item.cost));

  if (completedTotal === 0) {
    return {
      title: "最初の講座を1本完了する",
      description: "まずは講座を1本見終えて、初回ポイントを獲得しましょう。",
      status: "未達成",
      actionLabel: "学習進捗へ移動",
      targetId: "learningSummary",
    };
  }

  if (todayPoints < 30) {
    return {
      title: "今日30ptを達成する",
      description: "視聴完了や投稿で、あとポイントを積み上げましょう。",
      status: `${todayPoints}/30pt`,
      actionLabel: "ポイントを積む",
      targetId: "rankingList",
    };
  }

  if (!hasManualSubmit) {
    return {
      title: "今日の投稿を1回実行する",
      description: "ポイント付与フォームから1回投稿して、行動記録を残しましょう。",
      status: "未投稿",
      actionLabel: "投稿フォームへ",
      targetId: "awardForm",
    };
  }

  if (userPoints >= cheapestReward) {
    return {
      title: "報酬を1つ交換する",
      description: "交換所で特典を受け取り、行動の報酬を体験しましょう。",
      status: `所持 ${userPoints}pt`,
      actionLabel: "交換所へ",
      targetId: "rewardList",
    };
  }

  return {
    title: "明日に向けて講座を1本進める",
    description: "明日のスタートを軽くするために、次の講座を先に視聴しましょう。",
    status: "おすすめ",
    actionLabel: "学習へ",
    targetId: "lectureList",
  };
}

function renderDailyFocus() {
  if (!dailyFocusTitle || !dailyFocusDescription || !dailyFocusStatus || !dailyFocusAction) {
    return;
  }
  const task = getFocusTask();
  dailyFocusTitle.textContent = task.title;
  dailyFocusDescription.textContent = task.description;
  dailyFocusStatus.textContent = `進捗: ${task.status}`;
  dailyFocusAction.textContent = task.actionLabel;
  dailyFocusAction.dataset.targetId = task.targetId;
}

function getWeekRange(offsetWeeks = 0) {
  const now = new Date();
  const currentDay = now.getDay();
  const diffToMonday = currentDay === 0 ? -6 : 1 - currentDay;
  const monday = new Date(now);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(monday.getDate() + diffToMonday + offsetWeeks * 7);
  const sundayEnd = new Date(monday);
  sundayEnd.setDate(sundayEnd.getDate() + 7);
  sundayEnd.setMilliseconds(-1);
  return { start: monday, end: sundayEnd };
}

function getPointsInRange(name, range) {
  return state.tickerEvents
    .filter((event) => event.name === name && event.timestamp >= range.start.getTime() && event.timestamp <= range.end.getTime())
    .reduce((sum, event) => sum + event.points, 0);
}

function getLastActivityTimestamp() {
  if (typeof state.gamification.lastActivityTimestamp === "number") {
    return state.gamification.lastActivityTimestamp;
  }
  const memberEvents = state.tickerEvents
    .filter((event) => event.name === state.learnerName)
    .sort((a, b) => b.timestamp - a.timestamp);
  return memberEvents[0]?.timestamp ?? null;
}

function renderReactivation() {
  if (!reactivationCard || !reactivationMessage || !reactivationActionButton) {
    return;
  }
  const lastActivity = getLastActivityTimestamp();
  if (!lastActivity) {
    reactivationCard.hidden = true;
    return;
  }
  const now = Date.now();
  const daysInactive = Math.floor((now - lastActivity) / (24 * 60 * 60 * 1000));
  if (daysInactive < 3) {
    reactivationCard.hidden = true;
    return;
  }

  reactivationCard.hidden = false;
  reactivationMessage.textContent = `${daysInactive}日ぶりです。復帰ミッション（講座1本＋10pt投稿）で流れを取り戻しましょう。`;
  reactivationActionButton.dataset.targetId = "lectureList";
}

function getRankPosition(name) {
  const sorted = [...state.members].sort((a, b) => b.points - a.points);
  const idx = sorted.findIndex((member) => member.name === name);
  return idx >= 0 ? idx + 1 : null;
}

function renderWeeklyReview() {
  if (!weeklyReviewSummary || !weeklyMetricProgress || !weeklyMetricConsistency || !weeklyMetricNext) {
    return;
  }
  const currentWeek = getWeekRange(0);
  const prevWeek = getWeekRange(-1);
  const thisWeekPoints = getPointsInRange(state.learnerName, currentWeek);
  const lastWeekPoints = getPointsInRange(state.learnerName, prevWeek);
  const diff = thisWeekPoints - lastWeekPoints;
  const rank = getRankPosition(state.learnerName);
  const lectureDoneToday = getTodayCompletedLectureCount();

  weeklyReviewSummary.textContent = `${state.learnerName}の今週サマリー: ${thisWeekPoints}pt（先週比 ${diff >= 0 ? "+" : ""}${diff}pt）`;
  weeklyMetricProgress.textContent = `成長量: 今週 ${thisWeekPoints}pt / 先週 ${lastWeekPoints}pt`;
  weeklyMetricConsistency.textContent = `継続: ${state.gamification.streak}日連続・本日講座完了 ${lectureDoneToday}本`;
  weeklyMetricNext.textContent = `次の一手: ${
    rank ? `現在${rank}位。` : ""
  } 今日の最重要タスクを完了して、明日も継続しましょう。`;
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
  playerXp.textContent = `${levelState.progress} / ${levelState.required} 経験値`;
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
    { id: "first-lecture", title: "はじめてクリア", unlocked: getCompletedLectureCount() >= 1 },
    { id: "three-lecture", title: "学習ランナー", unlocked: getCompletedLectureCount() >= 3 },
    { id: "streak-3", title: "3日連続達成", unlocked: state.gamification.streak >= 3 },
    { id: "xp-300", title: "経験値300以上", unlocked: totalPoints >= 300 },
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
  const currentLeagueId = league.id;
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
    const unlocked = isRewardUnlockedForLeague(reward, currentLeagueId);
    const canBuy = unlocked && userPoints >= reward.cost;
    const requiredText = reward.requiredLeagues?.length
      ? ` / 条件: ${reward.requiredLeagues.map((id) => leagueTable.find((l) => l.id === id)?.title ?? id).join("・")}`
      : "";
    const item = document.createElement("article");
    item.className = `reward-item ${unlocked ? "" : "locked"}`;
    item.innerHTML = `
      <div>
        <p class="reward-title">${reward.title}</p>
        <p class="reward-meta">必要: ${reward.cost}pt / 所持: ${claimed}個${requiredText}</p>
        ${unlocked ? "" : `<p class="reward-lock">現在のリーグでは未解放</p>`}
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
  const currentLeagueId = getCurrentLeagueId();
  if (!isRewardUnlockedForLeague(reward, currentLeagueId)) {
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

if (rankingTabButtons.length > 0) {
  rankingTabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tabId = button.dataset.rankingTab;
      if (!tabId || tabId === currentRankingTab) {
        return;
      }
      currentRankingTab = tabId;
      renderRanking();
    });
  });
}

if (reactivationActionButton) {
  reactivationActionButton.addEventListener("click", () => {
    const targetId = reactivationActionButton.dataset.targetId;
    if (!targetId) {
      return;
    }
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

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
  state.gamification.lastActivityTimestamp = null;
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
    nicknameMap: state.nicknameMap,
    rewardInventory: state.rewardInventory,
    gamification: state.gamification,
    joinedAtMap: state.joinedAtMap,
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
  autoFeedButton.textContent = `自動速報: ${enabled ? "オン" : "オフ"}`;
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

if (dailyFocusAction) {
  dailyFocusAction.addEventListener("click", () => {
    const targetId = dailyFocusAction.dataset.targetId;
    if (!targetId) {
      return;
    }
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

render();
setAutoFeed(true);
