# ADR-015 - Long runs are watched from outside their training, in a queue per GPU

## Status

Accepted on 2026-11-24, while writing the
[long runs guide](../guides/operate-long-runs.md). The thesis, the first
project, needs weeks of GPU time on the workstation, run after run, with
nobody watching ([roadmap](../roadmap.md)).

Supersedes in part
[ADR-006](ADR-006-public-repositories-on-github-private-on-forgejo.md), whose
`run-signals` repository is not created, and
[ADR-007](ADR-007-liveness-is-watched-from-outside.md), in how a run reports
itself and how its check stays quiet between runs.

## Context

- The workstation has two GPUs, an RTX 5080 and an RTX 4070. A run of the
  thesis lasts from hours to a day, and its experiment adds up to weeks of
  GPU time (as of November 2026).
- nnU-Net 2.8.1 prints a line when each epoch starts and ends, with its losses
  and pseudo Dice. It saves `checkpoint_latest` every 50 epochs, and continues
  a training with `--c` from `checkpoint_final`, else `checkpoint_latest`,
  else `checkpoint_best`.
- On 2026-11-04, a watcher that read those lines from outside a training sent
  through ntfy every notice of a short training on the workstation, of a
  failure and of a Ctrl+C.
- healthchecks.io, as of November 2026: a ping cannot pause a check, only the
  project's management API can, with a read-write key that can also change and
  remove every check of the project. A check that its first ping creates waits
  a day and an hour before its first alarm. A paused check resumes with its
  next ping.
- The workstation starts Windows at times, and stays off after a power cut by
  its firmware setting. Power in the house can drop several times in a row.

## Decision

**A run is watched from outside its training, because then a project changes
nothing in its code to use the platform.** `run-queue` starts the command with
its output going to a log, reads nnU-Net's lines from it, sends the notices
through ntfy
([ADR-014](ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md)),
and keeps a record of the run next to the log. Refused: `run-signals`, a
package inside the training with a notification port and a null adapter
(ADR-006, ADR-007). Every project would depend on it, and it would know no
more than the log says.

**Each GPU has a queue, named after its model and served by a systemd user
service, because a GPU that waits for someone to start its next run loses its
nights.** A queue stops at its first failure, because a run can depend on the
one before it, and does not start a run without enough free disk. Refused:
starting each run by hand, in tmux.

**The workstation stays off after a power cut until someone switches it on,
and when Ubuntu starts, each queue resumes its interrupted run with `--c`, up
to three times.** Power that drops several times in a row would start and
stop the machine each time. A resume costs at most the 50 epochs since the
last checkpoint, and a run that keeps bringing the machine down stops instead
of looping. A run that failed never resumes by itself. Refused: *Power On*
after a power cut.

**The workstation pings a check of its own every five minutes while Ubuntu
runs, and the check is paused by hand before the workstation is switched off
or starts Windows, because then its silence means that it died or froze.** A
training that stops advancing while the machine lives is announced by ntfy.
Refused: a check per run. Pausing it between runs would put the project's
read-write API key on the workstation, and it would need its timing set
through the same API to alarm in time.

**The platform records only what it alone knows about a run:** this
repository's commit, the GPU and its power limit, and each start, interruption,
resume and end. The project records its own environment, and runs the same
without the platform.

## Consequences

- `scripts/run-queue.py`, `scripts/workstation-heartbeat.sh` and the units in
  `config/systemd/user/` are installed by the long runs guide.
- The workstation's firmware keeps *Power Off* after a power cut, now for the
  reason above
  ([workstation guide](../guides/install-ubuntu-gpu-workstation.md),
  section 6).
- The workstation pings healthchecks.io with the project's ping key and a slug
  of its own, `workstation`
  ([heartbeat guide](../guides/watch-the-service-host-with-healthchecks.md)).
- A project's training command exits with a status other than 0 when it
  fails, takes its GPU from `CUDA_VISIBLE_DEVICES`, and continues with `--c`.
- A run's record, `platform.json`, sits next to its log, and its project can
  cite it.

## Trade-off

The watcher understands nnU-Net's lines only: another trainer gets a notice
when it starts and when it ends, until its lines are taught. A pause by hand
can be forgotten, and then one email comes, which the next ping clears. A
resumed run is not identical to one without cuts, because the order of its
patches and augmentations starts again; its record says where each
interruption was.

## Revisit when

A project trains with something other than nnU-Net and needs its epochs in
the notices; the workstation gets a UPS, which makes *Power On* safe;
healthchecks.io lets a ping pause a check; or runs start to need a fourth
resume.
