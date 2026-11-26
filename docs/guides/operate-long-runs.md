# Operate long runs on the workstation

> **Scope:** the GPU workstation. At the end, each GPU has a queue that runs
> its trainings one after another, by itself and without a session. Each run
> tells the phone how it goes, and after a power cut it resumes from its last
> checkpoint once Ubuntu starts again. The workstation pings healthchecks.io
> every five minutes while Ubuntu runs, and an email reaches you when it goes
> silent.

> **Status:** written on 2026-11-24 from the documentation of systemd,
> `nvidia-smi`, healthchecks.io and ntfy, and from nnU-Net 2.8.1's code.
> `run-queue` grew from a watcher tried on the workstation on 2026-11-04,
> which sent every notice of a short training, of a failure and of a Ctrl+C.
> First run on 2026-11-25 and 2026-11-26, sections 1 to 9: every notice
> reached the phone, a failure held its queue, a stopped run and a killed one
> resumed from their checkpoints, the queues started by themselves after a
> reboot, and the check went down on a test failure and up again, each time
> with an email. Section 9's first pings failed because the workstation's name
> lookups took minutes, until it restarted. Revised from that run: section 3
> gives its notices a quarter of an hour, section 5 waits for the queues to
> start, `watch` writes its record from the start, `list` says which epoch a
> run is in, and *If something goes wrong* covers slow name lookups. The
> rehearsal, section 10, is pending.

The thesis needs weeks of GPU time, in runs of hours to a day each. Nobody
watches them, so the platform does three things for them
([ADR-015](../adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md)):

- **`run-queue` watches a run from outside.** It starts the command with its
  output going to a log, reads nnU-Net's lines from that log, and sends the
  notices through ntfy, with the file that `notify` reads
  ([ntfy guide](install-ntfy.md), section 7). Next to the log it keeps the
  run's record, `platform.json`. A project changes nothing in its code.
- **Each GPU has a queue,** named after its model: `5080` and `4070`. A
  systemd user service, `run-queue@5080` or `run-queue@4070`, runs the queue's
  runs one after another, starts with the workstation, and goes on when you
  log out.
- **`workstation-heartbeat`** pings healthchecks.io every five minutes while
  Ubuntu runs, like the service host's heartbeat. The service host's already
  emails when the house loses its power or its internet; this one emails when
  the workstation alone dies or freezes.

After a power cut, the workstation stays off until you switch it on
([workstation guide](install-ubuntu-gpu-workstation.md), section 6). When
Ubuntu starts, each queue resumes its interrupted run from the last
checkpoint, which nnU-Net saves every 50 epochs.

What leaves the workstation: a notice carries a run's name, a status, numbers
and the GPU's model; a ping carries `ok`, or the names of the checks that
failed. Neither carries paths, study identifiers or patient data
([ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md),
[ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md)). A run's name
goes in every notice, so it says what the run is, never whose data it reads.

Every command runs on the workstation, in a terminal of your own user, never
with `sudo` unless the block shows it; the dashboard of healthchecks.io opens
in a browser. Every section ends with a check, and read-only commands come
first. The tries use the benchmark dataset of the
[validation guide](validate-gpu-workstation.md), Spleen, with results in a
folder of their own, so nothing of the validation's results is touched.

Never commit the ping URL, the ping key or your email address to this
repository.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| How a run is watched | From outside: `run-queue` reads what the command prints | A project changes nothing in its code, and runs the same without the platform | [ADR-015](../adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md) |
| How runs follow each other | One queue per GPU, served by `run-queue@5080` and `run-queue@4070`. A queue stops at its first failure, and does not start a run with less than 50 GB free | A run can depend on the one before it, and a full disk kills a run when it saves a checkpoint | [ADR-015](../adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md) |
| Without a session | systemd user services, with lingering on for your user | They start at boot before anyone logs in, and go on after you log out | This guide |
| After a power cut | The workstation stays off until you switch it on; when Ubuntu starts, the queue resumes the run with `--c` | Power that drops several times in a row would start the machine each time. A resume costs at most the 50 epochs since the last checkpoint | [ADR-015](../adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md) |
| How many resumes | Three per run. A run that failed never resumes by itself | A run that keeps bringing the machine down stops instead of looping | This guide |
| The notices | At the start, every 50 epochs with the pseudo Dice and the losses, at the end, and at a failure; when a training stops advancing; the epoch notices carry the GPU's highest temperature, any slowdown for heat, and the free disk | nnU-Net saves `checkpoint_latest` every 50 epochs; heat and disk are what fails without a sound over weeks | This guide |
| The heartbeat | A check named `workstation`, period 5 minutes and grace time 10, paused by hand before the workstation is switched off or starts Windows | Its silence means that the workstation died or froze; a paused check resumes with its next ping | [ADR-015](../adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md) |
| What the platform records | `platform.json`, next to the run's log: this repository's commit, the GPU and its power limit, and each start, interruption, resume and end | The project records its own environment, and can cite this record | [ADR-015](../adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md) |

## 1. What you need

- The workstation installed and validated: the workstation guide through
  section 20, and the validation guide's section 6, which built the
  benchmark project in `~/bench/nnunet` with Spleen preprocessed.
- ntfy reaching the phone from the workstation: the ntfy guide's sections 7
  and 8, with `~/.config/research-platform/ntfy.env`.
- The healthchecks.io project with its ping key: the heartbeat guide's
  sections 1 and 2.
- A clone of this repository in `~/src/research-platform`, with its guard
  (guard guide).

Read-only:

```bash
python3 --version                                                    # Python 3.12.3
stat -c '%a' ~/.config/research-platform/ntfy.env                    # 600
ls ~/bench/nnunet/.venv/bin/nnUNetv2_train ~/bench/nnunet/env.sh     # both listed
ls ~/bench/nnunet/data/preprocessed/Dataset009_Spleen | head -n 3    # its files
nvidia-smi --query-gpu=name,temperature.gpu,clocks_event_reasons.sw_thermal_slowdown,clocks_event_reasons.hw_thermal_slowdown --format=csv,noheader
loginctl show-user "$USER" -p Linger                                 # Linger=no, until section 4
```

The `nvidia-smi` line prints one line per GPU: its name, its temperature, and
`Not Active` twice, the two kinds of slowdown for heat. `run-queue` reads the
same fields; if a driver lacks the last two, its notices carry the
temperature alone.

**Check:** each command prints what its comment says, and the `nvidia-smi`
line names both GPUs.

## 2. Install `run-queue` and the heartbeat

```bash
cd ~/src/research-platform && git pull
git status --short                                  # nothing: what you install is a commit
git log -1 --format='%h %ad %s' --date=short
```

The last commit must be the one on the repository's page on GitHub. Then the
two scripts, into the folder where `notify` already is, and the commit they
came from, which each run's record cites:

```bash
install -m 755 scripts/run-queue.py ~/.local/bin/run-queue
install -m 755 scripts/workstation-heartbeat.sh ~/.local/bin/workstation-heartbeat
mkdir -p ~/.local/share/research-platform
git log -1 --format='%H %cs' > ~/.local/share/research-platform/installed-commit
```

`run-queue` uses only Python's standard library, so it runs with Ubuntu's own
`python3`, outside any project's environment.

**Check:**

```bash
command -v run-queue workstation-heartbeat                       # both in ~/.local/bin
run-queue list                                                   # no queues yet: run-queue add QUEUE NAME -- command
cut -c1-7 ~/.local/share/research-platform/installed-commit      # the commit that git log printed
```

## 3. Watch a short training in this terminal

`run-queue watch` runs a command now, in the terminal, and watches it as a
queue would. In a new terminal:

```bash
cd ~/bench/nnunet && source env.sh
export nnUNet_results="$HOME/bench/nnunet/data/runs"
run-queue watch spleen-try --gpu 5080 --epochs 5 --every 2 -- \
    ~/bench/nnunet/.venv/bin/nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_5epochs
```

`--gpu 5080` sets `CUDA_VISIBLE_DEVICES` to that GPU's UUID, which
`run-queue` asks `nvidia-smi` for; `--every 2` sends an epoch notice every
two epochs, instead of 50, for the try. The terminal shows nnU-Net's output
as it goes, and five notices reach the phone in about a quarter of an hour,
the last one after nnU-Net's final validation:

- *spleen-try started*: `nnUNetv2_train on the RTX 5080, with a notice every 2 epochs, 5 epochs planned.`
- *spleen-try: epoch 2 of 5* and *epoch 4 of 5*: the pseudo Dice, the best EMA
  pseudo Dice, the losses, the last epoch's time and the training left, the
  GPU's highest temperature since the last notice and whether heat slowed it,
  and the free disk.
- *spleen-try: training done*, when nnU-Net prints `Training done.`; its final
  validation comes next.
- *spleen-try finished*, with how long it took.

The log and the record went to a folder of their own:

```bash
ls ~/.local/state/research-platform/runs/                                   # spleen-try- and the time, in UTC
cat ~/.local/state/research-platform/runs/spleen-try-*/platform.json
```

The record has two events: `started`, with this repository's commit, the
GPU's name and its power limit, and `ended`, with `"how": "finished"` and 5
epochs. A watched run dies with its terminal, and says so with a *stopped*
notice; a run longer than a sitting goes in a queue.

**Check:** the five notices arrived, the epoch notices carry a temperature
and the free disk, and the record says `finished`.

## 4. Let your services run without a session

systemd runs a service manager for your user, and with it your user services,
only while you are logged in. *Lingering* starts it at boot, before anyone
logs in, and keeps it after you log out:

```bash
sudo loginctl enable-linger "$USER"
```

**Check:** `loginctl show-user "$USER" -p Linger` prints `Linger=yes`.

## 5. Start a queue for each GPU

The unit is a template: `run-queue@5080` and `run-queue@4070` are two
instances of it, one per GPU.

```bash
mkdir -p ~/.config/systemd/user
install -m 644 ~/src/research-platform/config/systemd/user/run-queue@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now run-queue@5080 run-queue@4070
```

`enable` starts both at every boot, and `--now` starts them now.

**Check:**

```bash
sleep 5                                                            # the queues take a few seconds to start
systemctl --user is-active run-queue@5080 run-queue@4070          # active, twice
journalctl --user -u run-queue@5080 -n 3 --no-pager -o cat        # run-queue: queue 5080: the RTX 5080, waiting for runs
run-queue list                                                     # queue 4070: idle, and queue 5080: idle
```

## 6. A run through a queue

`run-queue add` puts a run at the end of a queue. It takes with it the folder
you are in and the variables of your shell, without those of the session
(`SSH_*`, `DISPLAY` and the like), so load the project's environment first:

```bash
cd ~/bench/nnunet && source env.sh
export nnUNet_results="$HOME/bench/nnunet/data/runs"
run-queue add 5080 spleen-q1 --epochs 5 --every 2 -- \
    ~/bench/nnunet/.venv/bin/nnUNetv2_train 9 3d_fullres 1 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_5epochs
```

It answers `spleen-q1 waits in queue 5080, the RTX 5080, behind 0 other
run(s)`, and the log's path. The run starts within 15 seconds, with the same
notices as in section 3, and a sixth one when nothing else waits: *Queue 5080
is empty*. While it runs:

```bash
run-queue list                                                       # running spleen-q1, and its epoch
tail -f ~/.local/state/research-platform/runs/spleen-q1/output.log   # its output; Ctrl+C stops tail, not the run
```

Close the terminal if you like: the run goes on.

**Check:** the notices arrived, and `run-queue list` shows
`done     1 run(s), the last spleen-q1`.

## 7. A failure holds the queue

Two runs: the first asks for a plan that does not exist, so it fails at
once; the second waits behind it.

```bash
cd ~/bench/nnunet && source env.sh
export nnUNet_results="$HOME/bench/nnunet/data/runs"
T=~/bench/nnunet/.venv/bin/nnUNetv2_train
run-queue add 5080 spleen-bad -- "$T" 9 3d_fullres 2 -p nnUNetResEncUNetMPlans_missing -tr nnUNetTrainer_5epochs
run-queue add 5080 spleen-after --epochs 5 --every 0 -- "$T" 9 3d_fullres 2 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_5epochs
```

*spleen-bad failed* arrives, with a higher priority: `Exit status 1 after …,
before the first epoch. Error: FileNotFoundError.`, and how to go on. The
queue now holds, and `spleen-after` does not start:

```bash
run-queue list        # queue 5080: holds (failed spleen-bad), failed spleen-bad, pending spleen-after
```

Either `run-queue retry spleen-bad` puts the failed run back at the front,
from the start, or `run-queue retry spleen-bad --resume` from its last
checkpoint; or the queue goes on without it:

```bash
run-queue release 5080
```

`spleen-after` starts, with no epoch notices (`--every 0`). `spleen-bad` stays
in the failed list, where it holds nothing.

**Check:** *spleen-after finished* arrived after the release, not before.

## 8. A stop and a power cut, and the resumes

A run of 20 epochs, interrupted twice: once by a stop, as a shutdown would,
and once by a kill, as a power cut would.

```bash
cd ~/bench/nnunet && source env.sh
export nnUNet_results="$HOME/bench/nnunet/data/runs"
run-queue add 5080 spleen-cut --epochs 20 --every 5 -- \
    ~/bench/nnunet/.venv/bin/nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_20epochs
```

When *spleen-cut: epoch 5 of 20* arrives, stop the queue:

```bash
systemctl --user stop run-queue@5080
```

`stop` returns once the run has ended, and *spleen-cut interrupted* arrives:
`Stopped in epoch 6 of 20 by SIGTERM. It resumes from its last checkpoint when
queue 5080 starts again.` `run-queue list` shows the run still running, and
that its service is not. Start the queue again:

```bash
systemctl --user start run-queue@5080
```

*spleen-cut resumed* arrives: `After an interruption in epoch 6 of 20, from its
last checkpoint, on the RTX 5080 (resume 1 of 3).` When *epoch 10 of 20*
arrives, kill everything of the queue at once, as a power cut would:

```bash
systemctl --user kill --signal=SIGKILL run-queue@5080
```

No notice comes for this one: nothing is left to send it. systemd starts the
queue again 30 seconds later, as it would at boot, and *spleen-cut resumed*
arrives again, with `(resume 2 of 3)`. Then the run finishes.

nnU-Net saves `checkpoint_latest` every 50 epochs, so before epoch 50, `--c`
goes back to `checkpoint_best`, the epoch of the best EMA pseudo Dice so far,
usually the last one. Section 10 resumes from a `checkpoint_latest`.

**Check:**

```bash
python3 -m json.tool ~/.local/state/research-platform/runs/spleen-cut/platform.json | grep -E '"(event|epochs_done|clean)"'
```

The events are `started`; `interrupted`, with `"clean": true` and the epochs
done; `resumed`, with the epochs its checkpoint had done; `interrupted` again,
with `"clean": false`; `resumed`; and `ended`, with 20 epochs. Each `resumed`
says where the training went on from, so the record shows what each cut cost.

## 9. The workstation's heartbeat

In the healthchecks.io dashboard, in the project whose ping key the service
host uses: **Add Check**, with **Name** `workstation`, **Slug** `workstation`,
and a **Simple** schedule of **Period** 5 minutes and **Grace Time** 10
minutes; then **Save**. On the check's page, choose **slug** instead of
**uuid** where it shows the URL: it has the form
`https://hc-ping.com/<ping-key>/workstation`.

Then the file that holds it, readable only by you:

```bash
ls ~/.config/research-platform/heartbeat.env 2>/dev/null || echo "not there yet"   # not there yet
( umask 077; printf 'HEARTBEAT_URL=\n' > ~/.config/research-platform/heartbeat.env )
nano ~/.config/research-platform/heartbeat.env
```

In nano, right after `HEARTBEAT_URL=`, paste the URL from the check's page.
Save with Ctrl+O and Enter, and leave with Ctrl+X. Check it without showing
it:

```bash
stat -c '%a' ~/.config/research-platform/heartbeat.env       # 600
sed -n 's/^HEARTBEAT_URL=//p' ~/.config/research-platform/heartbeat.env | tr -d "[:space:]\"'" | awk -F/ '{print $3, length($4), $5}'
```

The second prints `hc-ping.com 22 workstation`: the host, the length of the
key and the slug. Then the timer and its service, and a try:

```bash
install -m 644 ~/src/research-platform/config/systemd/user/workstation-heartbeat.service ~/src/research-platform/config/systemd/user/workstation-heartbeat.timer ~/.config/systemd/user/
systemctl --user daemon-reload
workstation-heartbeat --dry-run                         # would send: success ok
systemctl --user start workstation-heartbeat.service
```

The check turns *up*. Now the alarm, and back:

```bash
workstation-heartbeat --test-fail
systemctl --user start workstation-heartbeat.service
```

The first turns the check *down* at once, with an email; the second brings
it *up*, with another. Then the timer, which pings two minutes after each
boot and every five minutes after that:

```bash
systemctl --user enable --now workstation-heartbeat.timer
sleep 5; systemctl --user list-timers workstation-heartbeat.timer --no-pager
```

**Check:** both emails arrived, `list-timers` shows the next run less than
five minutes away, and ten minutes later the check's log shows two more pings.

## 10. Rehearse the operation: both GPUs, for hours

The rehearsal runs everything at once for about four hours: both queues with
two runs each, a long one on each GPU, a power cut on purpose after the
5080's run has saved a `checkpoint_latest`, and the validation's monitor
logging every second. It trains Spleen, not the thesis's data.

The monitor goes in tmux, so that it survives a closed terminal: open it with
`tmux new -A -s rehearsal`. In its window 0, the start time and the monitor:

```bash
date '+%F %T' > ~/bench/logs/rehearsal-start
~/bench/monitor.sh rehearsal
```

Window 1 (Ctrl+b then c), the four runs:

```bash
cd ~/bench/nnunet && source env.sh
export nnUNet_results="$HOME/bench/nnunet/data/runs"
T=~/bench/nnunet/.venv/bin/nnUNetv2_train
run-queue add 5080 rehearsal-5080-long --epochs 250 -- "$T" 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_250epochs
run-queue add 5080 rehearsal-5080-short --epochs 10 --every 5 -- "$T" 9 3d_fullres 2 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_10epochs
run-queue add 4070 rehearsal-4070-long --epochs 100 -- "$T" 9 3d_fullres 1 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_100epochs
run-queue add 4070 rehearsal-4070-short --epochs 10 --every 5 -- "$T" 9 3d_fullres 3 -p nnUNetResEncUNetMPlans -tr nnUNetTrainer_10epochs
run-queue list
```

The long runs notify every 50 epochs, the default. After
*rehearsal-5080-long: epoch 100 of 250* arrives, and before epoch 150, the
power cut on purpose:

```bash
systemctl --user kill --signal=SIGKILL run-queue@5080
```

Half a minute later, *rehearsal-5080-long resumed* arrives, and the run goes
on from epoch 100. Log out of the desktop and back in while it runs, if you
like: nothing stops. When both *Queue … is empty* notices have arrived, stop
the monitor with Ctrl+C in window 0, and look:

```bash
S=$(cat ~/bench/logs/rehearsal-start)
journalctl -k --since "$S" | grep -iE 'NVRM|Xid|AER|machine check|hardware error|EDAC|nvme|I/O error'   # nothing
journalctl -u systemd-oomd --since "$S" --no-pager | grep -i killed                                     # nothing
~/bench/summary.sh rehearsal 300
python3 -m json.tool ~/.local/state/research-platform/runs/rehearsal-5080-long/platform.json | grep -E '"(event|epochs_done|clean)"'
run-queue list
```

The kernel lines and `systemd-oomd` are the validation's section 11 checks.
`summary.sh` gives each GPU's peak temperature and the clock event reasons, to
compare with the soak. The long run's record shows `interrupted`, with
`"clean": false` and the epochs done when it was cut, then `resumed`, with
`"epochs_done": 100`, and `ended` with 250.

**Check:** the four runs finished, in order on each GPU; the long run lost at
most 50 epochs to the cut; every epoch notice arrived with its temperature;
the kernel logged no error and `systemd-oomd` killed nothing; the heartbeat
sent no email.

## 11. Living with it

- **A project's runs** go in a queue from the project's folder, with its
  environment loaded: `run-queue add QUEUE NAME --epochs N --log FILE --
  command`. The run takes the folder and the environment with it. `--log`
  puts its output, and `platform.json` next to it, in the project's own run
  folder: one folder per run.
- **The notices a run sends:**
  - `--every 0` sends none per epoch, for series of many runs;
  - `--progress-only` leaves out the pseudo Dice and the losses, for runs
    whose metric must not be seen while they run;
  - `--generic` is for jobs that are not trainings, such as an inference: a
    notice when they start and when they end, no stall notice, and no resume
    after an interruption.
- **A training that stops advancing,** with no new epoch for an hour before
  its first, or for five times a recent epoch and at least 20 minutes after
  that, sends *no progress*. It is only a notice: the run goes on, and
  *advancing again* follows if it does. `run-queue cancel NAME` ends it.
- **Switching the workstation off, or starting Windows:** pause the
  `workstation` check first, with **Pause** on its page; the first ping after
  Ubuntu is back resumes it. A run that is running is interrupted, and resumes
  when Ubuntu starts again; that counts as one of its three resumes. Its
  *interrupted* notice may not leave before the network goes down; the
  *resumed* one says where it was.
- **Before an update of the driver or the kernel,** between runs
  (workstation guide, section 23): `run-queue hold 5080` and
  `run-queue hold 4070`, wait until `run-queue list` shows neither running,
  pause the check, update and reboot, then `run-queue release` both.
- **An update to `run-queue`** comes with this repository: `git pull`, then
  section 2's four lines. A queue takes the new version when it starts again:
  `systemctl --user restart run-queue@5080 run-queue@4070`, best while both
  are idle, because a restart interrupts a running run.
- **A run that needs more than three resumes** fails with *Interrupted 4
  times*. `run-queue retry NAME --resume` gives it three more.
- **Where things live:** each queue's runs in
  `~/.local/share/research-platform/queues/`, one file per run, and the
  output and record of a run without `--log` in
  `~/.local/state/research-platform/runs/NAME/`. A run's file holds its
  command and its environment, readable only by you.
- **If the ping URL leaks:** in the project's **Settings**, revoke the ping key
  and create a new one, then write the new URLs in both hosts' files: this
  guide's section 9, and the heartbeat guide's section 3.
- **What healthchecks.io learns:** when the workstation is up and its disk
  nearly full, and the house's public address.

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 2, any | `run-queue: command not found` | `~/.local/bin` is not on the shell's path yet: open a new terminal. If it still fails, repeat section 2's `install` lines. |
| 3, 5, any | `nvidia-smi lists no single GPU named 5080` | `nvidia-smi -L` must list both GPUs: if it lists none, the driver is not loaded (workstation guide, section 18). A queue whose GPU is missing waits, and looks again every minute. |
| 3, 5, any | `NTFY_URL, NTFY_TOPIC and NTFY_TOKEN must be set` | `~/.config/research-platform/ntfy.env` is missing a line or a value: the ntfy guide's section 7. A queue's service stops for good on this error: `systemctl --user restart` it once the file is fixed. |
| 3, any | Notices do not arrive, and the terminal says `not sent (HTTP 401)` or `(HTTP 403)` | The token or the topic: the ntfy guide's *If something goes wrong*. A queue writes the same lines to its journal: `journalctl --user -u run-queue@5080 --no-pager -o cat \| grep 'not sent'`. |
| 4 | `Linger=no` after `enable-linger` | Run it again with `sudo`, and check that `"$USER"` is your user: `echo "$USER"`. |
| 5, any | `systemctl --user` says `Failed to connect to bus` | The command ran as another user, for instance inside `sudo -i`: run it as yourself, in a terminal or an SSH session of your own. |
| 5, any | `is-active` says `failed` | `journalctl --user -u run-queue@5080 -n 20 --no-pager -o cat` says why: find the message in this table. |
| 6, any | `add` says `… is not a command that this environment can run` | Give the command's full path, as section 6 does, or load the project's environment first. |
| 6, any | `add` says `… belongs to another run` | That `--log` folder already has another run's `platform.json`: give each run a folder of its own. |
| 6, any | `add` says `queue 5080's service is not running` | `systemctl --user start run-queue@5080`. The run waits in the queue until then. |
| 6, any | *Queue 5080 holds*: `… needs 50 GB free to start` | The disk is nearly full: `df -h ~` and `du -sh ~/data/* ~/bench/*` show where the space went. Free some, then `run-queue release 5080`. |
| 7, any | A run fails at once with `Exit status 127` or `did not start` | The program is not where the run's file says: `run-queue list` names the run, and its log the error. Add it again with the right path, under another name. |
| 8, any | After `systemctl --user kill`, the queue does not come back | `systemctl --user status run-queue@5080 --no-pager` must say `activating (auto-restart)`, then `active`. If it says `failed`, the unit lacks `Restart=on-failure`: install it again (section 5) and `daemon-reload`. |
| 8, any | The resumed run starts from epoch 0 | It found no checkpoint: nnU-Net printed `Cannot continue training`. Its `nnUNet_results` must be the same as when it was added, which the run's file keeps. |
| 9 | The second command prints something other than `hc-ping.com 22 workstation` | The URL is not the check's slug URL: copy it again, with **slug** chosen, into the file with `nano`. |
| 9, any | `curl: (22) The requested URL returned error: 404` | healthchecks.io has no check with that key and slug: the slug must be `workstation`, in the same project as the service host's. |
| 9, any | `curl: (22) … 429` | More than five pings in a minute: wait a minute. |
| 9, any | The service fails, or the check goes down while the workstation is up, and `journalctl --user -u workstation-heartbeat -n 20 --no-pager -o cat` shows `curl: (28) Resolving timed out` | Name lookups take too long on the workstation: `resolvectl query --cache=no hc-ping.com` says how long one takes. A failed ping now and then raises no alarm, since the email waits for 15 minutes without any. If they keep failing, restart the workstation and look again. |
| 10, any | A run failed with `Killed by SIGKILL`, and `systemd-oomd` says it killed it | Memory ran out under two trainings: the validation guide's `nnUNet_n_proc_DA` sets how many processes each one starts. Lower it in `~/bench/nnunet/env.sh`, `source` it, and add the run again under another name, with `--c` at the end of its command, so that it goes on from its last checkpoint with the new value: a run's file keeps the environment it was added with. |
| 11 | No queue started after a reboot | `loginctl show-user "$USER" -p Linger` must say `yes`, and `systemctl --user is-enabled run-queue@5080` must say `enabled`: sections 4 and 5. |

## Next

The backups: a copy of the results away from the house, with a restore
tested by predicting with a restored checkpoint. What comes after them is in
the [roadmap](../roadmap.md).

## References

- systemd, `systemd.service` (`Restart=on-failure`,
  `RestartPreventExitStatus=`, `Type=oneshot`):
  https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- systemd, `systemd.kill` (`KillMode=mixed`):
  https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html
- systemd, `systemd.timer` (`OnBootSec=`, `OnUnitActiveSec=`):
  https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html
- systemd, `loginctl` (`enable-linger`):
  https://www.freedesktop.org/software/systemd/man/latest/loginctl.html
- systemd, `systemd.unit` (templates, `%i` and `%h`):
  https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html
- NVIDIA, `nvidia-smi` (the query fields, in `nvidia-smi --help-query-gpu`):
  https://docs.nvidia.com/deploy/nvidia-smi/index.html
- nnU-Net 2.8.1, `run_training.py` (`--c`: `checkpoint_final`, then
  `checkpoint_latest`, then `checkpoint_best`):
  https://github.com/MIC-DKFZ/nnUNet/blob/v2.8.1/nnunetv2/run/run_training.py
- nnU-Net 2.8.1, `nnUNetTrainer.py` (`save_every = 50`, the lines it prints at
  each epoch):
  https://github.com/MIC-DKFZ/nnUNet/blob/v2.8.1/nnunetv2/training/nnUNetTrainer/nnUNetTrainer.py
- nnU-Net 2.8.1, the trainers of fixed length (`nnUNetTrainer_5epochs` to
  `nnUNetTrainer_8000epochs`):
  https://github.com/MIC-DKFZ/nnUNet/blob/v2.8.1/nnunetv2/training/nnUNetTrainer/variants/training_length/nnUNetTrainer_Xepochs.py
- healthchecks.io, *Pinging API* (the slug URL, `/fail`):
  https://healthchecks.io/docs/http_api/
- healthchecks.io, *Configuring checks* (period, grace time, pausing):
  https://healthchecks.io/docs/configuring_checks/
- healthchecks.io's source, where a ping resumes a paused check unless it has
  `manual_resume` (`Check.ping` in `hc/api/models.py`):
  https://github.com/healthchecks/healthchecks/blob/master/hc/api/models.py
- ntfy, *Publishing* (title, priority and authentication):
  https://docs.ntfy.sh/publish/
