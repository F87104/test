import cors from "cors";
import express from "express";
import helmet from "helmet";
import { z } from "zod";

import { authenticateToken, authorizeRoles, loginAndIssueToken } from "./auth.js";
import { getMembers, initDb } from "./db.js";
import { awardPoints, buildWeeklyReview, getDashboardMetrics, getLiveState, getUserRole } from "./services.js";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(4),
});

const awardSchema = z.object({
  memberName: z.string().min(1),
  points: z.number().int().min(1).max(500),
  reason: z.string().min(1).max(120),
});

export function createApp(io = null) {
  initDb();

  const app = express();
  app.use(helmet());
  app.use(cors());
  app.use(express.json());

  app.get("/api/health", (_req, res) => {
    res.json({ status: "ok", timestamp: Date.now() });
  });

  app.post("/api/auth/login", (req, res) => {
    const parsed = loginSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({ error: "入力形式が不正です。" });
    }
    const { email, password } = parsed.data;
    const result = loginAndIssueToken(email, password);
    if (!result) {
      return res.status(401).json({ error: "メールまたはパスワードが正しくありません。" });
    }
    return res.json(result);
  });

  app.get("/api/me", authenticateToken, (req, res) => {
    res.json({
      id: req.user.id,
      name: req.user.name,
      email: req.user.email,
      role: req.user.role,
      roleFromDb: getUserRole(req.user.id),
    });
  });

  app.get("/api/members", authenticateToken, (_req, res) => {
    res.json({ members: getMembers() });
  });

  app.get("/api/state", authenticateToken, (_req, res) => {
    res.json(getLiveState());
  });

  app.get("/api/reviews/:memberName", authenticateToken, (req, res) => {
    res.json({ review: buildWeeklyReview(req.params.memberName) });
  });

  app.post("/api/points/award", authenticateToken, authorizeRoles(["admin", "mentor"]), (req, res) => {
    const parsed = awardSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({ error: "入力形式が不正です。" });
    }
    const payload = parsed.data;
    const result = awardPoints({
      memberName: payload.memberName,
      points: payload.points,
      reason: payload.reason,
      actorUserId: req.user.id,
      actorRole: req.user.role,
      source: "manual",
    });

    if (io) {
      io.emit("points:awarded", result);
      io.emit("state:updated", getLiveState());
      io.emit("metrics:updated", getDashboardMetrics());
    }
    return res.status(201).json(result);
  });

  app.get("/api/ops/metrics", authenticateToken, authorizeRoles(["admin", "mentor"]), (_req, res) => {
    res.json(getDashboardMetrics());
  });

  app.get("/api/ops/audit", authenticateToken, authorizeRoles(["admin"]), (_req, res) => {
    const state = getLiveState();
    res.json({
      generatedAt: Date.now(),
      totalEvents: state.events.length,
      latestEvents: state.events.slice(0, 20),
      highestMembers: [...state.members].sort((a, b) => b.points - a.points).slice(0, 10),
    });
  });

  app.use((error, _req, res, _next) => {
    console.error("Unhandled server error:", error);
    res.status(500).json({ error: "サーバーエラーが発生しました。" });
  });

  return app;
}
