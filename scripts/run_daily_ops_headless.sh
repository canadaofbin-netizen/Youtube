#!/usr/bin/env bash
# Zero-Token Headless Daily Operations Runner for ALL ABOUT BRAIN (07_Youtube)
# Optional OS crontab install (runs daily at 07:00 UTC & 08:00 UTC with 0 LLM tokens):
#   0 7 * * * /home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/run_daily_ops_headless.sh report
#   0 8 * * * /home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/run_daily_ops_headless.sh schedule
#   */30 * * * * /home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/run_daily_ops_headless.sh watchdog

set -euo pipefail

WORKSPACE="/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube"
PY="/home/canadaofbin/hermes-venv/bin/python"
LOG_DIR="/tmp/aab_daily_ops_logs"
LOCK_FILE="/tmp/aab_daily_ops.lock"
MODE="${1:-all}"

mkdir -p "${LOG_DIR}"
cd "${WORKSPACE}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "[$(date -u +%FT%TZ)] Skipped (${MODE}): another daily_ops instance holds ${LOCK_FILE}" >> "${LOG_DIR}/daily_ops.log"
  exit 0
fi

STAMP="$(date -u +%Y-%m-%d)"
LOG_FILE="${LOG_DIR}/daily_ops_${STAMP}.log"

{
  echo "=== [$(date -u +%FT%TZ)] START mode=${MODE} ==="
  case "${MODE}" in
    report)
      "${PY}" -X utf8 main.py studio-report
      ;;
    watchdog)
      "${PY}" -X utf8 main.py studio-watchdog --apply
      ;;
    schedule)
      "${PY}" -X utf8 main.py qa-scheduler
      ;;
    all)
      "${PY}" -X utf8 main.py studio-watchdog --apply
      "${PY}" -X utf8 main.py studio-report
      "${PY}" -X utf8 main.py qa-scheduler
      ;;
    *)
      echo "Unknown mode: ${MODE} (expected: report | watchdog | schedule | all)" >&2
      exit 2
      ;;
  esac
  echo "=== [$(date -u +%FT%TZ)] DONE mode=${MODE} ==="
} >> "${LOG_FILE}" 2>&1

find "${LOG_DIR}" -name "daily_ops_*.log" -mtime +14 -delete 2>/dev/null || true
