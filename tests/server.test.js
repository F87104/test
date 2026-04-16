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
