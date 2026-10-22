# ADR-010 - The workstation's Ubuntu SSD goes inside, in M2_1, without the USB4 trial

## Status

Accepted on 2026-10-21, after the first install over USB4 failed. It supersedes
the USB4 trial of
[ADR-009](ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md); the
rest of ADR-009 stands.

## Context

ADR-009 put the Ubuntu SSD in a USB4 enclosure first, so that Ubuntu, the NVIDIA
driver and the training stack could be tried before taking the PC apart. The
trial ran from 2026-10-19 to 2026-10-21, with a UGREEN 40 Gbps enclosure
(ASMedia ASM2464PD bridge) on a rear USB4 port, board firmware 4.10 and the
Ubuntu 24.04.5 live session (kernel 7.0). What it found:

- **Only a PCIe tunnel.** Over USB4 the enclosure never appeared as a USB disk.
  The SSD was reachable only through the PCIe tunnel the firmware builds, which
  Linux keeps when it starts with `thunderbolt.host_reset=0` (mode P of the
  guide's version at commit `8141750`). On this firmware the USB4 domain reported no IOMMU DMA protection
  (`iommu_dma_protection` 0), so bolt does not authorize a new device by
  itself.
- **Disconnects in both systems.** Windows logged the enclosure's disk as
  surprise removed (System log, source `disk`, event 157) several times in those
  three days. In Linux, in mode P, the enclosure dropped in the middle of the
  install: the installer failed, and the SSD no longer appeared in `lsblk`.
- **The slots.** M2_1 is wired to the CPU (PCIe 5.0 x4), and ASRock's
  specifications call it "the first priority for M.2 installation". M2_2 to
  M2_4 hang off the chipset (PCIe 4.0 x4), whose single link to the CPU they
  share with USB, SATA and the network. M2_1 sits next to the memory slots,
  above the first GPU, and is reached without taking the GPUs out. It held the
  Windows data disk.
- **The SSDs.** The Ubuntu SSD (Kingston FURY Renegade 2 TB) and the Windows
  data disk (Kingston KC3000 1 TB) are both PCIe 4.0 drives: each links at Gen4
  x4 in any of the four slots.

## Decision

**The Ubuntu SSD goes inside, in M2_1, because over USB4 it disconnected in
Windows and in the middle of the install,** and a root filesystem cannot depend
on a link that drops during runs that last days.

**The trial is dropped, not repeated with another enclosure, cable or kernel
parameter.** It existed to try the platform before opening the PC. With the PC
opened anyway, everything it was meant to measure, except USB4 itself, is
measured on the internal SSD.

**M2_1 for Ubuntu, a chipset slot for the Windows data disk,** because training
reads the Ubuntu SSD at every iteration, and in M2_1 those reads do not share
the chipset's link; the data disk sits idle while training runs.

**Refused: Ubuntu in a chipset slot, with the data disk left in M2_1.** It would
have saved moving a disk, and put the training data behind the chipset's shared
link.

## Consequences

- [install-ubuntu-gpu-workstation.md](../guides/install-ubuntu-gpu-workstation.md)
  was rewritten for the internal SSD from its first run: no USB4 test, no kernel
  parameters, no move. Its version with the trial stays in the repository's
  history, at commit `8141750`.
- [validate-gpu-workstation.md](../guides/validate-gpu-workstation.md) measures
  the CPU, the memory, the SSD and the GPUs on the internal SSD before the
  machine trains for real.
- The data disk moved from M2_1 to a chipset slot; Windows kept its drive letter
  and its automatic BitLocker unlock.
- The SSD can no longer be unplugged to leave Windows alone. Windows starts from
  the firmware's boot menu, as ADR-009 already required, and a Windows restart
  lands in Ubuntu unless *Windows Boot Manager* is chosen there.

## Trade-off

The PC was opened, and a second disk moved, without the answer the trial was
meant to give first. Whether another enclosure, cable or port would have held
was not tested: Windows' own removals show that the drops were not a Linux
problem, but not which part caused them.

## Revisit when

A disk has to run from outside the case again. A new trial would then start in
Windows, watching the System log for event 157 over several days, before
anything is installed on the disk.
