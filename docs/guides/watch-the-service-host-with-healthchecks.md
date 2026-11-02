# Watch the service host with healthchecks.io

> **Scope:** the service host. At the end, it pings healthchecks.io every five
> minutes, and an email reaches you when a ping names a problem, or when the
> pings stop because the host is off, the house lost its power or its
> internet, or the timer died. The GPU workstation does not ping this way: its
> long runs will, each with a check of its own.

> **Status:** written on 2026-11-01 from the documentation of healthchecks.io,
> systemd and apt. Not run yet.

A watcher at home dies with the house, so healthchecks.io watches the platform
from outside
([ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md)). It works as a
dead man's switch: the host sends a *ping*, one HTTPS request, on a schedule,
and healthchecks.io raises the alarm when a ping reports a failure, or when
the pings stop arriving.

Every five minutes, a systemd timer on the server runs a short script,
`service-host-heartbeat`. The script checks four things that fail without a
sound, then pings:

- **apt can read its configuration and its sources.** A typo in either stops
  every apt command, the automatic security updates included; on the server
  guide's first run, one went unnoticed until a later check (its step 10).
- **unattended-upgrades finished a run without errors in the last 60 hours.**
- **No reboot has been pending for more than two days.** The automatic reboot
  at 04:00 should clear each one within a day.
- **The root file system is less than 90% full.**

A ping carries `ok`, or the names of the checks that failed, and nothing that
identifies the host. Its address, the *ping URL*, is a credential: whoever
holds it can report a false success and silence a real failure. It lives in a
file on the server that only root can read, and in the healthchecks.io
dashboard, which shows it again whenever you need it; your private note does
not need it.

The script and its timer are files of this repository, in `scripts/` and
`config/systemd/`. The server installs them from a clone, so that what runs
there as root is what git shows.

Read the [server guide](install-ubuntu-server.md), at least its step 10, and
the [Tailscale guide](install-tailscale.md) first: this guide builds on them.
Every command runs on the server, over SSH (`ssh server`). The dashboard opens
in a browser, on any computer.

Every step ends with a check. Read-only commands come first, and nothing that
changes the machine runs until they match what you expect.

Before pasting a block that has `sudo` after its first line, run `sudo -v`
alone and type your password. In a new session, or 15 minutes after the last
`sudo`, a password prompt would take the lines pasted after it.

Never commit the ping URL, the ping key or your email address to this
repository.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| Which host pings | The service host only | It is always on and powers on by itself after a power cut, so its silence means something. The workstation starts Windows at times and stays off after a cut: its silence is not an alarm, and its long runs ping on their own | [ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md) |
| When an email arrives | After 15 minutes without a ping (period 5 minutes, grace time 10), or at once when a ping names a failed check | Around the 04:00 reboot, two pings are less than ten minutes apart; a power cut, a hang or a lost connection lasts longer | This guide |
| What each ping checks | apt reads its configuration and its sources; unattended-upgrades finished a run without errors in the last 60 hours; no reboot pending for more than two days; the root file system less than 90% full | Each one fails without a sound, and stops the security updates or, with a full disk, the services. The update job starts between 06:00 and 07:00 and the reboot is at 04:00, so the limits of both are crossed only after two days in a row went wrong, never by the minute a job ran | This guide |
| What a ping carries | `ok`, or the names of the checks that failed | healthchecks.io stores the body of every ping; nothing in it identifies the host | [ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md) |
| The ping URL | `https://hc-ping.com/<ping-key>/service-host`: the project's ping key, then the check's slug | One secret for the project instead of one for each check: the checks that come later, such as each long run's, use the same key with a slug of their own | This guide |
| Where the URL lives | In `/etc/research-platform/heartbeat.env`, which only root can read, and in the dashboard | Whoever holds it can silence a real failure. The script reads the file itself, so it runs the same way from its timer and by hand | [ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md) |
| How it runs | A systemd timer and a oneshot service, installed from a clone of this repository | They come back after every reboot, and what runs as root is what git shows | This guide |
| Where alerts go | The email address of the healthchecks.io account: your personal one, with two-factor authentication on the account | Email does not depend on the house; ntfy, on the service host, would die with it | This guide |

## 1. What you need

- The service host installed (server guide, through step 11), with the
  automatic updates and the 04:00 reboot of its step 10, and in the tailnet
  (Tailscale guide, through section 6).
- A healthchecks.io account on the free plan (Hobbyist: 20 checks, as of
  November 2026), opened with your personal email address, where the alerts
  arrive, and with two-factor authentication on, in the account's settings.

On the server, read-only:

```bash
systemctl is-enabled apt-daily-upgrade.timer                  # enabled
ls -l --time-style=+%F /var/lib/apt/periodic/upgrade-stamp    # today's or yesterday's date
apt-config dump | grep -i automatic-reboot                    # the two lines of step 10
command -v git curl                                           # /usr/bin/git and /usr/bin/curl
```

`upgrade-stamp` is the file that apt's daily job touches each time
unattended-upgrades finishes a run without errors. It is what the heartbeat
looks at.

**Check:** `ssh server` opens a session, each command prints what its comment
says, and you can sign in to healthchecks.io with your second factor.

## 2. Create the ping key and the check

In the dashboard, at https://healthchecks.io. A new account has one project,
with an email integration to your address and a check named *My First Check*.

1. Open the project's **Settings**, at the top. In the table of keys, on the
   *Ping key* row, click **Create**. The key is shown in a dialog; you do not
   need to copy it, because the check's page shows it inside the URL.
2. Back in **Checks**, click **Add Check** and fill in:
   - **Name:** `service-host`
   - **Slug:** `service-host`
   - **Schedule:** Simple, with **Period** 5 minutes and **Grace Time** 10
     minutes.

   Then **Save**.
3. Open the new check. Under *Notification Methods*, the email integration
   with your address is on: a new check gets every integration of its
   project.
4. Where the page shows the check's URL, choose **slug** instead of **uuid**.
   The URL now has the form `https://hc-ping.com/<ping-key>/service-host`.
   Keep the page open for section 3.

*My First Check* never raises an alarm, because a check that has never
received a ping cannot be late. Remove it if you like, with **Remove** at the
bottom of its page.

**Check:** the check's page shows *Period* 5 minutes and *Grace Time* 10
minutes, its state is *new*, its email integration is on, and its URL in the
slug form ends in `/service-host`.

## 3. Put the URL in a file that only root can read

On the server. Read-only first:

```bash
ls -ld /etc/research-platform 2>/dev/null || echo "not there yet"    # not there yet
```

Then the folder, readable only by root, and an empty file in it:

```bash
sudo install -d -m 700 /etc/research-platform
sudo touch /etc/research-platform/heartbeat.env
sudo chmod 600 /etc/research-platform/heartbeat.env
sudo nano /etc/research-platform/heartbeat.env
```

In nano, write one line: `HEARTBEAT_URL=`, and right after it the URL, pasted
from the check's page, with no spaces or quotes. Save with Ctrl+O and Enter,
and leave with Ctrl+X. The URL goes through the editor, not through a
command, so it does not stay in the shell's history.

**Check:**

```bash
sudo stat -c '%a %U %n' /etc/research-platform /etc/research-platform/heartbeat.env
sudo grep -c '^HEARTBEAT_URL=https://hc-ping.com/' /etc/research-platform/heartbeat.env
```

The first prints `700 root /etc/research-platform` and
`600 root /etc/research-platform/heartbeat.env`; the second prints `1`. To
read the file, use `sudo cat` on your own screen only: a screenshot or a
paste in a chat would hand the URL out.

## 4. Install the script and the timer from a clone

Read-only first:

```bash
ls -d ~/src/research-platform 2>/dev/null || echo "no clone yet"                     # no clone yet
ls /usr/local/sbin /etc/systemd/system | grep heartbeat || echo "nothing installed"   # nothing installed
```

Clone this repository, and see which commit you are about to install:

```bash
git clone https://github.com/asegura-dev/research-platform.git ~/src/research-platform
cd ~/src/research-platform
git log -1 --format='%h %ad %s' --date=short
```

It must be the latest commit on the repository's page on GitHub. Then install
the script and the two units, owned by root:

```bash
sudo install -m 755 scripts/service-host-heartbeat.sh /usr/local/sbin/service-host-heartbeat
sudo install -m 644 config/systemd/service-host-heartbeat.service config/systemd/service-host-heartbeat.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

`daemon-reload` makes systemd read the new units. The timer stays off until
section 6, after the tests.

**Check:**

```bash
ls -l /usr/local/sbin/service-host-heartbeat /etc/systemd/system/service-host-heartbeat.*
systemctl list-unit-files 'service-host-heartbeat*' --no-pager
```

The script is `-rwxr-xr-x` and the two units `-rw-r--r--`, all of them
`root root`; `list-unit-files` lists the service as `static` and the timer as
`disabled`.

## 5. Try it by hand

What the script would send, without sending it:

```bash
sudo service-host-heartbeat --dry-run    # would send: success ok
```

If it names a check, fix that first (*If something goes wrong*). Then a real
ping, run by systemd the way the timer will run it:

```bash
sudo systemctl start service-host-heartbeat.service
systemctl status service-host-heartbeat.service --no-pager
```

`start` returns when the run ends. The status says `inactive (dead)`, and a
line ends in `status=0/SUCCESS`. In the dashboard, the check turns *up*
(green), and its log shows the ping, with the body `ok`. No email comes for
this one: healthchecks.io stays quiet when a new check comes up.

Now the alarm, with a ping that names a failed check, `test`:

```bash
sudo service-host-heartbeat --test-fail
```

The check turns *down* (red) at once, and an email says so. Bring it back up
with a real ping:

```bash
sudo systemctl start service-host-heartbeat.service
```

The check is *up* again, and a second email says so.

**Check:** both emails arrived. If not, look in the spam folder and mark them
as not spam: an alert that lands there is as good as none.

## 6. Turn on the timer

```bash
sudo systemctl enable --now service-host-heartbeat.timer
systemctl list-timers service-host-heartbeat.timer --no-pager
```

`enable` starts the timer at every boot, with a first run two minutes after
it; `--now` starts it now, and since those two minutes have passed, it runs
at once. Then one run every five minutes.

**Check:** `list-timers` shows the timer, with its next run less than five
minutes away, and ten minutes later the check's log shows two more pings.

## 7. Test the silence

Optional, and it takes 20 minutes. Stop the pings, as a power cut would:

```bash
sudo systemctl stop service-host-heartbeat.timer
```

Five minutes after the last ping the check turns *late*, and ten minutes
later *down*, with an email. Then start the pings again:

```bash
sudo systemctl start service-host-heartbeat.timer
```

The timer runs at once, because its time has passed.

**Check:** the *down* email arrived about 15 minutes after the last ping, and
the *up* email right after the timer started again.

## 8. Test a reboot

Optional. A reboot must not raise the alarm:

```bash
sudo reboot
```

Connect again three minutes later:

```bash
uptime -s                                                                     # when the server started
sudo journalctl -b -u service-host-heartbeat.service --no-pager | head -n 3   # its first run since then
systemctl list-timers service-host-heartbeat.timer --no-pager                 # its next run
```

**Check:** the first run came about two minutes after the start, the timer
shows its next run, and no email arrived.

## 9. Living with it

- **What an email says.** *Down* after the pings stopped: the host is off,
  without power or internet, or its timer stopped; look at the house first.
  *Down* after a ping that names checks: the ping's body, in the check's log,
  names them, and *If something goes wrong* says where to look, starting with
  `sudo service-host-heartbeat --dry-run`. A check stays down while the
  problem lasts, without an email at each ping, and the next good ping brings
  the *up* email.
- **Switching the host off on purpose** for more than 15 minutes: pause the
  check first, with **Pause** on its page. The first ping after the host comes
  back resumes it, without an email.
- **An update to the script or the units** comes with this repository: in
  `~/src/research-platform`, `git pull`, then section 4's three commands
  again.
- **If the URL leaks,** in a screenshot, a paste or a commit: in the project's
  **Settings**, revoke the ping key and create a new one, then write the new
  URL in the file with `sudo nano` (section 3). Until then, the old URL's
  pings are refused, and 15 minutes later the check goes down: the alarm
  working.
- **The log** keeps the last 100 pings on the free plan, about eight hours:
  enough to see when the pings stopped, and what the last ones said.
- **What healthchecks.io learns:** when the host is up, the names of the
  checks that fail, and the house's public address, which every ping comes
  from.

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 1 | `upgrade-stamp` is missing, or its date is older than yesterday | unattended-upgrades has not finished a run without errors lately. `systemctl list-timers apt-daily-upgrade.timer --no-pager` shows when it last ran, and `sudo tail -n 30 /var/log/unattended-upgrades/unattended-upgrades.log` what went wrong. Fix that first: the heartbeat would report it at once. |
| 1 | `apt-config` prints `E: Syntax error` | A typo in a file of `/etc/apt/apt.conf.d/`; the message names the file and the line. Fix it as in the server guide's step 10. |
| 2 | The slug form of the URL is missing, or asks for a slug | The project has no ping key yet, or the check has no slug: create the key (section 2, step 1), or set the slug in the check's *Name and Tags* dialog, with *edit…* next to its name. |
| 3 | `grep -c` prints `0` | The line does not start with `HEARTBEAT_URL=https://hc-ping.com/`: open the file again with `sudo nano` and write the line as section 3 says. |
| 5, any | `systemctl status` shows `status=1/FAILURE`, or another number | `sudo journalctl -u service-host-heartbeat.service -n 20 --no-pager` shows the message of the script or of `curl`: find it in this table. |
| 5, any | `service-host-heartbeat: no HEARTBEAT_URL in /etc/research-platform/heartbeat.env` | The file is missing or empty, or its line does not begin with `HEARTBEAT_URL=`: section 3. |
| 5, any | `curl: (22) The requested URL returned error: 404` | healthchecks.io has no check with that key and slug: the slug at the end must be the check's, `service-host`, and the key the project's current one. Copy the URL from the check's page into the file again (section 3). |
| 5, any | `curl: (22) The requested URL returned error: 429` | More than five pings in a minute: wait a minute, and try again. |
| 5, any | `curl: (6) Could not resolve host`, or `curl: (28)`, a timeout | The server cannot reach healthchecks.io: `ping -c 3 hc-ping.com` tells whether its internet is down. |
| 5, any | The dry run names `apt-config` | apt cannot read its configuration: `sudo apt-config dump >/dev/null` prints the file and the line (*Extra junk after value*, for instance). Fix that line as in the server guide's step 10, and run the dry run again. |
| 5, any | The dry run names `apt-sources` | apt cannot read one of its sources: `sudo apt-cache policy >/dev/null` names the file and the entry. Fix that file in `/etc/apt/sources.list.d/`, from its copy if you kept one. |
| 5, any | The dry run names `unattended-upgrades-stale` | No run of unattended-upgrades finished without errors in 60 hours: the first row of this table. After the host was off for days, it clears by itself within an hour or two of the boot, once the missed daily run catches up. |
| 5, any | The dry run names `reboot-pending` | A reboot has waited for two days. `cat /var/run/reboot-required.pkgs` names the updates that asked for it. unattended-upgrades schedules the 04:00 reboot at its daily run, even for an update installed by hand: check its policy with `apt-config dump \| grep -i automatic-reboot`, then reboot by hand when nothing important is running, with `sudo reboot`. |
| 5, any | The dry run names `disk-` and a number | The root file system is that full: `df -h /` and `sudo du -xh --max-depth=1 / \| sort -h \| tail` show where the space went; once Docker runs services, `sudo docker system df` too. |
| 5 | No email arrives | Look in the spam folder. In the dashboard, **Integrations** must list your address, and the check's *Notification Methods* must have it on. |
| 6 | `list-timers` does not list the timer, or shows no next run | `systemctl status service-host-heartbeat.timer --no-pager` says why; usually the `daemon-reload` of section 4 was skipped. |
| 9 | The check goes *down* and *up* again and again | One check is near its limit, usually the disk around 90%: the bodies of the pings, in the check's log, name it. Pause the check while you free space. |

## Next

The long runs on the workstation ping healthchecks.io one run at a time, with
the same ping key and a slug of their own, in the guide for operating long
runs. What comes before and after it is in the [roadmap](../roadmap.md).

## References

- healthchecks.io, *Pinging API* (the slug URL, `/fail`, the body of a ping,
  the answer to an unknown slug, the limit of pings per minute):
  https://healthchecks.io/docs/http_api/
- healthchecks.io, *Slug URLs* (the ping key):
  https://healthchecks.io/docs/slug_urls/
- healthchecks.io, *Configuring checks* (period, grace time, pausing):
  https://healthchecks.io/docs/configuring_checks/
- healthchecks.io, *Shell Scripts* (the `curl` options):
  https://healthchecks.io/docs/bash/
- healthchecks.io, *Pricing* (the Hobbyist plan's checks and log entries):
  https://healthchecks.io/pricing/
- systemd, `systemd.timer` (`OnBootSec=`, `OnUnitActiveSec=`, a timer started
  after its time has passed):
  https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html
- systemd, `systemd.service` (`Type=oneshot`):
  https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- apt, `apt.conf(5)` (turning off the cache files):
  https://manpages.ubuntu.com/manpages/noble/man5/apt.conf.5.html
- Ubuntu Server, *Automatic updates*:
  https://ubuntu.com/server/docs/how-to/software/automatic-updates/
