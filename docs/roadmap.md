# Roadmap

What the platform is for, what it still needs, in what order, and what was
considered and refused. A ticked item has been done on the real hardware.
Whatever is adopted gets its guide, and its decision record when there is a
choice worth keeping.

## The goal: the thesis's first long training runs supervised

The platform is for long trainings that nobody watches: days of nnU-Net on the
workstation. While one runs, the phone hears how it goes and when it fails, a
silence raises an alarm, a power cut costs only the epochs since its last
checkpoint, the environment it ran in is recorded, and its results survive
the loss of the house. The thesis is the first project that needs it. The
service host runs the services that make it possible, and later others, each
with its guide. Once the thesis's runs hold, version 1.0 makes it a platform
that any project can use and cite.

### What already holds

- [x] The service host runs Ubuntu Server, comes back by itself after a power
  cut, and installs its security updates on its own
  ([server guide](guides/install-ubuntu-server.md);
  [ADR-008](adr/ADR-008-a-service-host-comes-back-on-its-own.md),
  [ADR-011](adr/ADR-011-the-service-host-runs-without-secure-boot.md)).
- [x] The workstation runs Ubuntu on its own SSD with both GPUs working, and
  Windows still starts from the firmware's menu
  ([workstation guide](guides/install-ubuntu-gpu-workstation.md), sections 1
  to 20).
- [x] The workstation is validated: memory, SSD and GPUs pass their tests, and
  two trainings hold for three hours
  ([validation guide](guides/validate-gpu-workstation.md), sections 1 to 9
  and 11).
- [x] Every computer in use reaches both hosts with its own SSH key, from
  inside and outside the house
  ([Tailscale guide](guides/install-tailscale.md);
  [ADR-012](adr/ADR-012-ssh-over-tailscale-with-a-key-per-computer.md);
  workstation guide, section 22). The phone joined the tailnet for ntfy; its
  SSH waits until it is needed.
- [x] Docker is installed on the service host, publishes every port on
  127.0.0.1 by default, and brings its containers back after a reboot
  ([Docker guide](guides/install-docker.md)).
- [x] The service host pings healthchecks.io every five minutes, and its
  silence arrives by email
  ([heartbeat guide](guides/watch-the-service-host-with-healthchecks.md);
  [ADR-007](adr/ADR-007-liveness-is-watched-from-outside.md)). The ping also
  fails when the host stops looking after itself: apt broken, automatic
  updates stopped, a reboot pending for days, or its disk nearly full.
- [x] ntfy runs on the service host, listens on 127.0.0.1 and is published
  only to the tailnet, with Tailscale Serve. It refuses whoever it does not
  know: the phone reads with a password, and the workstation publishes with a
  token. A command that ends on the workstation shows on the phone
  ([ntfy guide](guides/install-ntfy.md);
  [ADR-014](adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md)).
- [x] This repository refuses instance data: a hook checks each commit before
  it is made, and a workflow checks each push
  ([guard guide](guides/set-up-the-instance-data-guard.md)). Private
  repositories live on GitHub too
  ([ADR-006](adr/ADR-006-public-repositories-on-github-private-on-forgejo.md),
  [ADR-013](adr/ADR-013-github-not-a-forge-at-home-for-private-code.md)).

### What is left, in this order

The thesis's pilot does not wait for steps 2 to 4: they are done while its
first runs train.

1. **Long runs: trainings run for days, one after another, without anyone
   watching** ([long runs guide](guides/operate-long-runs.md);
   [ADR-015](adr/ADR-015-long-runs-are-watched-from-outside-in-a-queue-per-gpu.md)).
   - [x] Each GPU has its own queue. Its runs start one after another by
     themselves, and keep running when the session that started them closes.
     A queue stops at its first failure, and does not start a run without
     enough free disk.
   - [ ] A training notifies when it starts, every 50 epochs with its metric,
     when it ends and when it fails; one whose metric must stay unseen while
     it runs notifies its progress alone. A training that stops advancing is
     announced too, and a job that is not a training notifies its start, its
     end and its failure.
   - [x] Its notices say how hot its GPU ran since the previous one, whether
     the GPU slowed down for heat, and how much disk is free.
   - [x] The workstation pings healthchecks.io every few minutes while Ubuntu
     runs, so that its silence raises the alarm
     ([ADR-007](adr/ADR-007-liveness-is-watched-from-outside.md)). Its check
     is paused by hand before the workstation is switched off or starts
     Windows, and resumes by itself with the next ping.
   - [x] After a power cut, the workstation stays off until someone switches
     it on, so that repeated drops of power do not start it each time
     ([workstation guide](guides/install-ubuntu-gpu-workstation.md), section
     6). When Ubuntu starts, the queue resumes the interrupted run from its
     last checkpoint.
   - [x] Each run leaves a record of what only the platform knows: this
     repository's commit, the GPU and its power limit, and how the run went:
     its start, each interruption and resume with its epoch, its end and its
     exit status. The project records its own environment (its commit, the
     kernel, the driver, and the versions of CUDA, PyTorch and nnU-Net), and
     can cite this record.

   A watcher outside the training, `run-queue`, sends these signals, so a
   project changes nothing in its code: `run-signals`, a package inside the
   training, is not created. The ticked items passed sections 1 to 9 of the
   guide. Still to be seen on the workstation: the notices of a training that
   shows only its progress, of a job that is not a training, and of a training
   that stops advancing.
2. **Backups: results survive the loss of the house.**
   - [ ] Results, the private note and the service host's `/srv` have a copy
     away from home, and a restore has been tested (backups, an open
     decision).
   - [ ] The service host holds a second copy at home, and sends the copy away
     from home itself, even while the workstation trains. The backups' record
     supersedes in part
     [ADR-004](adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md),
     which keeps heavy data on the workstation.
   - [ ] Of each training, the copy keeps its final checkpoint, its logs and
     its predictions. A checkpoint that later runs depend on is copied as
     soon as its run ends, and the restore is tested by predicting with a
     restored checkpoint.
3. **End to end: a short training on each GPU at once goes through all of
   it.**
   - [ ] Its code from a private repository at a recorded commit, its run
     through the queue with its record written, the workstation's heartbeat
     in healthchecks.io, a cut on purpose and a resume from its checkpoint,
     its results in the backup, and its notices on the phone.
4. **Version 1.0: any project can use the platform and cite it.**
   - [ ] A guide for a project that uses the platform: the guard it copies,
     how its runs go through the queues, what each run records, and what is
     backed up.
   - [ ] The decisions its operation depends on are closed, each in its
     record: the RTX 4070's role and the GPUs' power limits.
   - [ ] The tag `v1.0`, with a changelog and a citation file, archived by
     Zenodo with a DOI, so that a project cites a version and not a commit.
     Zenodo gets its decision record, as every service outside the house
     does.

### Alongside, without holding up the goal

- [ ] Sections 7 to 9 of the validation guide again with the thesis dataset
  once it is converted, with both GPUs training at once, before the RTX
  4070's role is decided; and the workstation's draw from the wall (section
  10), which waits for a meter.
- [ ] The thesis repositories take the instance-data guard when they are
  created (guard guide).

## After it operates

- [ ] **Monitoring with history and alerts.** Both hosts and both GPUs graphed
  over days: temperatures, power, clocks held back, fans, disk space. An alert
  reaches the phone through ntfy when a GPU or the CPU runs hot, a disk is
  filling up, or a host stops reporting. The tools, Prometheus and Grafana or
  something lighter, are for its guide to choose.
- [ ] **An experiment tracker, if a project needs one.** nnU-Net logs every
  epoch, and a project keeps its own record of runs. A tracker on the service
  host (MLflow or Aim) comes only when comparing runs needs more.
- **More services on the service host, as projects need them,** each with its
  guide. Each one listens on 127.0.0.1, is published only to the tailnet, and
  asks for its own login.

## Refused

- **Waking the workstation from the service host (Wake-on-LAN).** After a
  power cut the workstation stays off until someone switches it on in person,
  so that repeated drops of power do not start it each time; waking it from
  afar would skip that choice. It would also need the workstation's wired port
  connected.
- **File sync on the service host (Syncthing, or Zotero over WebDAV).** Files
  are already synced with OneDrive.
- **A password manager, or any store of secrets.** The service host's disk is
  not encrypted and it runs without Secure Boot
  ([ADR-008](adr/ADR-008-a-service-host-comes-back-on-its-own.md),
  [ADR-011](adr/ADR-011-the-service-host-runs-without-secure-boot.md)): a
  stolen host would give them away.
- **DNS or ad blocking for the house (Pi-hole and the like).** The whole
  house's internet would depend on the service host.
- **Notebooks, language models or other heavy work on the service host.** It
  has 4 cores, 16 GB and no GPU: that work belongs to the workstation.
- **A forge at home (Forgejo) for private code.** Private repositories live on
  GitHub with the public ones
  ([ADR-013](adr/ADR-013-github-not-a-forge-at-home-for-private-code.md)): a
  forge here would add a service, a CI runner and backups for what GitHub
  already gives.
