# Research Platform

Infrastructure for reproducible machine-learning research on hardware you own:
a GPU workstation, an always-on service host, and the shared services every
project consumes (remote access, notifications, liveness checks, code hosting
and experiment tracking).

This repository publishes the **design** of the platform: guides, decision
records and, later, scripts and configuration templates. It never contains an
**instance** of it: no hostnames, addresses, notification topics, ping URLs or
tokens. Each host keeps those outside git.

> **Status:** early. Guides are written from official documentation, and each
> one says whether it has been run end to end on real hardware. The
> [roadmap](docs/roadmap.md) lists what holds, what is left before real work,
> and what was considered and refused.

## Hosts

| Role | What it does | Designed on |
|---|---|---|
| GPU workstation | Training and evaluation, also used at its own screen. Ubuntu Desktop by default on its own internal SSD, Windows on its own disks | Ryzen 9 7900X, 64 GB, RTX 5080 16 GB and RTX 4070 12 GB |
| Service host | Always-on services: code hosting and CI, notifications, experiment tracking | Ryzen 3 4300U, 16 GB, 512 GB SSD |

Liveness is the one thing watched from outside, because it has to keep working
when the house loses power
([ADR-007](docs/adr/ADR-007-liveness-is-watched-from-outside.md)).

## Principles

- **Publish the design, never the instance.** Real names, addresses, topics,
  ping URLs and tokens never enter git.
- **Private by network.** Services listen on loopback and are reached only
  through Tailscale; nothing is published to the internet.
- **Outside only where it must be.** A third-party service is used only for a
  job that cannot be done from home, and its decision record says why.
- **Read-only before destructive.** Every step that erases, moves or rewrites is
  preceded by checks that change nothing.
- **Projects do not depend on the platform.** They reach it through
  configuration and must run without it, so anyone can reproduce their results
  on their own hardware.

## Guides

| Guide | Host | Status |
|---|---|---|
| [Install Ubuntu Server on a single-OS host](docs/guides/install-ubuntu-server.md) | Service host | First run in October 2026, steps 1 to 11; without Secure Boot (ADR-011) |
| [Install Ubuntu Desktop on the GPU workstation](docs/guides/install-ubuntu-gpu-workstation.md) | GPU workstation | First run on 2026-10-21, sections 1 to 20; section 22 on 2026-10-28, and section 23 by 2026-10-29 |
| [Validate the GPU workstation before it trains for real](docs/guides/validate-gpu-workstation.md) | GPU workstation | First run on 2026-10-22, sections 1 to 9 and 11, memory stress repeated over 40 GiB; section 10 pending |
| [Join the hosts and your computers with Tailscale](docs/guides/install-tailscale.md) | Both hosts and your computers | First run on 2026-10-28, sections 1 to 7; the phone (section 8) pending |
| [Download a public imaging dataset from IDC onto the workstation](docs/guides/download-a-dataset-from-idc.md) | GPU workstation | First run on 2026-10-29: downloaded and verified |
| [Install Docker on the service host](docs/guides/install-docker.md) | Service host | Written on 2026-10-30; not run yet |

Planned: ntfy, liveness checks, Forgejo and its runner, experiment tracking,
operating long runs, backups, and monitoring.

## Decisions

Every choice whose reason is worth keeping is a record in
[docs/adr](docs/adr/README.md), with what was refused and when to revisit it.
Decisions still open are listed there too.

## License

[MIT](LICENSE)
