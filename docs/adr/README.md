# Decision records

One record per decision, numbered in the order the decisions were taken. The
number is the identity: guides and other records cite it.

Every record says what was refused as well as what was chosen, and when the
decision should be looked at again. Infrastructure facts (versions, prices,
known bugs) go stale faster than code, so each record dates its facts and names
the event that should reopen it. New records start from
[TEMPLATE.md](TEMPLATE.md).

### 001 - Ubuntu 24.04 LTS on every host, until 26.04 has matured

[`ADR-001-ubuntu-24-04-lts-on-every-host.md`](ADR-001-ubuntu-24-04-lts-on-every-host.md)

24.04.5 on both hosts. 26.04 is refused for now: its Rust core utilities and
`sudo-rs` are where its early regressions were, and that is where unattended
updates run.

### 002 - Ubuntu Server, not Desktop, on every host

[`ADR-002-ubuntu-server-not-desktop-on-every-host.md`](ADR-002-ubuntu-server-not-desktop-on-every-host.md)

One installer stick for both hosts. Server installs default to the GA kernel;
Desktop installs track the HWE kernel, the one with open questions on RTX 50
cards. Superseded for the GPU workstation by ADR-009; still holds for the
service host.

### 003 - The GPU workstation boots native Ubuntu, not WSL2

[`ADR-003-the-workstation-boots-native-ubuntu-not-wsl2.md`](ADR-003-the-workstation-boots-native-ubuntu-not-wsl2.md)

Dual boot on separate disks, Ubuntu by default. WSL2's limits on pinned memory,
GPU monitoring and idle shutdown outweigh keeping Windows usable during
training.

### 004 - Compute on the workstation, always-on services on a separate host

[`ADR-004-compute-and-always-on-services-on-separate-hosts.md`](ADR-004-compute-and-always-on-services-on-separate-hosts.md)

The mini PC hosts code, CI, notifications and tracking. Heavy data never leaves
the workstation, and services are reachable only through Tailscale.

### 005 - Forgejo, not GitLab, for private code

[`ADR-005-forgejo-not-gitlab-for-private-code.md`](ADR-005-forgejo-not-gitlab-for-private-code.md)

GitLab would take half of the mini PC's memory and every core; Forgejo covers
CI, boards and review within its means.

### 006 - Public repositories on GitHub, private ones on Forgejo

[`ADR-006-public-repositories-on-github-private-on-forgejo.md`](ADR-006-public-repositories-on-github-private-on-forgejo.md)

A repository lives where its readers are. Public repositories publish the
design, never the instance. Names of the first four repositories.

### 007 - Liveness is watched from outside, because the house can go dark

[`ADR-007-liveness-is-watched-from-outside.md`](ADR-007-liveness-is-watched-from-outside.md)

healthchecks.io, the one deliberate exception to owned hardware. Two levels of
heartbeat, and pings that carry no identifiers.

### 008 - A service host comes back on its own

[`ADR-008-a-service-host-comes-back-on-its-own.md`](ADR-008-a-service-host-comes-back-on-its-own.md)

No disk passphrase, power-on after a power cut, timed automatic reboots for
security fixes (service hosts only), and Secure Boot with the 2023
certificates. Its power-cut test passed; its Secure Boot point is superseded
for the current service host by ADR-011.

### 009 - The GPU workstation runs Ubuntu Desktop on its own disk, trialled over USB4 first

[`ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md`](ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md)

Desktop with the HWE kernel, because the machine is used at its own screen and
the GA kernel has no driver for its network chip. Its own SSD and EFI system
partition; Windows starts only from the firmware's boot menu. Its USB4 trial is
superseded by ADR-010.

### 010 - The workstation's Ubuntu SSD goes inside, in M2_1, without the USB4 trial

[`ADR-010-the-ubuntu-ssd-goes-inside-the-workstation.md`](ADR-010-the-ubuntu-ssd-goes-inside-the-workstation.md)

The USB4 enclosure disconnected in Windows and in the middle of the install.
M2_1 because it is on the CPU's lanes; the Windows data disk moved to a chipset
slot.

### 011 - The service host runs without Secure Boot, because its firmware offers only a test key

[`ADR-011-the-service-host-runs-without-secure-boot.md`](ADR-011-the-service-host-runs-without-secure-boot.md)

Its firmware holds no keys, and its factory keys stop at an AMI test platform
key and the 2011 certificates. Installing them, and replacing the test key, are
refused for now.

### 012 - SSH goes over Tailscale with each computer's own key, not with Tailscale SSH

[`ADR-012-ssh-over-tailscale-with-a-key-per-computer.md`](ADR-012-ssh-over-tailscale-with-a-key-per-computer.md)

A login needs the tailnet and a key. Tailscale SSH is refused: its check mode
asks for a browser sign-in every 12 hours and hangs VS Code, and its accept
mode leaves the Tailscale account as the only lock.

## Open decisions

Each one gets its record when the work reaches it. Operational choices that
belong to a single guide (a driver branch, the clock convention, how BitLocker
is handled during an install) are recorded in that guide's decisions table.

| Decision | Where it is decided |
|---|---|
| Role of the RTX 4070: second training GPU, or local inference (Ollama) | Validation guide, sections 7 and 9, repeated with the real dataset |
| GPU power limits applied at every start | Validation guide, sections 8 and 10 |
| Switching to Windows remotely | A later revision of the Tailscale guide |
| Experiment tracker: MLflow or Aim | Tracker guide |
| A copy of irreplaceable data away from home | Backups guide |
