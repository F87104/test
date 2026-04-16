import {
  awardPoints,
  clearAuthToken,
  fetchMe,
  fetchReview,
  fetchState,
  getAuthToken,
  login,
  logout,
} from "./src/shared/client.js";
import { connectRealtime, disconnectRealtime } from "./src/shared/realtime.js";
import { mapApiStateToUiState, mergeWeeklyReviewToDom } from "./src/shared/stateMapper.js";

const DEFAULT_LEARNER_NAME = "あなた";
const RANKING_VISIBLE_COUNT = 4;

const rewardCatalog = [
  { id: "priority-review", title: "優先レビュー権", cost: 40, requiredLeagues: [] },
  { id: "special-template", title: "限定テンプレ解放", cost: 70, requiredLeagues: ["silver", "gold"] },
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
  authForm: document.getElementById("authForm"),
  authEmail: document.getElementById("authEmail"),
  authPassword: document.getElementById("authPassword"),
  authStatus: document.getElementById("authStatus"),
  logoutButton: document.getElementById("logoutButton"),
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
};

const localUi = {
  nicknameMap: JSON.parse(localStorage.getItem("ui-nickname-map") || "{}"),
  rewardInventory: JSON.parse(localStorage.getItem("ui-reward-inventory") || "{}"),
  learnerName: localStorage.getItem("ui-learner-name") || DEFAULT_LEARNER_NAME,
};

let authToken = getAuthToken();
let me = null;
let currentRankingTab = "overall";
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

function setAuthStatus(message) {
  if (els.authStatus) {
    els.authStatus.textContent = message;
  }
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
  const userPoints = getTotalPointsByLearner(localUi.learnerName);
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

  els.rewardBalance.textContent = `交換可能ポイント: ${userPoints}pt`;
  els.rewardList.innerHTML = "";
  rewardCatalog.forEach((reward) => {
    const claimed = localUi.rewardInventory[reward.id] ?? 0;
    const unlocked = isRewardUnlockedForLeague(reward, league.id);
    const canBuy = unlocked && userPoints >= reward.cost;
    const card = document.createElement("article");
    card.className = `reward-item ${unlocked ? "" : "locked"}`;
    card.innerHTML = `
      <div>
        <p class="reward-title">${reward.title}</p>
        <p class="reward-meta">必要: ${reward.cost}pt / 所持: ${claimed}個</p>
        ${unlocked ? "" : '<p class="reward-lock">現在のリーグでは未解放</p>'}
      </div>
      <button class="button button-small" type="button" data-reward-id="${reward.id}" ${canBuy ? "" : "disabled"}>交換</button>
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

function render() {
  renderRanking();
  renderTicker();
  renderMvp();
  renderLeagueAndRewards();
  renderGamification();
  renderDailyFocus();
  renderUpdatedAt();
}

function showAwardToast(message) {
  if (!els.awardToast) return;
  els.awardToast.textContent = message;
  els.awardToast.classList.add("show");
  window.setTimeout(() => els.awardToast.classList.remove("show"), 1800);
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
  if (!authToken) {
    setAuthStatus("未ログイン");
    syncPermissions();
    return;
  }
  try {
    me = await fetchMe();
    setAuthStatus(`ログイン中: ${me.name}（${me.role}）`);
    syncPermissions();
    await refreshState();
    connectRealtimeBridge();
  } catch (error) {
    clearAuthToken();
    authToken = "";
    me = null;
    setAuthStatus(`認証エラー: ${error.message}`);
    syncPermissions();
  }
}

function bindAuthUi() {
  els.authForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = els.authEmail.value.trim();
    const password = els.authPassword.value;
    if (!email || !password) return;
    setAuthStatus("認証中...");
    try {
      const result = await login(email, password);
      authToken = result.token;
      me = result.user;
      await bootstrap();
    } catch (error) {
      setAuthStatus(`ログイン失敗: ${error.message}`);
    }
  });

  els.logoutButton?.addEventListener("click", () => {
    logout();
    clearAuthToken();
    disconnectRealtime();
    authToken = "";
    me = null;
    setAuthStatus("ログアウトしました");
    syncPermissions();
  });
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
    localUi.rewardInventory[rewardId] = (localUi.rewardInventory[rewardId] ?? 0) + 1;
    localStorage.setItem("ui-reward-inventory", JSON.stringify(localUi.rewardInventory));
    renderLeagueAndRewards();
    showAwardToast("報酬を交換しました（デモ）");
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
}

bindAuthUi();
bindAwardUi();
bindNavigation();
syncAwardPreview();
bootstrap();
