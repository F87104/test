export function mapServerStateToLegacyShape(serverState, existingState = null) {
  const now = Date.now();
  const members = (serverState.members ?? []).map((member) => ({
    name: member.name,
    points: Number(member.points ?? 0),
  }));
  const tickerEvents = (serverState.events ?? []).map((event) => ({
    id: String(event.id),
    name: event.memberName,
    points: Number(event.points ?? 0),
    reason: event.reason,
    timestamp: Number(event.timestamp ?? now),
  }));

  const nicknameMap = { ...(existingState?.nicknameMap ?? {}) };
  const joinedAtMap = { ...(existingState?.joinedAtMap ?? {}) };
  members.forEach((member) => {
    if (!joinedAtMap[member.name]) {
      const found = (serverState.members ?? []).find((m) => m.name === member.name);
      joinedAtMap[member.name] = Number(found?.joinedAt ?? now);
    }
  });

  return {
    members,
    tickerEvents,
    updatedAt: Number(serverState.generatedAt ?? now),
    learnerName: existingState?.learnerName ?? "あなた",
    learningProgress: existingState?.learningProgress ?? {},
    nicknameMap,
    rewardInventory: existingState?.rewardInventory ?? {},
    gamification: existingState?.gamification ?? {
      streak: 0,
      lastActivityDate: null,
      lastActivityTimestamp: null,
      completedQuests: {},
    },
    joinedAtMap,
  };
}

export const mapApiStateToUiState = mapServerStateToLegacyShape;

export function mergeWeeklyReviewToDom(review) {
  const byId = (id) => document.getElementById(id);
  const grade = byId("weeklyReviewGrade");
  const score = byId("weeklyReviewScore");
  const delta = byId("weeklyReviewDelta");
  const bar = byId("weeklyReviewTargetBar");
  const text = byId("weeklyReviewTargetText");
  const summary = byId("weeklyReviewSummary");
  const progress = byId("weeklyMetricProgress");
  const consistency = byId("weeklyMetricConsistency");
  const next = byId("weeklyMetricNext");
  if (!grade || !score || !delta || !bar || !text || !summary || !progress || !consistency || !next) {
    return;
  }
  score.textContent = `${review.score} / 100`;
  delta.textContent = `先週比 ${review.diffPoints >= 0 ? "+" : ""}${review.diffPoints}pt`;
  bar.style.width = `${Math.max(0, Math.min(100, Number(review.targetRate ?? 0)))}%`;
  text.textContent = `${review.pointsThisWeek} / 80pt（達成率 ${review.targetRate}%）`;
  grade.textContent = `評価: ${review.grade}`;
  grade.classList.remove("is-strong", "is-mid", "is-alert");
  if (review.gradeTone) {
    grade.classList.add(review.gradeTone);
  }
  summary.textContent = review.summary;
  progress.textContent = `進捗: 今週 ${review.pointsThisWeek}pt / 先週 ${review.pointsLastWeek}pt / 目標 80pt`;
  consistency.textContent = `継続: 週間講座完了 ${review.lectureCompletions}本`;
  next.textContent = `次の一手: ${review.nextAction}`;
}
