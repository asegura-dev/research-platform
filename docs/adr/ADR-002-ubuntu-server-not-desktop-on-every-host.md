# ADR-002 - Ubuntu Server, not Desktop, on every host

## Status

Accepted on 2026-10-09. The service host was decided first; the GPU workstation
followed once it was clear that it would also be operated remotely.

Superseded for the GPU workstation by
[ADR-009](ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) on
2026-10-13: the workstation is used at its own screen, and the GA kernel has no
driver for its network chip. This record still holds for the service host.

## Context

Neither host is used at its own screen. The service host runs services. The
workstation is driven from a laptop over SSH (VS Code Remote-SSH), and its
monitor, when one is attached, hangs from the CPU's integrated GPU.

The two images differ in ways that matter here (Ubuntu documentation, October
2026):

- **Kernel.** Server installations default to the GA kernel (6.8 for 24.04) and
  offer the hardware enablement (HWE) kernel as optional. Desktop installations
  track the HWE stack, which in 24.04.5 is kernel 7.0. There are early forum
  reports of hangs with RTX 50 cards on kernel 7.0 that disappear on 6.17; they
  are reports, not an established fact.
- **Remote access.** The Server installer offers OpenSSH and imports the
  user's public keys from GitHub, so the first login is key-only.
- **NVIDIA.** Ubuntu publishes precompiled, Canonical-signed NVIDIA modules for
  the GA kernel, including the 580 branch with the open kernel modules that the
  RTX 50 series requires.

## Decision

**Ubuntu Server on every host, because no host needs a desktop and Server
starts from the conservative kernel.** On the workstation, moving to the HWE
kernel is a separate decision, taken with measurements.

**One installer stick serves both hosts.**

**Refused: Ubuntu Desktop.** A desktop nobody looks at costs memory and
updates, and its default kernel is the one with open questions on this GPU.

## Consequences

- Both hosts are installed and administered the same way, over SSH.
- The workstation's NVIDIA cards drive no display.

## Trade-off

Neither host has a graphical session. Anything that needs one locally happens
in Windows on the workstation, or on the laptop. If the GA kernel turns out to
lack support for some component of the workstation (a newer network chip, for
example), the HWE kernel becomes necessary and the conservative-kernel argument
disappears.

## Revisit when

A host needs a local desktop, or the smoke test moves the workstation to the
HWE kernel.
