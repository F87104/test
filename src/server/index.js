import { createServer } from "node:http";

import { Server as SocketIOServer } from "socket.io";

import { createApp } from "./app.js";

const PORT = Number(process.env.PORT || 3001);
const HOST = process.env.HOST || "0.0.0.0";

const httpServer = createServer();
const io = new SocketIOServer(httpServer, {
  cors: {
    origin: "*",
  },
});

const app = createApp(io);
httpServer.on("request", app);

io.on("connection", (socket) => {
  socket.emit("system:hello", {
    message: "Realtime connected",
    timestamp: Date.now(),
  });
});

httpServer.listen(PORT, HOST, () => {
  console.log(`API listening on http://${HOST}:${PORT}`);
});
