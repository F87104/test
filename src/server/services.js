import {
  addEvent,
  createMissionTeam,
  getAllMissionProfiles,
  getEvents,
  getMemberByName,
  getMembers,
  getMissionProfileByUserId,
  getMissionTeamsByUserId,
  getRoleByUserId,
  getWeeklyReviews,
  setMemberPoints,
  upsertMissionProfile,
  upsertWeeklyReview,
} from "./db.js";

export const LECTURE_COUNT_TARGET = 3;
export const WEEKLY_POINT_TARGET = 80;

export function getWeekRange(offsetWeeks = 0, nowDate = new Date()) {
  const now = new Date(nowDate);
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

export function pointsInRange(events, name, range) {
  return events
    .filter(
      (event) =>
        event.memberName === name &&
        event.timestamp >= range.start.getTime() &&
        event.timestamp <= range.end.getTime()
    )
    .reduce((sum, event) => sum + event.points, 0);
}

export function lectureCompletionsInRange(events, name, range) {
  return events.filter(
    (event) =>
      event.memberName === name &&
      event.timestamp >= range.start.getTime() &&
      event.timestamp <= range.end.getTime() &&
      String(event.reason).includes("視聴完了")
  ).length;
}

export function getReviewGrade(score) {
  if (score >= 85) return { label: "S", tone: "is-strong" };
  if (score >= 70) return { label: "A", tone: "is-strong" };
  if (score >= 55) return { label: "B", tone: "is-mid" };
  return { label: "C", tone: "is-alert" };
}

export function buildWeeklyReview(memberName) {
  const events = getEvents();
  const currentWeek = getWeekRange(0);
  const prevWeek = getWeekRange(-1);
  const thisWeekPoints = pointsInRange(events, memberName, currentWeek);
  const lastWeekPoints = pointsInRange(events, memberName, prevWeek);
  const diff = thisWeekPoints - lastWeekPoints;
  const weeklyLectureCompletions = lectureCompletionsInRange(events, memberName, currentWeek);
  const targetRate = Math.max(0, Math.min(100, Math.round((thisWeekPoints / WEEKLY_POINT_TARGET) * 100)));

  // Keep score formula aligned with frontend experience.
  const score = Math.max(
    0,
    Math.min(
      100,
      Math.round(
        targetRate * 0.55 +
          Math.min(100, weeklyLectureCompletions * 24) * 0.2 +
          Math.min(100, Math.max(0, diff + 20)) * 0.25
      )
    )
  );

  const grade = getReviewGrade(score);
  const summary =
    diff >= 0
      ? `先週より行動量が増加。特に${weeklyLectureCompletions > 0 ? "講座完了" : "日次アクション"}が伸びています。`
      : "先週よりペースが低下。まずは短い行動（+10pt投稿 or 講座1本）で流れを戻しましょう。";
  const nextAction = targetRate < 70 ? "目標まで不足ptを優先回収" : "上位維持のため貢献アクションを追加";

  return {
    memberName,
    weekStart: currentWeek.start.getTime(),
    weekEnd: currentWeek.end.getTime(),
    score,
    grade: grade.label,
    gradeTone: grade.tone,
    pointsThisWeek: thisWeekPoints,
    pointsLastWeek: lastWeekPoints,
    diffPoints: diff,
    targetRate,
    lectureCompletions: weeklyLectureCompletions,
    summary,
    nextAction,
  };
}

export function awardPoints({
  memberName,
  points,
  reason,
  actorUserId,
  actorRole = "member",
  source = "manual",
}) {
  const normalizedName = memberName.trim();
  const member = getMemberByName(normalizedName);
  const beforePoints = member ? member.points : 0;
  const afterPoints = beforePoints + points;
  setMemberPoints(normalizedName, afterPoints);
  const event = addEvent({
    memberName: normalizedName,
    points,
    reason,
    source,
    actorUserId: actorUserId ?? null,
  });
  const review = buildWeeklyReview(normalizedName);
  upsertWeeklyReview(review);

  return {
    event,
    member: {
      name: normalizedName,
      points: afterPoints,
      role: member?.role ?? (normalizedName === "あなた" ? "member" : "member"),
    },
    review,
    actorRole,
  };
}

export function getDashboardMetrics() {
  const members = getMembers();
  const events = getEvents();
  const week = getWeekRange(0);
  const prevWeek = getWeekRange(-1);
  const thisWeekEvents = events.filter(
    (event) => event.timestamp >= week.start.getTime() && event.timestamp <= week.end.getTime()
  );
  const prevWeekEvents = events.filter(
    (event) => event.timestamp >= prevWeek.start.getTime() && event.timestamp <= prevWeek.end.getTime()
  );

  const thisWeekPoints = thisWeekEvents.reduce((sum, event) => sum + event.points, 0);
  const prevWeekPoints = prevWeekEvents.reduce((sum, event) => sum + event.points, 0);
  const activeMembersThisWeek = new Set(thisWeekEvents.map((event) => event.memberName)).size;
  const lectureCompletions = thisWeekEvents.filter((event) => String(event.reason).includes("視聴完了")).length;
  const manualPosts = thisWeekEvents.filter((event) => event.source === "manual").length;
  const supportActions = thisWeekEvents.filter((event) => String(event.reason).includes("支援")).length;

  const reviews = getWeeklyReviews();
  const averageReviewScore =
    reviews.length === 0
      ? 0
      : Math.round(reviews.reduce((sum, review) => sum + Number(review.score || 0), 0) / reviews.length);

  return {
    generatedAt: Date.now(),
    membersCount: members.length,
    activeMembersThisWeek,
    thisWeekPoints,
    prevWeekPoints,
    weekOverWeekDiff: thisWeekPoints - prevWeekPoints,
    lectureCompletions,
    manualPosts,
    supportActions,
    averageReviewScore,
  };
}

export function getLiveState() {
  const members = getMembers();
  const events = getEvents();
  const reviews = getWeeklyReviews(members.length * 3 || 100);
  return {
    members,
    events,
    reviews,
    generatedAt: Date.now(),
  };
}

export function getUserRole(userId) {
  return getRoleByUserId(userId) ?? "member";
}

function normalizeText(value = "") {
  return String(value).trim().toLowerCase();
}

function calcRoleComplementScore(baseProfile, candidateProfile) {
  const baseSeek = normalizeText(baseProfile.seekRole);
  const baseOffer = normalizeText(baseProfile.offerRole);
  const candidateSeek = normalizeText(candidateProfile.seekRole);
  const candidateOffer = normalizeText(candidateProfile.offerRole);
  let score = 40;
  if (baseSeek && candidateOffer && candidateOffer.includes(baseSeek)) score += 30;
  if (baseOffer && candidateSeek && candidateSeek.includes(baseOffer)) score += 20;
  return Math.min(100, score);
}

function calcThemeScore(baseProfile, candidateProfile) {
  const baseTheme = normalizeText(baseProfile.theme);
  const candidateTheme = normalizeText(candidateProfile.theme);
  if (!baseTheme || !candidateTheme) return 50;
  return baseTheme === candidateTheme ? 100 : 55;
}

function calcHoursScore(baseProfile, candidateProfile) {
  const base = Number(baseProfile.weeklyHours ?? 0);
  const candidate = Number(candidateProfile.weeklyHours ?? 0);
  const diff = Math.abs(base - candidate);
  if (diff <= 2) return 100;
  if (diff <= 5) return 80;
  if (diff <= 8) return 60;
  return 40;
}

function computeMissionMatchScore(baseProfile, candidateProfile) {
  const themeScore = calcThemeScore(baseProfile, candidateProfile);
  const hoursScore = calcHoursScore(baseProfile, candidateProfile);
  const complementScore = calcRoleComplementScore(baseProfile, candidateProfile);
  const score = Math.round(themeScore * 0.45 + hoursScore * 0.2 + complementScore * 0.35);
  return {
    score,
    reasons: [
      `テーマ一致度 ${themeScore}%`,
      `稼働時間の近さ ${hoursScore}%`,
      `役割補完性 ${complementScore}%`,
    ],
  };
}

export function getMissionProfile(userId) {
  return getMissionProfileByUserId(userId);
}

export function saveMissionProfile(userId, payload) {
  return upsertMissionProfile({
    userId,
    theme: payload.theme,
    goal: payload.goal,
    weeklyHours: payload.weeklyHours,
    offerRole: payload.offerRole,
    seekRole: payload.seekRole,
    note: payload.note,
  });
}

export function getMissionMatchesForUser(userId, limit = 5) {
  const base = getMissionProfileByUserId(userId);
  if (!base) {
    return [];
  }
  const allProfiles = getAllMissionProfiles();
  return allProfiles
    .filter((profile) => profile.userId !== userId)
    .map((profile) => {
      const scored = computeMissionMatchScore(base, profile);
      return {
        ...profile,
        score: scored.score,
        reasons: scored.reasons,
      };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

export function createMissionTeamForUser({ ownerUserId, teammateUserIds, teamName, missionTitle }) {
  const allMemberIds = [ownerUserId, ...teammateUserIds];
  return createMissionTeam({
    name: teamName,
    missionTitle,
    createdByUserId: ownerUserId,
    memberUserIds: allMemberIds,
  });
}

export function getMissionTeamsForUser(userId) {
  return getMissionTeamsByUserId(userId);
}
