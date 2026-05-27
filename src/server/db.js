import Database from "better-sqlite3";
import bcrypt from "bcryptjs";
import path from "node:path";

const DB_FILE = process.env.DB_FILE || path.join(process.cwd(), "data.sqlite");

let db;

const seedUsers = [
  { id: 1, name: "管理者", email: "admin@example.com", password: "admin1234", role: "admin" },
  { id: 2, name: "メンター花", email: "mentor@example.com", password: "mentor1234", role: "mentor" },
  { id: 3, name: "あなた", email: "member@example.com", password: "member1234", role: "member" },
];

const seedMembers = [
  { name: "田中さん", points: 64, role: "member" },
  { name: "佐藤さん", points: 58, role: "member" },
  { name: "高橋さん", points: 46, role: "member" },
  { name: "鈴木さん", points: 44, role: "member" },
  { name: "中村さん", points: 39, role: "member" },
  { name: "あなた", points: 28, role: "member" },
];

function getDb() {
  if (!db) {
    db = new Database(DB_FILE);
    db.pragma("journal_mode = WAL");
  }
  return db;
}

export function initDb() {
  const database = getDb();
  database.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin','mentor','member')),
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS members (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      points INTEGER NOT NULL DEFAULT 0,
      role TEXT NOT NULL CHECK(role IN ('admin','mentor','member')),
      joined_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS point_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      member_name TEXT NOT NULL,
      points INTEGER NOT NULL,
      reason TEXT NOT NULL,
      source TEXT NOT NULL DEFAULT 'manual',
      created_by_user_id INTEGER,
      timestamp INTEGER NOT NULL,
      FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS weekly_reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      member_name TEXT NOT NULL,
      week_start INTEGER NOT NULL,
      week_end INTEGER NOT NULL,
      score INTEGER NOT NULL,
      grade TEXT NOT NULL,
      grade_tone TEXT NOT NULL,
      points_this_week INTEGER NOT NULL,
      points_last_week INTEGER NOT NULL,
      diff_points INTEGER NOT NULL,
      target_rate INTEGER NOT NULL,
      lecture_completions INTEGER NOT NULL,
      summary TEXT NOT NULL,
      next_action TEXT NOT NULL,
      updated_at INTEGER NOT NULL,
      UNIQUE(member_name, week_start, week_end)
    );

    CREATE TABLE IF NOT EXISTS mission_profiles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL UNIQUE,
      theme TEXT NOT NULL DEFAULT '',
      goal TEXT NOT NULL DEFAULT '',
      weekly_hours INTEGER NOT NULL DEFAULT 0,
      offer_role TEXT NOT NULL DEFAULT '',
      seek_role TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '',
      updated_at INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS mission_teams (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      mission_title TEXT NOT NULL,
      mission_status TEXT NOT NULL DEFAULT 'planning',
      created_by_user_id INTEGER NOT NULL,
      created_at INTEGER NOT NULL,
      FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS mission_team_members (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      team_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      role_in_team TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'active',
      joined_at INTEGER NOT NULL,
      UNIQUE(team_id, user_id),
      FOREIGN KEY(team_id) REFERENCES mission_teams(id),
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);

  const userCount = database.prepare("SELECT COUNT(*) AS count FROM users").get().count;
  if (userCount === 0) {
    const insertUser = database.prepare(`
      INSERT INTO users (id, name, email, password_hash, role, created_at)
      VALUES (@id, @name, @email, @password_hash, @role, @created_at)
    `);
    const now = Date.now();
    for (const user of seedUsers) {
      insertUser.run({
        id: user.id,
        name: user.name,
        email: user.email,
        password_hash: bcrypt.hashSync(user.password, 10),
        role: user.role,
        created_at: now,
      });
    }
  }

  const memberCount = database.prepare("SELECT COUNT(*) AS count FROM members").get().count;
  if (memberCount === 0) {
    const insertMember = database.prepare(`
      INSERT INTO members (name, points, role, joined_at)
      VALUES (@name, @points, @role, @joined_at)
    `);
    const now = Date.now();
    for (const member of seedMembers) {
      insertMember.run({ ...member, joined_at: now });
    }
  }

  const missionProfileCount = database.prepare("SELECT COUNT(*) AS count FROM mission_profiles").get().count;
  if (missionProfileCount === 0) {
    const now = Date.now();
    const insertProfile = database.prepare(`
      INSERT INTO mission_profiles (user_id, theme, goal, weekly_hours, offer_role, seek_role, note, updated_at)
      VALUES (@user_id, @theme, @goal, @weekly_hours, @offer_role, @seek_role, @note, @updated_at)
    `);
    const seedProfiles = [
      {
        user_id: 1,
        theme: "教育DX",
        goal: "3ヶ月で講座運営を自動化する",
        weekly_hours: 8,
        offer_role: "戦略設計",
        seek_role: "実装担当",
        note: "検証速度を重視",
      },
      {
        user_id: 2,
        theme: "コミュニティ運営",
        goal: "伴走導線をテンプレート化する",
        weekly_hours: 6,
        offer_role: "コーチング",
        seek_role: "SNS発信",
        note: "小さく試すのが得意",
      },
      {
        user_id: 3,
        theme: "AI活用",
        goal: "最初の有料サービスを作る",
        weekly_hours: 10,
        offer_role: "リサーチ",
        seek_role: "販売設計",
        note: "同じ熱量の仲間を探したい",
      },
    ];
    for (const profile of seedProfiles) {
      insertProfile.run({ ...profile, updated_at: now });
    }
  }
}

export function getUsers() {
  const database = getDb();
  return database
    .prepare("SELECT id, name, email, password_hash AS passwordHash, role, created_at AS createdAt FROM users ORDER BY id")
    .all();
}

export function getUserByEmail(email) {
  const database = getDb();
  return (
    database
      .prepare(
        "SELECT id, name, email, password_hash AS passwordHash, role, created_at AS createdAt FROM users WHERE email = ?"
      )
      .get(email) ?? null
  );
}

export function getUserById(userId) {
  const database = getDb();
  return (
    database
      .prepare(
        "SELECT id, name, email, password_hash AS passwordHash, role, created_at AS createdAt FROM users WHERE id = ?"
      )
      .get(userId) ?? null
  );
}

export function getRoleByUserId(userId) {
  const database = getDb();
  const found = database.prepare("SELECT role FROM users WHERE id = ?").get(userId);
  return found?.role ?? null;
}

export function getMembers() {
  const database = getDb();
  return database
    .prepare("SELECT name, points, role, joined_at AS joinedAt FROM members ORDER BY points DESC, name ASC")
    .all();
}

export function getMemberByName(name) {
  const database = getDb();
  return (
    database
      .prepare("SELECT name, points, role, joined_at AS joinedAt FROM members WHERE name = ?")
      .get(name) ?? null
  );
}

export function setMemberPoints(name, points) {
  const database = getDb();
  const now = Date.now();
  const existing = getMemberByName(name);
  if (existing) {
    database.prepare("UPDATE members SET points = ? WHERE name = ?").run(points, name);
  } else {
    database
      .prepare("INSERT INTO members (name, points, role, joined_at) VALUES (?, ?, 'member', ?)")
      .run(name, points, now);
  }
}

export function addEvent({ memberName, points, reason, source = "manual", createdByUserId = null }) {
  const database = getDb();
  const timestamp = Date.now();
  const info = database
    .prepare(
      "INSERT INTO point_events (member_name, points, reason, source, created_by_user_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)"
    )
    .run(memberName, points, reason, source, createdByUserId, timestamp);
  return {
    id: info.lastInsertRowid,
    memberName,
    points,
    reason,
    source,
    createdByUserId,
    timestamp,
  };
}

export function getEvents(limit = 500) {
  const database = getDb();
  return database
    .prepare(
      `
      SELECT
        id,
        member_name AS memberName,
        points,
        reason,
        source,
        created_by_user_id AS createdByUserId,
        timestamp
      FROM point_events
      ORDER BY timestamp DESC
      LIMIT ?
    `
    )
    .all(limit);
}

export function upsertWeeklyReview(review) {
  const database = getDb();
  const now = Date.now();
  database
    .prepare(
      `
      INSERT INTO weekly_reviews (
        member_name, week_start, week_end, score, grade, grade_tone,
        points_this_week, points_last_week, diff_points, target_rate,
        lecture_completions, summary, next_action, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(member_name, week_start, week_end) DO UPDATE SET
        score = excluded.score,
        grade = excluded.grade,
        grade_tone = excluded.grade_tone,
        points_this_week = excluded.points_this_week,
        points_last_week = excluded.points_last_week,
        diff_points = excluded.diff_points,
        target_rate = excluded.target_rate,
        lecture_completions = excluded.lecture_completions,
        summary = excluded.summary,
        next_action = excluded.next_action,
        updated_at = excluded.updated_at
    `
    )
    .run(
      review.memberName,
      review.weekStart,
      review.weekEnd,
      review.score,
      review.grade,
      review.gradeTone,
      review.pointsThisWeek,
      review.pointsLastWeek,
      review.diffPoints,
      review.targetRate,
      review.lectureCompletions,
      review.summary,
      review.nextAction,
      now
    );
}

export function getWeeklyReviews(limit = 100) {
  const database = getDb();
  return database
    .prepare(
      `
      SELECT
        member_name AS memberName,
        week_start AS weekStart,
        week_end AS weekEnd,
        score,
        grade,
        grade_tone AS gradeTone,
        points_this_week AS pointsThisWeek,
        points_last_week AS pointsLastWeek,
        diff_points AS diffPoints,
        target_rate AS targetRate,
        lecture_completions AS lectureCompletions,
        summary,
        next_action AS nextAction,
        updated_at AS updatedAt
      FROM weekly_reviews
      ORDER BY updated_at DESC
      LIMIT ?
    `
    )
    .all(limit);
}

export function getMissionProfileByUserId(userId) {
  const database = getDb();
  return (
    database
      .prepare(
        `
        SELECT
          mp.user_id AS userId,
          u.name AS userName,
          u.email AS userEmail,
          mp.theme,
          mp.goal,
          mp.weekly_hours AS weeklyHours,
          mp.offer_role AS offerRole,
          mp.seek_role AS seekRole,
          mp.note,
          mp.updated_at AS updatedAt
        FROM mission_profiles mp
        INNER JOIN users u ON u.id = mp.user_id
        WHERE mp.user_id = ?
      `
      )
      .get(userId) ?? null
  );
}

export function upsertMissionProfile({
  userId,
  theme,
  goal,
  weeklyHours,
  offerRole,
  seekRole,
  note,
}) {
  const database = getDb();
  const updatedAt = Date.now();
  database
    .prepare(
      `
      INSERT INTO mission_profiles (
        user_id, theme, goal, weekly_hours, offer_role, seek_role, note, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        theme = excluded.theme,
        goal = excluded.goal,
        weekly_hours = excluded.weekly_hours,
        offer_role = excluded.offer_role,
        seek_role = excluded.seek_role,
        note = excluded.note,
        updated_at = excluded.updated_at
    `
    )
    .run(userId, theme, goal, weeklyHours, offerRole, seekRole, note, updatedAt);
  return getMissionProfileByUserId(userId);
}

export function getAllMissionProfiles() {
  const database = getDb();
  return database
    .prepare(
      `
      SELECT
        mp.user_id AS userId,
        u.name AS userName,
        u.email AS userEmail,
        mp.theme,
        mp.goal,
        mp.weekly_hours AS weeklyHours,
        mp.offer_role AS offerRole,
        mp.seek_role AS seekRole,
        mp.note,
        mp.updated_at AS updatedAt
      FROM mission_profiles mp
      INNER JOIN users u ON u.id = mp.user_id
      ORDER BY mp.updated_at DESC
    `
    )
    .all();
}

export function createMissionTeam({
  name,
  missionTitle,
  createdByUserId,
  memberUserIds,
}) {
  const database = getDb();
  const now = Date.now();
  const insertTeam = database.prepare(
    `
    INSERT INTO mission_teams (name, mission_title, mission_status, created_by_user_id, created_at)
    VALUES (?, ?, 'planning', ?, ?)
  `
  );
  const insertMember = database.prepare(
    `
    INSERT INTO mission_team_members (team_id, user_id, role_in_team, status, joined_at)
    VALUES (?, ?, '', 'active', ?)
  `
  );
  const transaction = database.transaction(() => {
    const teamResult = insertTeam.run(name, missionTitle, createdByUserId, now);
    const teamId = Number(teamResult.lastInsertRowid);
    const uniqueMembers = [...new Set(memberUserIds)];
    for (const userId of uniqueMembers) {
      insertMember.run(teamId, userId, now);
    }
    return teamId;
  });
  const teamId = transaction();
  return getMissionTeamById(teamId);
}

export function getMissionTeamById(teamId) {
  const database = getDb();
  const team = database
    .prepare(
      `
      SELECT
        t.id,
        t.name,
        t.mission_title AS missionTitle,
        t.mission_status AS missionStatus,
        t.created_by_user_id AS createdByUserId,
        t.created_at AS createdAt,
        u.name AS createdByName
      FROM mission_teams t
      INNER JOIN users u ON u.id = t.created_by_user_id
      WHERE t.id = ?
    `
    )
    .get(teamId);
  if (!team) return null;
  const members = database
    .prepare(
      `
      SELECT
        tm.user_id AS userId,
        u.name AS userName,
        u.email AS userEmail,
        tm.role_in_team AS roleInTeam,
        tm.status,
        tm.joined_at AS joinedAt
      FROM mission_team_members tm
      INNER JOIN users u ON u.id = tm.user_id
      WHERE tm.team_id = ?
      ORDER BY tm.joined_at ASC
    `
    )
    .all(teamId);
  return { ...team, members };
}

export function getMissionTeamsByUserId(userId) {
  const database = getDb();
  const teamRows = database
    .prepare(
      `
      SELECT
        t.id,
        t.name,
        t.mission_title AS missionTitle,
        t.mission_status AS missionStatus,
        t.created_at AS createdAt
      FROM mission_teams t
      INNER JOIN mission_team_members tm ON tm.team_id = t.id
      WHERE tm.user_id = ?
      ORDER BY t.created_at DESC
    `
    )
    .all(userId);
  return teamRows.map((row) => getMissionTeamById(row.id)).filter(Boolean);
}
