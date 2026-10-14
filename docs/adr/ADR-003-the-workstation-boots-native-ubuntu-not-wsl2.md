# ADR-003 - The GPU workstation boots native Ubuntu, not WSL2

## Status

Accepted on 2026-10-09, after weighing both options against how the workstation
will actually be used.

On 2026-10-13
[ADR-009](ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md)
changed how the workstation runs Ubuntu: Desktop instead of Server, used at its
own screen, on its own disk trialled over USB4 first. This decision stands:
native Ubuntu rather than WSL2, Ubuntu first when its disk is present.

## Context

The workstation trains for days at a time and is driven from a laptop. It can
be dedicated to training for weeks, and the local inference server it also
hosts can pause during long runs.

WSL2 runs CUDA, but with limits that a training host feels (NVIDIA's CUDA on
WSL guide and Microsoft's WSL documentation, 2026):

- Pinned system memory is limited, and some deep-learning training can exceed
  it.
- `nvidia-smi` inside WSL does not report GPU utilization or the running
  processes.
- An idle distribution shuts down after 15 seconds by default, and there are
  reports of services stopped for inactivity even with the VM timeout
  disabled.
- Windows Update can restart the machine.
- Networking goes through the VM's NAT by default, one more layer for a host
  that is reached remotely.

Native Linux has none of these, gives training all 24 threads and 64 GB, and is
the primary platform of nnU-Net, the framework of the first project. Windows
itself was ruled out earlier: `torch.compile` depends on Triton, which has no
working toolchain on Windows.

## Decision

**Ubuntu Server on its own disk, as the default operating system, because the
workstation is a remote compute server and should behave like one.**

**Windows stays on its own disk, untouched, for occasional use.** Booting it
pauses whatever runs on Ubuntu.

**Refused: WSL2.** Its advantage was keeping Windows usable during training,
and nothing here needs that.

## Consequences

- The workstation gets its own install guide (dual boot, BitLocker, keeping the
  Windows disk out of reach) and a guide for the NVIDIA driver.
- Switching to Windows needs a reboot, and doing it remotely needs a method that
  BitLocker tolerates (an open decision).

## Trade-off

Installing a second operating system next to Windows is the riskiest step of the
platform: the boot manager, BitLocker's recovery screen and the Secure Boot
certificate update all meet there. WSL2 would have touched none of them. While
Ubuntu runs, nothing on Windows is available.

## Revisit when

The workstation has to serve Windows workloads while it trains.
