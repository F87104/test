import {
  awardPoints,
  createMissionTeam,
  fetchMissionMatches,
  fetchMissionProfile,
  fetchMissionTeams,
  fetchReview,
  fetchState,
  getAuthToken,
  login,
  saveMissionProfile,
} from "./src/shared/client.js";
import { connectRealtime, disconnectRealtime } from "./src/shared/realtime.js";
import { mapApiStateToUiState, mergeWeeklyReviewToDom } from "./src/shared/stateMapper.js";

const DEFAULT_LEARNER_NAME = "あなた";
const RANKING_VISIBLE_COUNT = 4;
const CUSTOMER_LOGIN_EMAIL = "member@example.com";
const CUSTOMER_LOGIN_PASSWORD = "member1234";
const LECTURE_PROGRESS_THRESHOLD = 0.95;

const lectureCatalog = [
  {
    id: "lecture-note-01",
    title: "講座1: メモで価値を言語化する基礎",
    vimeoId: "76979871",
    minutes: 6,
    points: 15,
  },
  {
    id: "lecture-note-02",
    title: "講座2: 自己紹介を商品ページ化する",
    vimeoId: "22439234",
    minutes: 7,
    points: 20,
  },
  {
    id: "lecture-note-03",
    title: "講座3: 1週間レビューで改善サイクルを回す",
    vimeoId: "146022717",
    minutes: 8,
    points: 25,
  },
  {
    id: "lecture-special-01",
    title: "特別講義: 成果導線の設計（報酬交換で解放）",
    vimeoId: "395212534",
    minutes: 10,
    points: 35,
    lockedByReward: "special-template",
  },
];

const rewardCatalog = [
  { id: "priority-review", title: "優先レビュー権", cost: 40, requiredLeagues: [] },
  { id: "special-template", title: "限定テンプレ解放", cost: 70, requiredLeagues: [] },
  { id: "mentor-qa", title: "メンターQ&Aチケット", cost: 120, requiredLeagues: ["gold"] },
];

const leagueTable = [
  { id: "bronze", title: "ブロンズリーグ", min: 0, max: 99, nextMin: 100 },
  { id: "silver", title: "シルバーリーグ", min: 100, max: 249, nextMin: 250 },
  { id: "gold", title: "ゴールドリーグ", min: 250, max: null, nextMin: null },
];

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
];

const els = {
  rankingList: document.getElementById("rankingList"),
  lastUpdated: document.getElementById("lastUpdated"),
  tickerTrack: document.getElementById("tickerTrack"),
  currentLeagueLabel: document.getElementById("currentLeagueLabel"),
  leagueProgressBar: document.getElementById("leagueProgressBar"),
  leagueProgressText: document.getElementById("leagueProgressText"),
  badgeBronze: document.getElementById("badgeBronze"),
  badgeSilver: document.getElementById("badgeSilver"),
  badgeGold: document.getElementById("badgeGold"),
  mvpNickname: document.getElementById("mvpNickname"),
  mvpTitle: document.getElementById("mvpTitle"),
  mvpPoints: document.getElementById("mvpPoints"),
  mvpMessage: document.getElementById("mvpMessage"),
  rewardBalance: document.getElementById("rewardBalance"),
  rewardList: document.getElementById("rewardList"),
  awardForm: document.getElementById("awardForm"),
  nameInput: document.getElementById("nameInput"),
  pointsInput: document.getElementById("pointsInput"),
  reasonInput: document.getElementById("reasonInput"),
  quickPointChips: document.querySelectorAll("[data-quick-point]"),
  awardPreview: document.getElementById("awardPreview"),
  awardToast: document.getElementById("awardToast"),
  awardHelper: document.querySelector(".award-helper"),
  playerLevel: document.getElementById("playerLevel"),
  playerXp: document.getElementById("playerXp"),
  playerStreak: document.getElementById("playerStreak"),
  playerXpBar: document.getElementById("playerXpBar"),
  dailyFocusTitle: document.getElementById("dailyFocusTitle"),
  dailyFocusDescription: document.getElementById("dailyFocusDescription"),
  dailyFocusReward: document.getElementById("dailyFocusReward"),
  dailyFocusStatus: document.getElementById("dailyFocusStatus"),
  dailyFocusAction: document.getElementById("dailyFocusAction"),
  learningSummary: document.getElementById("learningSummary"),
  learningProgressBar: document.getElementById("learningProgressBar"),
  learningPoints: document.getElementById("learningPoints"),
  lectureList: document.getElementById("lectureList"),
  learnerForm: document.getElementById("learnerForm"),
  learnerNameInput: document.getElementById("learnerNameInput"),
  resetLearningButton: document.getElementById("resetLearningButton"),
  missionProfileForm: document.getElementById("missionProfileForm"),
  missionThemeInput: document.getElementById("missionThemeInput"),
  missionGoalInput: document.getElementById("missionGoalInput"),
  missionHoursInput: document.getElementById("missionHoursInput"),
  missionOfferRoleInput: document.getElementById("missionOfferRoleInput"),
  missionSeekRoleInput: document.getElementById("missionSeekRoleInput"),
  missionNoteInput: document.getElementById("missionNoteInput"),
  missionRefreshButton: document.getElementById("missionRefreshButton"),
  missionMatchesList: document.getElementById("missionMatchesList"),
  missionTeamForm: document.getElementById("missionTeamForm"),
  missionTeamNameInput: document.getElementById("missionTeamNameInput"),
  missionTeamMissionInput: document.getElementById("missionTeamMissionInput"),
  missionTeamSelection: document.getElementById("missionTeamSelection"),
  missionTeamsList: document.getElementById("missionTeamsList"),
  dashboardContent: document.getElementById("dashboardContent"),
  gameLobby: document.getElementById("gameLobby"),
  lobbyLevelValue: document.getElementById("lobbyLevelValue"),
  lobbyGemValue: document.getElementById("lobbyGemValue"),
  lobbyPointValue: document.getElementById("lobbyPointValue"),
  lobbyStaminaValue: document.getElementById("lobbyStaminaValue"),
  lobbyStaminaBar: document.getElementById("lobbyStaminaBar"),
  lobbyLeagueValue: document.getElementById("lobbyLeagueValue"),
  lobbyNextStepValue: document.getElementById("lobbyNextStepValue"),
  lobbyMainActionButton: document.getElementById("lobbyMainActionButton"),
  lobbyMainActionHint: document.getElementById("lobbyMainActionHint"),
  lobbyQuestButton: document.getElementById("lobbyQuestButton"),
  lobbyMatchButton: document.getElementById("lobbyMatchButton"),
  lobbyRewardButton: document.getElementById("lobbyRewardButton"),
  lobbyLectureButton: document.getElementById("lobbyLectureButton"),
  lobbyTabButtons: document.querySelectorAll("[data-lobby-tab]"),
  lobbyPanels: document.querySelectorAll("[data-lobby-panel]"),
  tutorialOverlay: document.getElementById("tutorialOverlay"),
  tutorialCloseButton: document.getElementById("tutorialCloseButton"),
  tutorialPrimaryButton: document.getElementById("tutorialPrimaryButton"),
  tutorialGoButton: document.getElementById("tutorialGoButton"),
  tutorialTargetLabel: document.getElementById("tutorialTargetLabel"),
  tutorialStep: document.getElementById("tutorialStep"),
  tutorialTitle: document.getElementById("tutorialTitle"),
  tutorialCopy: document.getElementById("tutorialCopy"),
  tutorialSkipButton: document.getElementById("tutorialSkipButton"),
  tutorialPrevButton: document.getElementById("tutorialPrevButton"),
  tutorialNextButton: document.getElementById("tutorialNextButton"),
  openTutorialButton: document.getElementById("openTutorialButton"),
};

const localUi = {
  nicknameMap: JSON.parse(localStorage.getItem("ui-nickname-map") || "{}"),
  rewardInventory: JSON.parse(localStorage.getItem("ui-reward-inventory") || "{}"),
  rewardSpentPoints: Number(localStorage.getItem("ui-reward-spent-points") || "0"),
  learnerName: localStorage.getItem("ui-learner-name") || DEFAULT_LEARNER_NAME,
  learningProgress: JSON.parse(localStorage.getItem("ui-learning-progress") || "{}"),
};

let authToken = getAuthToken();
let me = null;
let currentRankingTab = "overall";
const vimeoPlayerMap = new Map();
let missionProfile = null;
let missionMatches = [];
let missionTeams = [];
const selectedMissionMatchUserIds = new Set();
const TUTORIAL_STORAGE_KEY = "ui-popquest-tutorial-seen";
const LOBBY_MODE_STORAGE_KEY = "ui-popquest-lobby-mode";
let activeLobbyTab = "overview";
let tutorialStepIndex = 0;
const tutorialSteps = [
  {
    id: "overview",
    title: "ホーム（ロビー）",
    copy: "まずはホームで「次の1手」を確認。中央の大きなボタンから最短で行動開始できます。",
    targetLabel: "対象: ホームタブ",
    lobbyTab: "overview",
  },
  {
    id: "match",
    title: "仲間スカウト",
    copy: "マッチタブで候補を見て、いいね→チーム作成へ。志の近い仲間を素早く見つけます。",
    targetLabel: "対象: マッチタブ",
    lobbyTab: "match",
  },
  {
    id: "reward",
    title: "報酬ショップ",
    copy: "報酬タブではポイントを特典に交換。特別講義の解放条件もここで確認できます。",
    targetLabel: "対象: 報酬タブ",
    lobbyTab: "reward",
  },
  {
    id: "lecture",
    title: "講義でスキル強化",
    copy: "講義タブで進捗と解放済み講義をチェック。完了を積み重ねるほど成長が可視化されます。",
    targetLabel: "対象: 講義タブ",
    lobbyTab: "lecture",
  },
  {
    id: "done",
    title: "準備完了！",
    copy: "あとはホームに戻って「今日のクエストを開始」を押すだけ。まず1アクションから進めましょう。",
    targetLabel: "対象: メインアクション",
    lobbyTab: "overview",
  },
];
let currentState = {
  members: [],
  tickerEvents: [],
  updatedAt: Date.now(),
  learnerName: localUi.learnerName,
  joinedAtMap: {},
  gamification: {
    streak: 0,
    completedQuests: {},
  },
};

function formatTimestamp(timestamp) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp);
}

function getRandomNickname() {
  const used = new Set(Object.values(localUi.nicknameMap));
  const available = nicknamePool.filter((name) => !used.has(name));
  return available[Math.floor(Math.random() * available.length)] ?? `Player${Math.floor(Math.random() * 999)}`;
}

function getDisplayName(realName) {
  if (!localUi.nicknameMap[realName]) {
    localUi.nicknameMap[realName] = getRandomNickname();
    localStorage.setItem("ui-nickname-map", JSON.stringify(localUi.nicknameMap));
  }
  return localUi.nicknameMap[realName];
}

function roleCanAward(role) {
  return role === "admin" || role === "mentor";
}

function getLearningProgressRecord(lectureId) {
  return localUi.learningProgress[lectureId] ?? null;
}

function isLectureUnlocked(lecture) {
  if (!lecture.lockedByReward) return true;
  return Number(localUi.rewardInventory[lecture.lockedByReward] ?? 0) > 0;
}

function isLectureCompleted(lectureId) {
  return Boolean(getLearningProgressRecord(lectureId)?.completed);
}

function getLearningCompletedCount() {
  return lectureCatalog.filter((lecture) => isLectureUnlocked(lecture) && isLectureCompleted(lecture.id)).length;
}

function getLearningEarnedPoints() {
  return lectureCatalog.reduce((sum, lecture) => {
    if (!isLectureUnlocked(lecture)) return sum;
    return sum + (isLectureCompleted(lecture.id) ? lecture.points : 0);
  }, 0);
}

function persistRewardState() {
  localStorage.setItem("ui-reward-inventory", JSON.stringify(localUi.rewardInventory));
  localStorage.setItem("ui-reward-spent-points", String(localUi.rewardSpentPoints));
}

function getAvailableRewardPoints() {
  return Math.max(0, getTotalPointsByLearner(localUi.learnerName) - localUi.rewardSpentPoints);
}

function persistLearningProgress() {
  localStorage.setItem("ui-learning-progress", JSON.stringify(localUi.learningProgress));
}

function updateLearningCardState(lecture) {
  if (!els.lectureList) return;
  const card = els.lectureList.querySelector(`[data-lecture-id="${lecture.id}"]`);
  if (!card) return;
  const status = card.querySelector("[data-lecture-status]");
  const unlocked = isLectureUnlocked(lecture);
  const completed = isLectureCompleted(lecture.id);
  card.classList.toggle("locked", !unlocked);
  card.classList.toggle("done", completed);
  if (status) {
    status.textContent = !unlocked
      ? "未解放 / 報酬交換で視聴可能"
      : completed
      ? `視聴完了 / +${lecture.points}pt（学習ポイント）`
      : `未完了 / +${lecture.points}pt`;
    status.classList.toggle("done", completed);
  }
}

async function markLectureCompleted(lecture) {
  if (!isLectureUnlocked(lecture)) return;
  if (isLectureCompleted(lecture.id)) return;
  localUi.learningProgress[lecture.id] = {
    completed: true,
    completedAt: Date.now(),
    points: lecture.points,
  };
  persistLearningProgress();
  updateLearningCardState(lecture);
  renderLearningSummary();
  showAwardToast(`講座完了: ${lecture.title}`);
}

function renderLearningSummary() {
  if (!els.learningSummary || !els.learningProgressBar || !els.learningPoints) return;
  const completed = getLearningCompletedCount();
  const total = lectureCatalog.filter(isLectureUnlocked).length;
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100);
  const earnedPoints = getLearningEarnedPoints();
  els.learningSummary.textContent = `完了 ${completed} / ${total}本`;
  els.learningProgressBar.style.width = `${percent}%`;
  els.learningPoints.textContent = `学習ポイント: ${earnedPoints}pt`;
}

function renderLectureList() {
  if (!els.lectureList) return;
  els.lectureList.innerHTML = "";
  lectureCatalog.forEach((lecture) => {
    const unlocked = isLectureUnlocked(lecture);
    const card = document.createElement("article");
    card.className = "lecture-card";
    card.dataset.lectureId = lecture.id;
    card.innerHTML = `
      <p class="lecture-card-title">${lecture.title}</p>
      <p class="lecture-card-meta">目安 ${lecture.minutes}分 / Vimeo サンプル</p>
      ${
        unlocked
          ? `<iframe
        class="lecture-player"
        title="${lecture.title}"
        src="https://player.vimeo.com/video/${lecture.vimeoId}?title=0&byline=0&portrait=0"
        loading="lazy"
        allow="autoplay; fullscreen; picture-in-picture; clipboard-write; encrypted-media"
        allowfullscreen
        data-lecture-iframe
        data-lecture-id="${lecture.id}"
      ></iframe>`
          : `<div class="lecture-player lecture-player-locked">
        <p class="lecture-lock">この講義は報酬交換で開放されます</p>
      </div>`
      }
      <p class="lecture-status" data-lecture-status></p>
    `;
    els.lectureList.appendChild(card);
    updateLearningCardState(lecture);
  });
}

function initializeVimeoTracking() {
  const VimeoPlayer = window.Vimeo?.Player;
  if (!VimeoPlayer || !els.lectureList) return;
  lectureCatalog.forEach((lecture) => {
    if (!isLectureUnlocked(lecture)) return;
    if (vimeoPlayerMap.has(lecture.id)) return;
    const iframe = els.lectureList.querySelector(`iframe[data-lecture-id="${lecture.id}"]`);
    if (!iframe) return;
    const player = new VimeoPlayer(iframe);
    vimeoPlayerMap.set(lecture.id, player);
    player.on("timeupdate", async (event) => {
      if (isLectureCompleted(lecture.id)) return;
      if (Number(event?.percent ?? 0) >= LECTURE_PROGRESS_THRESHOLD) {
        await markLectureCompleted(lecture);
      }
    });
  });
}

function renderMissionProfileForm() {
  if (!missionProfile) return;
  if (els.missionThemeInput) els.missionThemeInput.value = missionProfile.theme ?? "";
  if (els.missionGoalInput) els.missionGoalInput.value = missionProfile.goal ?? "";
  if (els.missionHoursInput) els.missionHoursInput.value = String(missionProfile.weeklyHours ?? 1);
  if (els.missionOfferRoleInput) els.missionOfferRoleInput.value = missionProfile.offerRole ?? "";
  if (els.missionSeekRoleInput) els.missionSeekRoleInput.value = missionProfile.seekRole ?? "";
  if (els.missionNoteInput) els.missionNoteInput.value = missionProfile.note ?? "";
}

function renderMissionMatches() {
  if (!els.missionMatchesList) return;
  els.missionMatchesList.innerHTML = "";
  if (!missionMatches.length) {
    const empty = document.createElement("li");
    empty.className = "mission-match-item";
    empty.textContent = "候補がまだありません。プロフィールを保存して再提案してください。";
    els.missionMatchesList.appendChild(empty);
    return;
  }

  missionMatches.forEach((match) => {
    const item = document.createElement("li");
    const checked = selectedMissionMatchUserIds.has(match.userId);
    item.className = "mission-match-item";
    item.innerHTML = `
      <label>
        <input type="checkbox" data-mission-user-id="${match.userId}" ${checked ? "checked" : ""} />
        <div class="mission-match-head">
          <p class="mission-match-name">${match.userName}（${match.theme}）</p>
          <p class="mission-match-score">一致度 ${match.score}%</p>
        </div>
      </label>
      <ul class="mission-match-reasons">${(match.reasons ?? []).map((reason) => `<li>${reason}</li>`).join("")}</ul>
    `;
    els.missionMatchesList.appendChild(item);
  });
}

function renderMissionTeams() {
  if (!els.missionTeamsList) return;
  els.missionTeamsList.innerHTML = "";
  if (!missionTeams.length) {
    const empty = document.createElement("li");
    empty.className = "mission-team-item";
    empty.textContent = "まだチームはありません。候補を選んで作成しましょう。";
    els.missionTeamsList.appendChild(empty);
    return;
  }
  missionTeams.forEach((team) => {
    const item = document.createElement("li");
    item.className = "mission-team-item";
    const memberNames = (team.members ?? []).map((member) => member.userName).join(" / ");
    item.innerHTML = `
      <p class="mission-match-name">${team.name}</p>
      <p class="reward-meta">ミッション: ${team.missionTitle}</p>
      <p class="reward-meta">メンバー: ${memberNames}</p>
    `;
    els.missionTeamsList.appendChild(item);
  });
}

function updateMissionSelectionText() {
  if (!els.missionTeamSelection) return;
  const selected = missionMatches.filter((match) => selectedMissionMatchUserIds.has(match.userId));
  if (!selected.length) {
    els.missionTeamSelection.textContent = "候補を選択してください";
    return;
  }
  els.missionTeamSelection.textContent = `選択中: ${selected.map((member) => member.userName).join(" / ")}`;
}

function renderMission() {
  renderMissionProfileForm();
  renderMissionMatches();
  renderMissionTeams();
  updateMissionSelectionText();
}

function getTotalPointsByLearner(name) {
  const found = currentState.members.find((member) => member.name === name);
  return found ? found.points : 0;
}

function calculateLevel(totalPoints) {
  const level = Math.floor(totalPoints / 100) + 1;
  const progress = totalPoints % 100;
  return { level, progress, required: 100 };
}

function getCurrentLeague(points) {
  return (
    leagueTable.find((league) => points >= league.min && (league.max === null || points <= league.max)) ??
    leagueTable[0]
  );
}

function isRewardUnlockedForLeague(reward, leagueId) {
  return !reward.requiredLeagues?.length || reward.requiredLeagues.includes(leagueId);
}

function renderRanking() {
  if (!els.rankingList) return;
  const members = [...currentState.members].sort((a, b) => b.points - a.points).slice(0, RANKING_VISIBLE_COUNT);
  els.rankingList.innerHTML = "";
  members.forEach((member, index) => {
    const row = document.createElement("li");
    row.className = `ranking-row ${index < 3 ? "top3" : ""}`;
    row.innerHTML = `
      <span class="ranking-position">${index + 1}</span>
      <span class="ranking-name">${getDisplayName(member.name)}</span>
      <span class="ranking-points">${member.points} pt</span>
    `;
    els.rankingList.appendChild(row);
  });
}

function renderTicker() {
  if (!els.tickerTrack) return;
  const repeatedEvents = [...currentState.tickerEvents, ...currentState.tickerEvents].slice(0, 30);
  els.tickerTrack.innerHTML = "";
  repeatedEvents.forEach((event) => {
    const item = document.createElement("li");
    item.className = "ticker-item";
    item.textContent = `${getDisplayName(event.name)}が${event.reason}で${Math.abs(event.points)}pt${
      event.points >= 0 ? "獲得" : "消費"
    }（${formatTimestamp(event.timestamp)}）`;
    els.tickerTrack.appendChild(item);
  });
}

function renderMvp() {
  const top = [...currentState.members].sort((a, b) => b.points - a.points)[0];
  if (!top) return;
  els.mvpNickname.textContent = getDisplayName(top.name);
  els.mvpPoints.textContent = `${top.points} pt`;
  els.mvpTitle.textContent = top.points >= 250 ? "称号: レジェンド開拓者" : "称号: 今週の急成長株";
  els.mvpMessage.textContent = `${getDisplayName(top.name)}さんがトップ。次の行動で追い上げ可能です。`;
}

function renderLeagueAndRewards() {
  const totalPoints = getTotalPointsByLearner(localUi.learnerName);
  const availablePoints = getAvailableRewardPoints();
  const spentPoints = Math.max(0, localUi.rewardSpentPoints);
  const userPoints = totalPoints;
  const league = getCurrentLeague(userPoints);
  els.currentLeagueLabel.textContent = `${league.title} (${userPoints}pt)`;
  const next = league.nextMin;
  if (next === null) {
    els.leagueProgressBar.style.width = "100%";
    els.leagueProgressText.textContent = "最高リーグ到達中";
  } else {
    const range = next - league.min;
    const current = Math.max(0, Math.min(range, userPoints - league.min));
    const percent = Math.round((current / range) * 100);
    els.leagueProgressBar.style.width = `${percent}%`;
    els.leagueProgressText.textContent = `次のリーグまで ${Math.max(0, next - userPoints)}pt`;
  }

  els.badgeBronze.classList.toggle("active", league.id === "bronze");
  els.badgeSilver.classList.toggle("active", league.id === "silver");
  els.badgeGold.classList.toggle("active", league.id === "gold");

  els.rewardBalance.textContent = `交換可能 ${availablePoints}pt（累計 ${totalPoints}pt / 使用 ${spentPoints}pt）`;
  els.rewardList.innerHTML = "";
  rewardCatalog.forEach((reward) => {
    const claimed = localUi.rewardInventory[reward.id] ?? 0;
    const unlocked = isRewardUnlockedForLeague(reward, league.id);
    const canBuy = unlocked && availablePoints >= reward.cost;
    const statusText = !unlocked
      ? "現在のリーグでは未解放"
      : canBuy
        ? "交換できます"
        : `あと${reward.cost - availablePoints}ptで交換`;
    const card = document.createElement("article");
    card.className = `reward-item ${unlocked ? "" : "locked"}`;
    card.innerHTML = `
      <div>
        <p class="reward-title">${reward.title}</p>
        <p class="reward-meta">必要: ${reward.cost}pt / 所持: ${claimed}個</p>
        <p class="reward-lock">${statusText}</p>
      </div>
      <button class="button button-small" type="button" data-reward-id="${reward.id}">交換</button>
    `;
    els.rewardList.appendChild(card);
  });
}

function renderGamification() {
  const points = getTotalPointsByLearner(localUi.learnerName);
  const levelState = calculateLevel(points);
  els.playerLevel.textContent = `Lv.${levelState.level}`;
  els.playerXp.textContent = `${levelState.progress} / ${levelState.required} 経験値`;
  els.playerXpBar.style.width = `${Math.round((levelState.progress / levelState.required) * 100)}%`;
  els.playerStreak.textContent = `${currentState.gamification?.streak ?? 0} 日`;
}

function renderDailyFocus() {
  const points = getTotalPointsByLearner(localUi.learnerName);
  if (points < 30) {
    els.dailyFocusTitle.textContent = "今日30ptを達成する";
    els.dailyFocusDescription.textContent = "まずは小さな投稿を重ねて勢いを作りましょう。";
    els.dailyFocusReward.textContent = `推奨報酬: +${30 - points}pt`;
    els.dailyFocusStatus.textContent = `進捗: ${points}/30pt`;
    return;
  }
  els.dailyFocusTitle.textContent = "貢献アクションを1回実行";
  els.dailyFocusDescription.textContent = "支援系アクションで評価と信頼を積み上げましょう。";
  els.dailyFocusReward.textContent = "推奨報酬: +10pt";
  els.dailyFocusStatus.textContent = "進捗: 推奨";
}

function renderUpdatedAt() {
  if (!els.lastUpdated) return;
  els.lastUpdated.textContent = `最終更新: ${formatTimestamp(currentState.updatedAt)}`;
}

function setLobbyTab(tabId) {
  activeLobbyTab = tabId;
  els.lobbyTabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.lobbyTab === tabId);
  });
  els.lobbyPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.lobbyPanel === tabId);
  });
}

function scrollToMissionPanel() {
  const node = document.getElementById("missionPanel");
  if (node) {
    node.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function scrollToRewardPanel() {
  const node = document.querySelector(".reward-header");
  if (node) {
    node.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function scrollToLecturePanel() {
  const node = document.getElementById("lectureList");
  if (node) {
    node.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function decideNextLobbyStep(totalPoints) {
  if (missionTeams.length === 0) {
    return {
      label: "仲間スカウト",
      hint: "志マッチで候補を選び、最初のチームを作成",
      buttonLabel: "仲間を探す",
      action: () => {
        setLobbyTab("match");
        scrollToMissionPanel();
      },
    };
  }
  const specialUnlocked = Number(localUi.rewardInventory["special-template"] ?? 0) > 0;
  if (!specialUnlocked) {
    return {
      label: "報酬解放",
      hint: "ショップで「限定テンプレ解放」を交換して特別講義を開放",
      buttonLabel: "ショップを開く",
      action: () => {
        setLobbyTab("reward");
        scrollToRewardPanel();
      },
    };
  }
  const specialLecture = lectureCatalog.find((lecture) => lecture.id === "lecture-special-01");
  if (specialLecture && !isLectureCompleted(specialLecture.id)) {
    return {
      label: "特別講義を視聴",
      hint: "解放済みの特別講義を見て、次の成果導線を実行",
      buttonLabel: "講義を再生",
      action: () => {
        setLobbyTab("lecture");
        scrollToLecturePanel();
      },
    };
  }
  if (totalPoints < 80) {
    return {
      label: "クエスト開始",
      hint: "まずはデイリー行動で80ptを目指しましょう",
      buttonLabel: "今日のクエストを開始",
      action: () => setLobbyTab("overview"),
    };
  }
  return {
    label: "週間レビュー更新",
    hint: "今週の成果を振り返り、来週の一手を決める",
    buttonLabel: "レビューを確認",
    action: () => setLobbyTab("overview"),
  };
}

function renderLobby() {
  if (!els.gameLobby) return;
  const points = getTotalPointsByLearner(localUi.learnerName);
  const levelState = calculateLevel(points);
  const league = getCurrentLeague(points);
  const nextStep = decideNextLobbyStep(points);

  if (els.lobbyLevelValue) {
    els.lobbyLevelValue.textContent = `Lv.${levelState.level}`;
  }
  if (els.lobbyLeagueValue) {
    els.lobbyLeagueValue.textContent = league.title;
  }
  if (els.lobbyGemValue) {
    els.lobbyGemValue.textContent = `${(10000 + points * 12).toLocaleString("ja-JP")} G`;
  }
  if (els.lobbyPointValue) {
    els.lobbyPointValue.textContent = `${points.toLocaleString("ja-JP")} pt`;
  }
  if (els.lobbyStaminaValue) {
    els.lobbyStaminaValue.textContent = `${levelState.progress} / ${levelState.required}`;
  }
  if (els.lobbyStaminaBar) {
    els.lobbyStaminaBar.style.width = `${Math.min(100, Math.max(0, (levelState.progress / levelState.required) * 100))}%`;
  }
  if (els.lobbyNextStepValue) {
    els.lobbyNextStepValue.textContent = nextStep.label;
  }
  if (els.lobbyMainActionButton) {
    els.lobbyMainActionButton.textContent = nextStep.buttonLabel;
    els.lobbyMainActionButton.onclick = nextStep.action;
  }
  if (els.lobbyMainActionHint) {
    els.lobbyMainActionHint.textContent = nextStep.hint;
  }
}

function render() {
  renderRanking();
  renderTicker();
  renderMvp();
  renderLeagueAndRewards();
  renderGamification();
  renderDailyFocus();
  renderLectureList();
  renderLearningSummary();
  initializeVimeoTracking();
  renderMission();
  renderLobby();
  renderUpdatedAt();
}

function showAwardToast(message) {
  if (!els.awardToast) return;
  els.awardToast.textContent = message;
  els.awardToast.classList.add("show");
  window.setTimeout(() => els.awardToast.classList.remove("show"), 1800);
}

function openTutorial() {
  if (!els.tutorialOverlay) return;
  renderTutorialStep();
  els.tutorialOverlay.classList.add("is-open");
  els.tutorialOverlay.hidden = false;
  document.body.classList.add("modal-open");
}

function closeTutorial() {
  if (!els.tutorialOverlay) return;
  els.tutorialOverlay.classList.remove("is-open");
  els.tutorialOverlay.hidden = true;
  document.body.classList.remove("modal-open");
}

function renderTutorialStep() {
  const step = tutorialSteps[tutorialStepIndex] ?? tutorialSteps[0];
  if (els.tutorialStep) {
    els.tutorialStep.textContent = `Step ${tutorialStepIndex + 1} / ${tutorialSteps.length}`;
  }
  if (els.tutorialTitle) {
    els.tutorialTitle.textContent = step.title;
  }
  if (els.tutorialCopy) {
    els.tutorialCopy.textContent = step.copy;
  }
  if (els.tutorialTargetLabel) {
    els.tutorialTargetLabel.textContent = step.targetLabel;
  }
  if (step.lobbyTab) {
    setLobbyTab(step.lobbyTab);
  }
  if (els.tutorialPrevButton) {
    els.tutorialPrevButton.disabled = tutorialStepIndex === 0;
  }
  if (els.tutorialNextButton) {
    els.tutorialNextButton.textContent = tutorialStepIndex === tutorialSteps.length - 1 ? "完了" : "次へ";
  }
}

function maybeOpenTutorialOnFirstVisit() {
  const seen = localStorage.getItem(TUTORIAL_STORAGE_KEY) === "1";
  if (seen) return;
  openTutorial();
}

function syncAwardPreview() {
  if (!els.awardPreview) return;
  const name = els.nameInput.value.trim() || "だれか";
  const reason = els.reasonInput.value || "投稿";
  const points = Number(els.pointsInput.value || 0);
  els.awardPreview.textContent = `送信プレビュー: ${name} が ${reason} で ${points}pt獲得`;
}

function syncPermissions() {
  const canAward = roleCanAward(me?.role);
  if (els.awardForm) {
    const controls = els.awardForm.querySelectorAll("input,select,button");
    controls.forEach((control) => control.toggleAttribute("disabled", !canAward));
  }
  if (els.awardHelper) {
    els.awardHelper.textContent = canAward
      ? "入力後すぐにランキングと速報へ反映されます"
      : "ポイント付与には mentor 以上の権限が必要です。";
  }
}

async function refreshMissionData() {
  if (!authToken) return;
  const [profileRes, matchesRes, teamsRes] = await Promise.all([
    fetchMissionProfile(),
    fetchMissionMatches(5),
    fetchMissionTeams(),
  ]);
  missionProfile = profileRes?.profile ?? null;
  missionMatches = matchesRes?.matches ?? [];
  missionTeams = teamsRes?.teams ?? [];
  const validUserIdSet = new Set(missionMatches.map((match) => match.userId));
  [...selectedMissionMatchUserIds].forEach((userId) => {
    if (!validUserIdSet.has(userId)) {
      selectedMissionMatchUserIds.delete(userId);
    }
  });
  renderMission();
}

async function refreshState() {
  if (!authToken) return;
  const [apiState, review] = await Promise.all([
    fetchState(),
    fetchReview(localUi.learnerName),
  ]);
  currentState = mapApiStateToUiState(apiState, currentState);
  currentState.learnerName = localUi.learnerName;
  currentState.updatedAt = Date.now();
  if (review?.review) {
    mergeWeeklyReviewToDom(review.review);
  }
  render();
}

function connectRealtimeBridge() {
  disconnectRealtime();
  connectRealtime({
    onState: (payload) => {
      currentState = mapApiStateToUiState(payload, currentState);
      currentState.updatedAt = Date.now();
      render();
    },
    onAward: (payload) => {
      showAwardToast(`${getDisplayName(payload.member.name)}に${payload.event.points}ptを反映`);
      if (payload.review) {
        mergeWeeklyReviewToDom(payload.review);
      }
    },
  });
}

async function bootstrap() {
  try {
    if (!authToken) {
      const result = await login(CUSTOMER_LOGIN_EMAIL, CUSTOMER_LOGIN_PASSWORD);
      authToken = result.token;
      me = result.user;
    }
    syncPermissions();
    await refreshState();
    await refreshMissionData();
    connectRealtimeBridge();
  } catch (error) {
    me = null;
    console.error("自動ログインに失敗しました:", error);
    syncPermissions();
  }
}

function bindAwardUi() {
  els.awardForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!roleCanAward(me?.role)) {
      showAwardToast("権限不足: mentor以上のみ付与可能");
      return;
    }
    const memberName = els.nameInput.value.trim();
    const points = Number(els.pointsInput.value);
    const reason = els.reasonInput.value;
    if (!memberName || !Number.isFinite(points) || points < 1) return;
    try {
      await awardPoints(memberName, points, reason);
      showAwardToast(`${memberName}に${points}ptを反映しました`);
      await refreshState();
      els.pointsInput.value = "10";
      syncAwardPreview();
    } catch (error) {
      showAwardToast(`付与失敗: ${error.message}`);
    }
  });

  els.quickPointChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const point = Number(chip.dataset.quickPoint);
      if (!Number.isFinite(point)) return;
      els.pointsInput.value = String(point);
      els.quickPointChips.forEach((button) => button.classList.toggle("active", button === chip));
      syncAwardPreview();
    });
  });

  ["input", "change"].forEach((eventName) => {
    els.nameInput?.addEventListener(eventName, syncAwardPreview);
    els.pointsInput?.addEventListener(eventName, syncAwardPreview);
    els.reasonInput?.addEventListener(eventName, syncAwardPreview);
  });

  els.rewardList?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const rewardId = target.dataset.rewardId;
    if (!rewardId) return;
    const reward = rewardCatalog.find((item) => item.id === rewardId);
    if (!reward) return;
    const totalPoints = getTotalPointsByLearner(localUi.learnerName);
    const league = getCurrentLeague(totalPoints);
    if (!isRewardUnlockedForLeague(reward, league.id)) {
      showAwardToast("現在のリーグでは交換できません");
      return;
    }
    const availablePoints = getAvailableRewardPoints();
    if (availablePoints < reward.cost) {
      showAwardToast(`ポイント不足: あと${reward.cost - availablePoints}pt必要です`);
      return;
    }
    const beforeOwned = Number(localUi.rewardInventory[rewardId] ?? 0);
    localUi.rewardInventory[rewardId] = (localUi.rewardInventory[rewardId] ?? 0) + 1;
    localUi.rewardSpentPoints += reward.cost;
    persistRewardState();

    const newlyUnlockedLectures = lectureCatalog.filter(
      (lecture) => lecture.lockedByReward === rewardId && beforeOwned === 0
    );
    if (newlyUnlockedLectures.length > 0) {
      const titles = newlyUnlockedLectures.map((lecture) => `「${lecture.title}」`).join(" / ");
      showAwardToast(`${reward.title}を交換。特別講義 ${titles} を開放しました`);
    } else {
      showAwardToast(`${reward.title}を交換しました（-${reward.cost}pt）`);
    }
    render();
  });
}

function bindLearningUi() {
  if (els.learnerNameInput) {
    els.learnerNameInput.value = localUi.learnerName;
  }

  els.learnerForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const nextName = els.learnerNameInput?.value?.trim();
    if (!nextName) return;
    localUi.learnerName = nextName;
    localStorage.setItem("ui-learner-name", nextName);
    currentState.learnerName = nextName;
    render();
    showAwardToast(`学習者名を「${nextName}」へ更新しました`);
  });

  els.resetLearningButton?.addEventListener("click", () => {
    localUi.learningProgress = {};
    persistLearningProgress();
    lectureCatalog.forEach(updateLearningCardState);
    renderLearningSummary();
    showAwardToast("学習進捗をリセットしました");
  });
}

function bindMissionUi() {
  els.missionProfileForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      theme: els.missionThemeInput?.value?.trim() ?? "",
      goal: els.missionGoalInput?.value?.trim() ?? "",
      weeklyHours: Number(els.missionHoursInput?.value ?? 0),
      offerRole: els.missionOfferRoleInput?.value?.trim() ?? "",
      seekRole: els.missionSeekRoleInput?.value?.trim() ?? "",
      note: els.missionNoteInput?.value?.trim() ?? "",
    };
    if (!payload.theme || !payload.goal || !payload.offerRole || !payload.seekRole || payload.weeklyHours < 1) {
      showAwardToast("志プロフィールの必須項目を入力してください");
      return;
    }
    try {
      const result = await saveMissionProfile(payload);
      missionProfile = result?.profile ?? missionProfile;
      showAwardToast("志プロフィールを保存しました");
      await refreshMissionData();
    } catch (error) {
      showAwardToast(`保存失敗: ${error.message}`);
    }
  });

  els.missionRefreshButton?.addEventListener("click", async () => {
    try {
      await refreshMissionData();
      showAwardToast("マッチ候補を更新しました");
    } catch (error) {
      showAwardToast(`再提案失敗: ${error.message}`);
    }
  });

  els.missionMatchesList?.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    const userId = Number(target.dataset.missionUserId);
    if (!Number.isFinite(userId)) return;
    if (target.checked) {
      if (selectedMissionMatchUserIds.size >= 3) {
        target.checked = false;
        showAwardToast("選択できるメンバーは3名までです");
        return;
      }
      selectedMissionMatchUserIds.add(userId);
    } else {
      selectedMissionMatchUserIds.delete(userId);
    }
    updateMissionSelectionText();
  });

  els.missionTeamForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const teammateUserIds = [...selectedMissionMatchUserIds];
    if (!teammateUserIds.length) {
      showAwardToast("チームメンバーを1名以上選択してください");
      return;
    }
    const teamName = els.missionTeamNameInput?.value?.trim() ?? "";
    const missionTitle = els.missionTeamMissionInput?.value?.trim() ?? "";
    if (!teamName || !missionTitle) {
      showAwardToast("チーム名とミッションを入力してください");
      return;
    }
    try {
      await createMissionTeam({
        teamName,
        missionTitle,
        teammateUserIds,
      });
      selectedMissionMatchUserIds.clear();
      if (els.missionTeamForm) {
        els.missionTeamForm.reset();
      }
      await refreshMissionData();
      showAwardToast("新しいチームを作成しました");
    } catch (error) {
      showAwardToast(`チーム作成失敗: ${error.message}`);
    }
  });
}

function bindNavigation() {
  document.querySelectorAll("[data-ranking-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tabId = button.dataset.rankingTab;
      if (!tabId || tabId === currentRankingTab) return;
      currentRankingTab = tabId;
      document
        .querySelectorAll("[data-ranking-tab]")
        .forEach((node) => node.classList.toggle("active", node === button));
      renderRanking();
    });
  });

  els.lobbyTabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tabId = button.dataset.lobbyTab;
      if (!tabId) return;
      setLobbyTab(tabId);
    });
  });

  els.lobbyQuestButton?.addEventListener("click", () => {
    setLobbyTab("overview");
  });
  els.lobbyMatchButton?.addEventListener("click", () => {
    setLobbyTab("match");
    scrollToMissionPanel();
  });
  els.lobbyRewardButton?.addEventListener("click", () => {
    setLobbyTab("reward");
    scrollToRewardPanel();
  });
  els.lobbyLectureButton?.addEventListener("click", () => {
    setLobbyTab("lecture");
    scrollToLecturePanel();
  });
}

function bindTutorialUi() {
  els.openTutorialButton?.addEventListener("click", () => {
    tutorialStepIndex = 0;
    openTutorial();
  });
  els.tutorialCloseButton?.addEventListener("click", () => {
    closeTutorial();
  });
  els.tutorialSkipButton?.addEventListener("click", () => {
    localStorage.setItem(TUTORIAL_STORAGE_KEY, "1");
    closeTutorial();
  });
  els.tutorialPrevButton?.addEventListener("click", () => {
    tutorialStepIndex = Math.max(0, tutorialStepIndex - 1);
    renderTutorialStep();
  });
  els.tutorialNextButton?.addEventListener("click", () => {
    if (tutorialStepIndex < tutorialSteps.length - 1) {
      tutorialStepIndex += 1;
      renderTutorialStep();
      return;
    }
    localStorage.setItem(TUTORIAL_STORAGE_KEY, "1");
    closeTutorial();
  });
  els.tutorialGoButton?.addEventListener("click", () => {
    const step = tutorialSteps[tutorialStepIndex];
    if (!step) return;
    if (step.lobbyTab) {
      setLobbyTab(step.lobbyTab);
    }
    if (step.lobbyTab === "match") {
      scrollToMissionPanel();
    } else if (step.lobbyTab === "reward") {
      scrollToRewardPanel();
    } else if (step.lobbyTab === "lecture") {
      scrollToLecturePanel();
    }
  });
  els.tutorialOverlay?.addEventListener("click", (event) => {
    if (event.target === els.tutorialOverlay) {
      closeTutorial();
    }
  });
}

function initLobbyMode() {
  const enabled = localStorage.getItem(LOBBY_MODE_STORAGE_KEY) ?? "1";
  if (enabled === "1") {
    document.body.classList.add("game-lobby-mode");
    setLobbyTab("overview");
  }
}

bindAwardUi();
bindLearningUi();
bindMissionUi();
bindNavigation();
bindTutorialUi();
initLobbyMode();
syncAwardPreview();
bootstrap();
maybeOpenTutorialOnFirstVisit();
