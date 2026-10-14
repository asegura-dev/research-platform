# ADR-004 - Compute on the workstation, always-on services on a separate host

## Status

Accepted on 2026-10-09, when the services every project needs (code hosting, CI,
notifications, experiment tracking) had to be placed somewhere.

## Context

Two machines are available:

| Machine | CPU | Memory | GPU | Storage |
|---|---|---|---|---|
| Workstation | Ryzen 9 7900X, 12 cores / 24 threads | 64 GB | RTX 5080 16 GB, RTX 4070 12 GB | Windows disk and a dedicated Ubuntu disk |
| Mini PC | Ryzen 3 4300U, 4 cores / 4 threads, 15 W | 16 GB | Integrated | 512 GB SSD |

The workstation reboots, boots Windows from time to time, and while it trains
its CPU is busy: for each training run, nnU-Net starts 12 data-augmentation
processes for training, 6 for validation and a main one.

## Decision

**The workstation computes; the mini PC hosts everything that must stay up:**
code hosting and its CI runner, ntfy, the experiment tracker and, later, the
dashboards. Services keep working while the workstation reboots or runs
Windows, and CI never competes with data augmentation for CPU.

**Heavy data never leaves the workstation.** Images, preprocessed data and
checkpoints stay there; the tracker on the mini PC keeps metrics, parameters and
small artifacts such as plots.

**Every service listens on 127.0.0.1 and is exposed only through Tailscale
Serve.** Publishing a port on every interface is refused: Docker routes traffic
to published ports before `ufw` sees it, so a firewall rule would not protect
it.

**Refused: one machine for everything.** It would put services and training on
the same CPU and take the services down with every reboot.

## Consequences

- Each host has its own install guide.
- Tests that need a GPU run by hand, or on a workstation runner that only takes
  jobs between trainings; every other test runs on the mini PC.

## Trade-off

Two machines to update and back up instead of one. They also share the same
power and internet connection, so neither can report the other's death when the
house goes dark. That is why liveness is watched from outside
([ADR-007](ADR-007-liveness-is-watched-from-outside.md)), and why backups need a
copy away from home.

## Revisit when

A service outgrows the mini PC's 4 cores and 16 GB, or a third machine joins.
