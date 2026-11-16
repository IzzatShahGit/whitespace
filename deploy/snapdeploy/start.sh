#!/usr/bin/env bash
# Runs the API and the web app in one container (see Dockerfile next to this file).
#
# Order matters:
# 1. The API starts first, on 127.0.0.1 only (never reachable from outside).
# 2. The web app starts only once the API answers its health check. SnapDeploy treats the
#    container as ready when $PORT answers, so no visitor is sent in before the API is up.
# 3. On stop (SIGTERM) both get the signal: the API finishes in-flight briefs and chat
#    replies before exiting (see core/tasks.py wait_for_jobs).
# 4. If either process dies, the other is stopped and the container exits, so the
#    platform restarts a whole, consistent pair instead of leaving half an app running.
set -uo pipefail

API_PORT=18000
WEB_PORT="${PORT:-8000}"
if [ "$WEB_PORT" = "$API_PORT" ]; then
  echo "PORT must not be $API_PORT (used by the API inside the container)" >&2
  exit 1
fi

api_pid=""
web_pid=""

stop_all() {
  trap - TERM INT
  [ -n "$web_pid" ] && kill -TERM "$web_pid" 2>/dev/null
  [ -n "$api_pid" ] && kill -TERM "$api_pid" 2>/dev/null
  wait
}
trap 'stop_all; exit 0' TERM INT

# One API process on purpose: the AI key rotation and background jobs live in its memory.
uvicorn whitespace_api.main:app \
  --host 127.0.0.1 --port "$API_PORT" \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 \
  --timeout-graceful-shutdown 25 &
api_pid=$!

# Wait up to 90 s for the API (a cold start on a quarter CPU can take a while).
python - "$API_PORT" <<'PY' || { echo "API did not become healthy" >&2; stop_all; exit 1; }
import sys, time, urllib.request
url = f"http://127.0.0.1:{sys.argv[1]}/api/v1/health"
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        urllib.request.urlopen(url, timeout=2)
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
sys.exit(1)
PY

cd /app/web
HOSTNAME=0.0.0.0 PORT="$WEB_PORT" node server.js &
web_pid=$!
echo "web on :$WEB_PORT, api on 127.0.0.1:$API_PORT"

wait -n "$api_pid" "$web_pid"
code=$?
echo "a process exited (code $code); stopping the container" >&2
stop_all
# Never report success here: an unexpected exit should make the platform restart us.
exit $(( code == 0 ? 1 : code ))
