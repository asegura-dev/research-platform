#!/bin/bash
# Reports the service host's health to healthchecks.io: a success when every
# check below passes, a failure with the names of the checks that did not.
# Its silence is the alarm: healthchecks.io emails when the reports stop
# (docs/guides/watch-the-service-host-with-healthchecks.md, ADR-007).
#
#   service-host-heartbeat              check, then report
#   service-host-heartbeat --dry-run    check, print what it would send, send nothing
#   service-host-heartbeat --test-fail  report a failure named "test", to try the alert
#
# The ping URL is read from /etc/research-platform/heartbeat.env, a file that
# only root can read, as a line HEARTBEAT_URL=... A report carries "ok" or the
# names of the failed checks, never an identifier. Every check only reads.

set -u

URL_FILE=/etc/research-platform/heartbeat.env
UPGRADE_STAMP=/var/lib/apt/periodic/upgrade-stamp
REBOOT_FLAG=/var/run/reboot-required
UPGRADE_MAX=3600   # minutes: 60 hours, two daily runs missed or failed in a row
REBOOT_MAX=2880    # minutes: two days, two nightly reboots missed
DISK_LIMIT=90      # percent of the root file system

mode=${1:-}
case "$mode" in
    ""|--dry-run|--test-fail) ;;
    *) echo "usage: service-host-heartbeat [--dry-run | --test-fail]" >&2; exit 2 ;;
esac

problems=()

# apt reads its configuration, then its sources: a typo in either stops every
# apt command, automatic security updates included, without a sound. A typo
# in the configuration stops the second command too, so only the first one is
# named. apt-cache keeps its cache in memory, so that it writes nothing.
if ! apt-config dump >/dev/null 2>&1; then
    problems+=("apt-config")
elif ! apt-cache -o Dir::Cache::pkgcache= -o Dir::Cache::srcpkgcache= policy >/dev/null 2>&1; then
    problems+=("apt-sources")
fi

# apt's daily job touches this stamp each time unattended-upgrades finishes
# without an error (/usr/lib/apt/apt.systemd.daily). The job starts between
# 06:00 and 07:00, so the stamp passes 60 hours only on the evening of the
# second day in a row without a good run, whatever the minute of each run.
if [ ! -e "$UPGRADE_STAMP" ] || [ -n "$(find "$UPGRADE_STAMP" -mmin +"$UPGRADE_MAX")" ]; then
    problems+=("unattended-upgrades-stale")
fi

# The automatic reboot at 04:00 (docs/guides/install-ubuntu-server.md, step 10)
# clears this flag; one older than two days means that the reboots stopped.
if [ -e "$REBOOT_FLAG" ] && [ -n "$(find "$REBOOT_FLAG" -mmin +"$REBOOT_MAX")" ]; then
    problems+=("reboot-pending")
fi

used=$(df --output=pcent / | tail -n 1 | tr -dc '0-9')
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
    echo "service-host-heartbeat: no HEARTBEAT_URL in $URL_FILE" >&2
    exit 1
fi

curl -fsS -m 10 --retry 5 -o /dev/null --data-raw "$body" "${url}${endpoint}"
