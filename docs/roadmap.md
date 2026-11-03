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
with its guide.

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
  workstation guide, section 22). The phone comes with ntfy, below.
- [x] Docker is installed on the service host, publishes every port on
  127.0.0.1 by default, and brings its containers back after a reboot
  ([Docker guide](guides/install-docker.md)).
- [x] The service host pings healthchecks.io every five minutes, and its
  silence arrives by email
  ([heartbeat guide](guides/watch-the-service-host-with-healthchecks.md);
  [ADR-007](adr/ADR-007-liveness-is-watched-from-outside.md)). The ping also
  fails when the host stops looking after itself: apt broken, automatic
  updates stopped, a reboot pending for days, or its disk nearly full.
- [x] This repository refuses instance data: a hook checks each commit before
  it is made, and a workflow checks each push
  ([guard guide](guides/set-up-the-instance-data-guard.md)). Private
  repositories live on GitHub too
  ([ADR-006](adr/ADR-006-public-repositories-on-github-private-on-forgejo.md),
  [ADR-013](adr/ADR-013-github-not-a-forge-at-home-for-private-code.md)).

### What is left, in this order

1. **ntfy: a notification reaches the phone.**
   - [ ] The phone joins the tailnet (Tailscale guide, section 8).
   - [ ] ntfy runs on the service host, listens on 127.0.0.1 and is published
     only to the tailnet, with Tailscale Serve
     ([ADR-004](adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md)).
     It refuses whoever it does not know: one token publishes from the
     workstation, and another reads on the phone.
   - [ ] A command that ends on the workstation shows on the phone.
2. **Long runs: a training runs for days without anyone watching** (guide for
   operating long runs).
   - [ ] It keeps running when the session that started it closes.
   - [ ] It notifies when it starts, every few dozen epochs with its metric,
     when it ends and when it fails.
   - [ ] It pings healthchecks.io as it goes, so that its silence raises the
     alarm ([ADR-007](adr/ADR-007-liveness-is-watched-from-outside.md)).
   - [ ] After a power cut, it resumes from its last checkpoint.
   - [ ] It records the environment it ran in: the commits of its code and of
     this repository, the kernel, the driver, and the versions of CUDA,
     PyTorch and nnU-Net.

   `run-signals`, the small package that sends these signals from a training,
   comes here, unless something simpler is enough.
3. **Backups: results survive the loss of the house.**
   - [ ] Results, the private note and the service host's `/srv` have a copy
     away from home, and a restore has been tested (backups, an open
     decision).
4. **End to end: one short training goes through all of it.**
   - [ ] Its code from a private repository at a recorded commit, its
     environment recorded, its heartbeat in healthchecks.io, a cut on purpose
     and a resume from its checkpoint, its results in the backup, and its
     start and end announced by ntfy.

### Alongside, without holding up the goal

- [ ] The workstation's draw from the wall (validation guide, section 10, which
  waits for a meter), and sections 7 to 9 again with the thesis dataset once
  it is converted, before the RTX 4070's role is decided.
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

- **Waking the workstation from the service host (Wake-on-LAN).** It pays only
  if the workstation stays off between runs, which is not the plan, and it
  needs the workstation's wired port connected.
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
