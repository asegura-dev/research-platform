#!/bin/bash
# Sends a notification to the phone through ntfy, on the service host
# (docs/guides/install-ntfy.md).
#
#   notify "text"                send the text
#   notify -- command [args...]  run the command, then send how it ended and
#                                how long it took; exits with its status
#
# Reads NTFY_URL, NTFY_TOPIC and NTFY_TOKEN from
# ~/.config/research-platform/ntfy.env, a file that only its owner can read.
# A notification leaves the workstation: it carries no paths, study
# identifiers or patient data (ADR-007), which is why the second form names
# only the program, never its arguments.

set -u

CONFIG=${XDG_CONFIG_HOME:-$HOME/.config}/research-platform/ntfy.env

value() {
    # A value holds no spaces or quotes: whatever of them the editor left goes.
    sed -n "s/^$1=//p" "$CONFIG" 2>/dev/null | head -n 1 | tr -d "[:space:]\"'"
}

url=$(value NTFY_URL)
topic=$(value NTFY_TOPIC)
token=$(value NTFY_TOKEN)
if [ -z "$url" ] || [ -z "$topic" ] || [ -z "$token" ]; then
    echo "notify: NTFY_URL, NTFY_TOPIC and NTFY_TOKEN must be set in $CONFIG" >&2
    exit 2
fi

# The token goes in a header read from a file descriptor, not on curl's
# command line, where any process on the machine could read it.
send() {  # title, text, priority, tags
    curl -fsS -m 10 --retry 3 -o /dev/null \
        -H @<(printf 'Authorization: Bearer %s\n' "$token") \
        -H "Title: $1" -H "Priority: $3" -H "Tags: $4" \
        --data-raw "$2" "$url/$topic"
}

if [ "${1:-}" != "--" ]; then
    if [ $# -eq 0 ]; then
        echo "usage: notify \"text\" | notify -- command [args...]" >&2
        exit 2
    fi
    send "Notice" "$*" default speech_balloon
    exit $?
fi

shift
if [ $# -eq 0 ]; then
    echo "usage: notify -- command [args...]" >&2
    exit 2
fi

program=$(basename "$1")
start=$(date +%s)
"$@"
status=$?
seconds=$(( $(date +%s) - start ))
took=$(printf '%dh %02dm %02ds' $((seconds / 3600)) $((seconds % 3600 / 60)) $((seconds % 60)))

if [ "$status" -eq 0 ]; then
    send "$program finished" "It took $took." default white_check_mark
else
    send "$program failed" "Exit status $status, after $took." high x
fi
exit "$status"
