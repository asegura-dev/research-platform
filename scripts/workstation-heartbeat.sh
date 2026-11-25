#!/bin/bash
# Reports to healthchecks.io that the workstation is up, while Ubuntu runs: a
# success while its disk has room, a failure named disk-NN% when it does not.
# Its silence is the alarm: healthchecks.io emails when the reports stop,
# because the workstation died, froze or lost its connection
# (docs/guides/operate-long-runs.md, ADR-007). Pause the check before you
# switch the workstation off or start Windows; the next report resumes it.
#
#   workstation-heartbeat              check, then report
#   workstation-heartbeat --dry-run    check, print what it would send, send nothing
#   workstation-heartbeat --test-fail  report a failure named "test", to try the alert
#
# The ping URL is read from ~/.config/research-platform/heartbeat.env, a file
# that only its owner can read, as a line HEARTBEAT_URL=... A report carries
# "ok" or the names of the failed checks, never an identifier. Unlike the
# service host's, it does not report a pending reboot or the state of the
# automatic updates: the workstation reboots by hand, between runs.

set -u

URL_FILE=${XDG_CONFIG_HOME:-$HOME/.config}/research-platform/heartbeat.env
DISK_LIMIT=90      # percent of the file system that holds the home folder

mode=${1:-}
case "$mode" in
    ""|--dry-run|--test-fail) ;;
    *) echo "usage: workstation-heartbeat [--dry-run | --test-fail]" >&2; exit 2 ;;
esac

problems=()

# A full disk ends a run when it saves a checkpoint; the queue looks before
# each run starts, and this report while it runs.
used=$(df --output=pcent "$HOME" | tail -n 1 | tr -dc '0-9')
if [ -z "$used" ] || [ "$used" -ge "$DISK_LIMIT" ]; then
    problems+=("disk-${used:-unknown}%")
fi

if [ "$mode" = "--test-fail" ]; then
    problems=("test")
fi

if [ ${#problems[@]} -eq 0 ]; then
    endpoint=""
    body="ok"
else
    endpoint="/fail"
    body="${problems[*]}"
fi

if [ "$mode" = "--dry-run" ]; then
    echo "would send: ${endpoint:-success} ${body}"
    exit 0
fi

# A URL holds no spaces or quotes: whatever of them the editor left goes.
url=$(sed -n 's/^HEARTBEAT_URL=//p' "$URL_FILE" 2>/dev/null | head -n 1 | tr -d "[:space:]\"'")
if [ -z "$url" ]; then
    echo "workstation-heartbeat: no HEARTBEAT_URL in $URL_FILE" >&2
    exit 1
fi

curl -fsS -m 10 --retry 5 -o /dev/null --data-raw "$body" "${url}${endpoint}"
