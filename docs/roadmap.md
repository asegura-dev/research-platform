# Roadmap

What must hold before a project relies on the platform, what comes after, and
what was considered and refused. A ticked item has been done on the real
hardware. Whatever is adopted gets its guide, and its decision record when
there is a choice worth keeping.

## Ready to operate

The platform is ready for a project's real work when every item below holds.

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
  for a meter).

**Access**

- [ ] Every computer in use, the phone included, reaches both hosts with its
  own SSH key, from inside and outside the house
  ([Tailscale guide](guides/install-tailscale.md);
  [ADR-012](adr/ADR-012-ssh-over-tailscale-with-a-key-per-computer.md);
  workstation guide, section 22).

**Services**, each listening on 127.0.0.1 and published only through Tailscale
Serve ([ADR-004](adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md))

- [ ] Docker runs the services, with every port published on 127.0.0.1 only,
  and they come back after a reboot
  ([Docker guide](guides/install-docker.md)).
- [ ] ntfy delivers a notification to the phone, from a training or from any
  long command.
- [ ] Each host pings healthchecks.io, and its silence arrives by email
  ([ADR-007](adr/ADR-007-liveness-is-watched-from-outside.md)).
- [ ] Forgejo hosts the private repositories, and its runner builds them,
  the thesis document included
  ([ADR-005](adr/ADR-005-forgejo-not-gitlab-for-private-code.md),
  [ADR-006](adr/ADR-006-public-repositories-on-github-private-on-forgejo.md)).
- [ ] The experiment tracker records a run's parameters and metrics (MLflow or
  Aim, an open decision).

**Operations**

- [ ] Irreplaceable data has a copy away from home (backups, an open
  decision).
- [ ] A long run can be started, watched, and resumed from its last checkpoint
  after a cut (guide for operating long runs).
- [ ] One short training goes through all of it: its code from Forgejo, its
  start and end announced by ntfy, its heartbeat in healthchecks.io, and its
  metrics in the tracker.

## After it operates

- [ ] **Monitoring with history and alerts.** Both hosts and both GPUs graphed
  over days: temperatures, power, clocks held back, fans, disk space. An alert
  reaches the phone through ntfy when a GPU or the CPU runs hot, a disk is
  filling up, or a host stops reporting. The tools, Prometheus and Grafana or
  something lighter, are for its guide to choose.

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
