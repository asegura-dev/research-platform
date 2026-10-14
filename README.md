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
> one says whether it has been run end to end on real hardware.

## Hosts

| Role | What it does | Designed on |
|---|---|---|
| GPU workstation | Training and evaluation, also used at its own screen. Ubuntu Desktop by default on its own disk (trialled over USB4 first), Windows on another disk | Ryzen 9 7900X, 64 GB, RTX 5080 16 GB and RTX 4070 12 GB |
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
| [Install Ubuntu Server on a single-OS host](docs/guides/install-ubuntu-server.md) | Service host | Written; first run pending |
| [Install Ubuntu Desktop on the GPU workstation](docs/guides/install-ubuntu-gpu-workstation.md) | GPU workstation | Written; first run pending |

Planned: Tailscale, Docker, ntfy, liveness checks, Forgejo and its runner,
experiment tracking, operating long runs, and backups.

## Decisions

Every choice whose reason is worth keeping is a record in
[docs/adr](docs/adr/README.md), with what was refused and when to revisit it.
Decisions still open are listed there too.

## License

[MIT](LICENSE)
