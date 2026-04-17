import { beforeAll, describe, expect, it } from "vitest";
import request from "supertest";

import { createApp } from "../src/server/app.js";
import { initDb } from "../src/server/db.js";

let app;
let adminToken;
let memberToken;

beforeAll(async () => {
  initDb();
  app = createApp();

  const adminRes = await request(app).post("/api/auth/login").send({
    email: "admin@example.com",
    password: "admin1234",
  });
  adminToken = adminRes.body.token;

  const memberRes = await request(app).post("/api/auth/login").send({
    email: "member@example.com",
    password: "member1234",
  });
  memberToken = memberRes.body.token;
});

describe("auth and RBAC", () => {
  it("logs in admin successfully", async () => {
    expect(adminToken).toBeTruthy();
  });

  it("rejects invalid credentials", async () => {
    const res = await request(app).post("/api/auth/login").send({
      email: "admin@example.com",
      password: "wrong-password",
    });
    expect(res.status).toBe(401);
  });

  it("blocks member from award endpoint", async () => {
    const res = await request(app)
      .post("/api/points/award")
      .set("Authorization", `Bearer ${memberToken}`)
      .send({
        memberName: "田中さん",
        points: 10,
        reason: "権限テスト",
      });
    expect(res.status).toBe(403);
  });

  it("allows admin to award points", async () => {
    const res = await request(app)
      .post("/api/points/award")
      .set("Authorization", `Bearer ${adminToken}`)
      .send({
        memberName: "田中さん",
        points: 12,
        reason: "テスト付与",
      });
    expect(res.status).toBe(201);
    expect(res.body.member.points).toBeGreaterThanOrEqual(12);
  });
});

describe("ops dashboard endpoints", () => {
  it("returns metrics for mentor/admin", async () => {
    const res = await request(app)
      .get("/api/ops/metrics")
      .set("Authorization", `Bearer ${adminToken}`);
    expect(res.status).toBe(200);
    expect(typeof res.body.membersCount).toBe("number");
    expect(typeof res.body.thisWeekPoints).toBe("number");
  });

  it("returns state for authenticated user", async () => {
    const res = await request(app).get("/api/state").set("Authorization", `Bearer ${memberToken}`);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.members)).toBe(true);
    expect(Array.isArray(res.body.events)).toBe(true);
  });
});

describe("mission match endpoints", () => {
  it("returns mission profile for authenticated user", async () => {
    const res = await request(app).get("/api/mission/profile").set("Authorization", `Bearer ${memberToken}`);
    expect(res.status).toBe(200);
    expect(res.body.profile.userId).toBeTruthy();
  });

  it("updates mission profile and fetches matches", async () => {
    const updateRes = await request(app)
      .put("/api/mission/profile")
      .set("Authorization", `Bearer ${memberToken}`)
      .send({
        theme: "教育×AI",
        goal: "3ヶ月でプロトタイプを公開する",
        weeklyHours: 9,
        offerRole: "リサーチ",
        seekRole: "セールス",
        note: "検証重視",
      });
    expect(updateRes.status).toBe(200);
    expect(updateRes.body.profile.theme).toBe("教育×AI");

    const matchesRes = await request(app).get("/api/mission/matches").set("Authorization", `Bearer ${memberToken}`);
    expect(matchesRes.status).toBe(200);
    expect(Array.isArray(matchesRes.body.matches)).toBe(true);
  });

  it("creates mission team from selected matches", async () => {
    const matchesRes = await request(app).get("/api/mission/matches").set("Authorization", `Bearer ${memberToken}`);
    const firstMatch = matchesRes.body.matches[0];
    expect(firstMatch).toBeTruthy();
    const createRes = await request(app)
      .post("/api/mission/teams")
      .set("Authorization", `Bearer ${memberToken}`)
      .send({
        teamName: "テスト共創チーム",
        missionTitle: "1週間で検証を実施",
        teammateUserIds: [firstMatch.userId],
      });
    expect(createRes.status).toBe(201);
    expect(createRes.body.team.name).toBe("テスト共創チーム");

    const teamsRes = await request(app).get("/api/mission/teams").set("Authorization", `Bearer ${memberToken}`);
    expect(teamsRes.status).toBe(200);
    expect(Array.isArray(teamsRes.body.teams)).toBe(true);
    expect(teamsRes.body.teams.length).toBeGreaterThan(0);
  });
});
