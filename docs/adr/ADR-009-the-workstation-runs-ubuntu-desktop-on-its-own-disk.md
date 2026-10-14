# ADR-009 - The GPU workstation runs Ubuntu Desktop on its own disk, trialled over USB4 first

## Status

Accepted on 2026-10-13, when the workstation's install was redefined for use at
its own screen. It supersedes
[ADR-002](ADR-002-ubuntu-server-not-desktop-on-every-host.md) for the GPU
workstation; ADR-002 still holds for the service host.

## Context

The workstation is used at its own monitor and keyboard as well as for long
training runs, and its fans and lighting are part of the build. ADR-002 chose
Ubuntu Server for every host on two assumptions that do not hold for this
machine: that no host is used locally, and that the workstation could stay on
the GA kernel. As of October 2026:

- **Kernel.** The board's wired network chip, a Realtek RTL8126 (5 GbE), has a
  Linux driver since kernel 6.9. Ubuntu 24.04's GA kernel (6.8) does not
  include it; the HWE kernel 7.0, the default of Ubuntu Desktop 24.04.5.1, does.
  Kernel 7.0 has an open bug with NVIDIA's open driver and RTX 50 cards: they
  hang when resuming from suspend (Launchpad bug 2149963). It concerns
  suspend, not compute.
- **Windows.** Windows 11 lives on an internal NVMe disk, with BitLocker, and
  has to keep starting on its own. Starting it through shim and GRUB changes
  what BitLocker measures and brings up its recovery screen; starting it from
  the firmware's boot menu does not.
- **Where the Ubuntu disk goes.** Reaching the board's free M.2 slots means
  taking both GPUs out. Before doing that, a trial should show whether Ubuntu,
  the NVIDIA driver and the training stack work on this hardware. A USB4
  enclosure allows that trial without opening the PC.
- **Root filesystem over USB4.** When Linux loads its USB4 driver it tears down
  the tunnels the firmware built, and PCIe tunnels need authorization; if the
  enclosure switches from a USB disk to PCIe while it holds the root
  filesystem, Linux loses it (kernel source and documentation). Kernel
  parameters avoid the switch, once a test in the live session shows which ones
  this firmware needs.

## Decision

**Ubuntu Desktop 24.04.5.1 LTS on the GPU workstation, with its default HWE
kernel, because the machine is used at its own screen and the GA kernel cannot
drive its network chip.** Suspend stays disabled while the resume bug is open.

**Ubuntu lives on its own SSD, with its own EFI system partition and boot
loader, because Windows must never depend on it nor it on Windows.** The
Windows disk is never written to.

**Windows starts only from the firmware's boot menu, never from GRUB**, so that
BitLocker always measures the same boot chain.

**The SSD is trialled in a USB4 enclosure first, and moves to an internal M.2
slot only if the trial passes**, by the go/no-go criteria of the install guide.
The same installation moves; it is not reinstalled.

**Refused: Ubuntu Server on the workstation**, which has no local desktop.
**Refused: "Install Ubuntu alongside Windows"**, which shrinks the Windows
volume and shares its disk. **Refused: installing straight into an internal
slot**, because taking the PC apart costs more than a trial while the platform
is unproven on this hardware.

## Consequences

- The install guide is
  [install-ubuntu-gpu-workstation.md](../guides/install-ubuntu-gpu-workstation.md).
  It also covers the NVIDIA driver, which ADR-003 expected in a guide of its
  own.
- During the trial the kernel command line carries the USB4 parameters that the
  guide's test selects; they are removed when the SSD moves inside.
- The workstation has a graphical session on the RTX 5080, and the desktop
  takes part of that GPU's memory; the guide measures how much.
- [ADR-003](ADR-003-the-workstation-boots-native-ubuntu-not-wsl2.md) stands:
  native Ubuntu rather than WSL2, and Ubuntu first in the boot order when its
  disk is present.

## Trade-off

A desktop costs memory and updates that a headless system would not, and the
HWE kernel follows newer upstream code than the GA kernel. During the trial the
root filesystem depends on a cable: a disconnect stops the system and loses
whatever was not yet written. Part of what the trial measures belongs to USB4
alone (storage speed, boot behaviour), so the guide separates what carries over
to the internal slot from what does not.

## Revisit when

The trial ends (record whether the disk moves inside), Launchpad bug 2149963 is
fixed (suspend could return), or
[ADR-001](ADR-001-ubuntu-24-04-lts-on-every-host.md) is revisited.
