#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${1:-/workspace}"
URL_FILE="$WORKDIR/.tunnel-url"
LOG_FILE="$WORKDIR/.tunnel.log"

mkdir -p "$WORKDIR"
touch "$URL_FILE" "$LOG_FILE"

echo "Starting stable tunnel loop..."
echo "Latest URL will be written to: $URL_FILE"

while true; do
  : > "$URL_FILE"
  ssh \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=20 \
    -o ServerAliveCountMax=3 \
    -R 80:localhost:8000 \
    nokey@localhost.run 2>&1 | tee -a "$LOG_FILE" | awk -v url_file="$URL_FILE" -v log_file="$LOG_FILE" '
      {
        if (match($0, /https:\/\/[a-z0-9]+\.lhr\.life/)) {
          url = substr($0, RSTART, RLENGTH);
          print url > url_file;
          close(url_file);
          print strftime("%Y-%m-%dT%H:%M:%S"), "active_url", url >> log_file;
          close(log_file);
          print "active_url=" url;
          fflush();
        }
      }
    '
  echo "$(date -Iseconds) tunnel disconnected, retrying in 2s..." | tee -a "$LOG_FILE"
  sleep 2
done
