# ADR-016 - Backups stay at home, pulled by the service host over SSH

## Status

Accepted on 2026-11-27, when the backups, step 2 of the
[roadmap](../roadmap.md), began.

Supersedes in part
[ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md):
heavy data no longer stays only on the workstation, because its results get
a copy on the service host, and the backups have no copy away from home.

## Context

- What can be neither downloaded again nor rebuilt from a repository: the
  results of each training (its final checkpoint, of about 0.8 GB with
  ResEnc M, its logs and its predictions), the private note, and the service
  host's `/srv` ([Docker guide](../guides/install-docker.md)). The code lives
  on GitHub ([ADR-013](ADR-013-github-not-a-forge-at-home-for-private-code.md)),
  and a public dataset downloads again
  ([IDC guide](../guides/download-a-dataset-from-idc.md)). The thesis's
  results should add up to about 100 GB (an estimate, November 2026).
- The service host is always on, and its 512 GB SSD had about 400 GB free on
  2026-11-27. Its heartbeat fails when its disk is nearly full
  ([heartbeat guide](../guides/watch-the-service-host-with-healthchecks.md)).
  The workstation reboots, starts Windows, and stays off after a power cut.
- SSH on 2026-11-27: each computer in use reaches both hosts with a key of its
  own, and the workstation reaches the service host
  ([ADR-012](ADR-012-ssh-over-tailscale-with-a-key-per-computer.md)); the
  service host has no key. Ubuntu 24.04's `rsync` package brings `rrsync`,
  which confines a key to rsync in one folder, read-only if asked.
- A copy away from home, in November 2026: a Hetzner Storage Box of 1 TB for
  €3.20 a month before VAT, reached over SFTP, whose snapshots cannot be
  changed over SFTP; Backblaze B2 at US$6.95 per TB a month, whose Object
  Lock works against restic's `prune`; or a small computer in a relative's
  house, with restic's `rest-server` in append-only mode.

## Decision

**The copy of the results stays at home, on the service host, because losing
them with the house is accepted in exchange for no account, no bill and no
new service.** The copy covers what is likelier: the workstation's disk
dying, a folder deleted by mistake, a reinstall. A copy away from home is not
used here. If a project needs its results to survive the loss of the house,
restic on the service host can send its copy to a Hetzner Storage Box, whose
snapshots a stolen host cannot erase.

**The service host pulls the copy with rsnapshot over SSH, because then the
workstation cannot touch the copies, and a restore is a file copy.** Each
snapshot is a folder with the files as they were, in which a file that did
not change is a hard link to the one before and takes no space again.
Refused: restic, pushed by the workstation to a `rest-server` in append-only
mode on the service host. It keeps compressed versions that it can verify,
and it is the tool of a copy away from home, but it adds a service with its
own login, and a repository password whose loss loses every copy.

**The service host gets a key of its own, which the workstation accepts only
to read the results' folders through `rrsync -ro`, as every computer has its
own key (ADR-012).** The key has no passphrase, so that the pulls run
unattended; on a stolen service host, it reads those folders and opens
nothing else.

## Consequences

- The backups guide installs rsnapshot and its timer on the service host,
  creates its key, adds the key's line to the workstation, and tests a
  restore by predicting with a restored checkpoint
  ([roadmap](../roadmap.md)).
- A run's results reach the copy with the next pull, which the backups guide
  schedules. A pull while the workstation is off or in Windows fails, and the
  next one catches up.
- The service host's `/srv` and the private note need their copy on another
  machine, since a copy on their own disk does not survive it. The backups
  guide decides how.

## Trade-off

A fire, a theft or a surge that takes the house takes the results with both
hosts, and the weeks of GPU time behind them. rsnapshot keeps no checksums of
its own: only a restore shows that a copy still opens.

## Revisit when

A project needs its results to survive the loss of the house, or its data's
terms ask for a copy away from it; or the service host's disk runs short.
