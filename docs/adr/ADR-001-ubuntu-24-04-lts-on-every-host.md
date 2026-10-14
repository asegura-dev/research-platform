# ADR-001 - Ubuntu 24.04 LTS on every host, until 26.04 has matured

## Status

Accepted on 2026-10-09, while choosing the installer image for both hosts.

## Context

Both hosts need the same Ubuntu release, so that one set of guides and scripts
serves the whole platform. Two LTS releases were available (as of October
2026):

- **24.04 LTS.** Its final planned point release, 24.04.5, came out on
  2026-09-10. Standard support runs until 2029.
- **26.04 LTS.** 26.04.1 came out on 2026-08-27. It replaces most core
  utilities with a Rust reimplementation and `sudo` with `sudo-rs`; only `cp`,
  `mv` and `rm` remain GNU. After 26.04.1, Canonical held back the upgrade
  prompt for 24.04 users while it fixed regressions in those utilities. In
  25.10, a bug in the Rust `date` stopped unattended security updates from
  running. It was fixed, but it is the kind of silent failure that a host
  updating itself cannot afford.

The third-party software the platform needs supports both: Docker Engine and
Tailscale publish packages for 26.04 as well. Python versions are pinned per
project with uv, so the system Python does not matter.

## Decision

**24.04 LTS on every host, because the work running on this platform needs a
mature userland more than the newer release's longer support.** The support
window of 24.04 already covers the first project, a master's thesis.

**Hosts are installed from the latest point release, 24.04.5.**

**Refused: 26.04 now.** Its risks fall exactly where this platform cannot
absorb them: in the updates that run unattended on the service host, and in the
NVIDIA driver on the workstation.

## Consequences

- Guides are written and checked against 24.04.
- An in-place upgrade to 26.04 is a supported path, so this decision can be
  undone without reinstalling.

## Trade-off

The platform starts on the older release and will have to move within its
support window, which is work a fresh 26.04 install would not need. Choosing
24.04 does not by itself avoid the kernel risk on the workstation: the HWE
kernel of 24.04.5 is 7.0, the same kernel as 26.04. That choice is made
separately ([ADR-002](ADR-002-ubuntu-server-not-desktop-on-every-host.md)).

## Revisit when

26.04.2 is released, or the thesis's critical experiments are finished,
whichever comes first.
