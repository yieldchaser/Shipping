#!/usr/bin/env bash
# Watchdog for the banchero LlamaParse run.
#
# Designed for a no-agent cron slot: stdout is the ONLY signal that reaches the
# user, so it prints NOTHING while the run is healthy. Silence means healthy.
# Output appears only on news: a restart, a completion, or detected failures.
#
# Recovery is simply "start it again if it is not running" - the runner is
# resumable (state written after every document), so a restart never loses work.
#
# Deliberately does NOT start a second worker when one is alive: two concurrent
# runs would double-spend credits on the same documents.
set -u
cd "C:/Users/Dell/Github/Shipping" || { echo "WATCHDOG: repo path missing"; exit 0; }

LOGDIR=data/extracted/llamaparse_banchero
LOG="$LOGDIR/run.log"
STATE="$LOGDIR/_run_state.json"
WATCHLOG="$LOGDIR/watchdog.log"
mkdir -p "$LOGDIR"

stamp() { date '+%Y-%m-%d %H:%M:%S'; }

count_procs() {
  powershell -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { \$_.CommandLine -like '*run_banchero_llamaparse*' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r\n '
}

read_state() {
  python3 -c "
import json
try:
    st = json.load(open(r'$STATE'))
    print(len(st['done']), len(st['failed']), st.get('pages_parsed', 0), st.get('credits_estimated', 0))
except Exception:
    print('0 0 0 0')
" 2>/dev/null
}

ALIVE=$(count_procs); ALIVE=${ALIVE:-0}
read -r DONE FAILED PAGES CREDITS <<< "$(read_state)"
TOTAL=$(ls corpus/01-brokers/banchero_costa/*/*.pdf 2>/dev/null | wc -l | tr -d ' ')

echo "$(stamp) alive=$ALIVE done=$DONE failed=$FAILED credits=$CREDITS" >> "$WATCHLOG"

# ---- healthy: say nothing ----
if [ "$ALIVE" -gt 0 ] 2>/dev/null; then
  exit 0
fi

# ---- finished? ----
if [ "$DONE" -ge "$((TOTAL - 1))" ] 2>/dev/null; then
  echo "$(stamp) COMPLETE done=$DONE/$TOTAL - no restart" >> "$WATCHLOG"
  if [ "${WATCH_COMPLETE_REPORTED:-0}" != "1" ]; then
    echo "banchero LlamaParse run COMPLETE: $DONE/$TOTAL docs, $PAGES pages, ~$CREDITS credits, $FAILED failures."
    [ "$FAILED" -gt 0 ] 2>/dev/null && echo "Failures to triage: see $STATE"
    touch "$LOGDIR/_complete_reported"
  fi
  exit 0
fi

# ---- dead: report and restart ----
echo "$(stamp) DEAD done=$DONE/$TOTAL - restarting" >> "$WATCHLOG"
export PYTHONUNBUFFERED=1
nohup python3 scripts/extract/publishers/run_banchero_llamaparse.py --tier cost_effective >> "$LOG" 2>&1 &
NEWPID=$!
echo "$(stamp) restarted pid $NEWPID" >> "$WATCHLOG"

echo "banchero LlamaParse run was DEAD at $DONE/$TOTAL docs ($FAILED failures, ~$CREDITS credits spent). Restarted as pid $NEWPID - it resumes from the checkpoint, no work lost."
