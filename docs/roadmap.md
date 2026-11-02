# Roadmap

What must hold before a project relies on the platform, what comes after, and
what was considered and refused. A ticked item has been done on the real
hardware. Whatever is adopted gets its guide, and its decision record when
there is a choice worth keeping.

## Ready to operate

The platform is ready for a project's real work, starting with its first long
training, when every item below holds. The work left goes in this order: the
instance-data guard, the service host's heartbeat, long runs, backups, ntfy,
and one short training through all of it. The validation's open sections and
the phone's access go alongside.

**Hosts**

- [x] The service host runs Ubuntu Server, comes back by itself after a power
  cut, and installs its security updates on its own
  ([server guide](guides/install-ubuntu-server.md);
  [ADR-008](adr/ADR-008-a-service-host-comes-back-on-its-own.md),
  [ADR-011](adr/ADR-011-the-service-host-runs-without-secure-boot.md)).
- [x] The workstation runs Ubuntu on its own SSD with both GPUs working, and
  Windows still starts from the firmware's menu
  ([workstation guide](guides/install-ubuntu-gpu-workstation.md), sections 1
  to 20).
- [ ] The workstation is validated: memory, SSD and GPUs pass their tests, two
  trainings hold for three hours, and its draw from the wall is known
  ([validation guide](guides/validate-gpu-workstation.md); section 10 waits
  for a meter). Sections 7 to 9 run again with the thesis dataset once it is
  converted, before the RTX 4070's role is decided.

**Access**

- [ ] Every computer in use, the phone included, reaches both hosts with its
  own SSH key, from inside and outside the house
  ([Tailscale guide](guides/install-tailscale.md);
  [ADR-012](adr/ADR-012-ssh-over-tailscale-with-a-key-per-computer.md);
  workstation guide, section 22).

**Repositories**

- [ ] Every repository lives on GitHub, private ones included
  ([ADR-006](adr/ADR-006-public-repositories-on-github-private-on-forgejo.md),
  [ADR-013](adr/ADR-013-github-not-a-forge-at-home-for-private-code.md)), and
  refuses instance data: a hook checks each commit before it is made, and a
  workflow checks each push
  ([guard guide](guides/set-up-the-instance-data-guard.md)).

**Services**, each listening on 127.0.0.1 and published only through Tailscale
Serve ([ADR-004](adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md))

- [x] Docker is installed, publishes every port on 127.0.0.1 by default, and
  brings its containers back after a reboot
  ([Docker guide](guides/install-docker.md)).
- [ ] ntfy delivers a notification to the phone, from a training or from any
  long command. Who may publish and read is decided before it goes live.

**Operations**

- [ ] The service host pings healthchecks.io every five minutes, and its
  silence arrives by email
  ([heartbeat guide](guides/watch-the-service-host-with-healthchecks.md);
  [ADR-007](adr/ADR-007-liveness-is-watched-from-outside.md)). The ping also
  fails when the host stops looking after itself: apt broken, automatic
  updates stopped, a reboot pending for days, or its disk nearly full.
- [ ] A long run can be started, watched, and resumed from its last checkpoint
  after a cut. It pings healthchecks.io as it goes, and records the
  environment it ran in (guide for operating long runs).
- [ ] Results, the private note and the service host's `/srv` have a copy away
  from home, and a restore has been tested (backups, an open decision).
- [ ] One short training goes through all of it: its code from a private
  repository at a recorded commit, its environment recorded, its heartbeat in
  healthchecks.io, a cut on purpose and a resume from its checkpoint, its
  results in the backup, and its start and end announced by ntfy.

## After it operates

- [ ] **Monitoring with history and alerts.** Both hosts and both GPUs graphed
  over days: temperatures, power, clocks held back, fans, disk space. An alert
  reaches the phone through ntfy when a GPU or the CPU runs hot, a disk is
  filling up, or a host stops reporting. The tools, Prometheus and Grafana or
  something lighter, are for its guide to choose.
- [ ] **An experiment tracker, if a project needs one.** nnU-Net logs every
  epoch, and a project keeps its own record of runs. A tracker on the service
  host (MLflow or Aim) comes only when comparing runs needs more.

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
