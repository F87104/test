import { io } from "https://cdn.socket.io/4.8.3/socket.io.esm.min.js";

import { getAuthToken } from "./client.js";

let socket = null;

export function connectRealtime({ onState, onMetrics, onAward }) {
  if (socket) {
    return socket;
  }
  socket = io(window.location.origin, {
    transports: ["websocket"],
    auth: {
      token: getAuthToken(),
    },
  });

  socket.on("connect_error", (error) => {
    console.warn("Realtime connection issue:", error?.message ?? error);
  });

  socket.on("state:updated", (payload) => {
    if (typeof onState === "function") {
      onState(payload);
    }
  });

  socket.on("metrics:updated", (payload) => {
    if (typeof onMetrics === "function") {
      onMetrics(payload);
    }
  });

  socket.on("points:awarded", (payload) => {
    if (typeof onAward === "function") {
      onAward(payload);
    }
  });

  return socket;
}

export function disconnectRealtime() {
  if (!socket) {
    return;
  }
  socket.disconnect();
  socket = null;
}
