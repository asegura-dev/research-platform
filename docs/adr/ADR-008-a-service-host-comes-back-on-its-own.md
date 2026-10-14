# ADR-008 - A service host comes back on its own

## Status

Accepted on 2026-10-09, while writing the service host's install guide.

## Context

The mini PC runs unattended. After a power cut, a kernel update or a hang, it
has to return to service with nobody at the keyboard, and keep receiving
security updates without supervision.

Facts that shape this (as of October 2026):

- A disk-encryption passphrase is typed at boot, at the keyboard.
- When a boot is interrupted, GRUB shows its menu on the next boot. Ubuntu
  changed the default wait for that case from forever to 30 seconds, so that
  headless servers come back alone.
- `unattended-upgrades` installs security updates but does not reboot by
  default, and some fixes (a kernel, for instance) need a reboot.
- Microsoft's 2011 UEFI certificate expired in June 2026. Canonical warns that
  systems without the 2023 certificate stop receiving shim security fixes, and
  that from Q4 2026 updates to stable releases may require it, with package
  management failures where it is missing.
- Several reports show the guided LVM layout leaving part of a large disk
  unallocated.

## Decision

**No disk-encryption passphrase,** because a prompt at boot keeps the host down
after every power cut.

**The firmware powers on when power returns, and GRUB keeps its 30-second
default.**

**Security updates install automatically, with a reboot at a fixed hour of the
early morning when one is needed.** This applies to service hosts only: the GPU
workstation never reboots on its own, because a reboot would cut a training
run.

**Secure Boot stays on, with the 2023 Microsoft certificates applied** before
automatic reboots are enabled.

**The root volume takes the whole volume group.**

**The acceptance test is a real power cut:** the host must power on, boot
without a keyboard and answer SSH within minutes.

**Refused: an encrypted disk unlocked by passphrase.** An unattended unlock (for
example, TPM-based) was not evaluated.

## Consequences

- The [install guide](../guides/install-ubuntu-server.md) implements each point
  and ends with the power-cut test.
- Each automatic reboot briefly takes Forgejo, ntfy and the tracker down, so the
  grace time of the host's heartbeat must cover it.

## Trade-off

A stolen mini PC exposes what it stores: private repositories, CI logs and run
metrics. It holds no images or patient data
([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)), which
is what makes this acceptable, and why that rule matters.

## Revisit when

The host starts storing sensitive data, or an unattended unlock is evaluated.
