# Install Ubuntu Desktop on the GPU workstation

> **Scope:** the dual-boot GPU workstation only. Windows keeps its internal
> NVMe disk and is never written to. Ubuntu Desktop goes on a second NVMe SSD
> with its own EFI system partition and boot loader. During a trial the SSD
> sits in a USB4 enclosure; if the trial passes, the same installation moves to
> an internal M.2 slot (section 31). For a single-OS service host, use
> [install-ubuntu-server.md](install-ubuntu-server.md).

> **Status:** written from official documentation and source code on
> 2026-10-13; not yet run end to end. After its first complete run, this line
> records the date, the versions it was verified with, and the USB4 mode that
> section 8 found.

The trial answers one question: does Ubuntu, with this hardware, the NVIDIA
driver and the training stack, work well enough to justify taking the PC apart
to put the SSD inside? Everything the trial measures carries over to the
internal slot except what belongs to USB4: storage speed, boot behaviour and
the risk of a disconnect. Section 27 says how to read the result.

How to follow it:

- Every section ends with a **Check:**. Do not start the next section until it
  passes.
- **STOP** marks a point where you confirm something before going on.
- Read-only commands come first. A command that changes something comes after
  them, and only once their output matches what the section expects.
- Outputs quoted here are examples; names, serial numbers and versions on your
  machine will differ.

## Hardware

| Part | Model |
|---|---|
| Board | ASRock X870E Taichi Lite |
| CPU | AMD Ryzen 9 7900X, 12 cores, 24 threads |
| Memory | 64 GB DDR5 |
| GPUs | NVIDIA RTX 5080 16 GB (Blackwell, PCIe 5.0) and RTX 4070 12 GB (Ada, PCIe 4.0) |
| Windows disk | Internal NVMe, Windows 11 with BitLocker or device encryption |
| Ubuntu disk | NVMe SSD in a UGREEN USB4 40 Gbps enclosure, on a rear USB4 port |

## Placeholders

- `<iso>`: `ubuntu-24.04.5.1-desktop-amd64.iso`.
- `<windows-disk>` and `<windows-esp>`: the Windows NVMe and its EFI system
  partition, as Linux names them in the current boot (for example
  `/dev/nvme0n1` and `/dev/nvme0n1p1`).
- `<ubuntu-disk>`: the SSD in the enclosure (for example `/dev/sda` when it runs
  as a USB disk, `/dev/nvme1n1` when it runs over PCIe).
- `<uuid-5080>` and `<uuid-4070>`: the GPUs' UUIDs as `nvidia-smi -L` prints
  them (`GPU-…`).
- `<user>`, `<github-user>`, `<lan-ip>`.

Linux device names are not identities: they can change from one boot to the
next. Every section that needs them identifies the disks again by serial number
and size.

Never commit serial numbers, GPU UUIDs, hostnames, addresses or BitLocker
recovery keys to this repository.

## Decisions this guide depends on

| Decision | Value here | Why | Record |
|---|---|---|---|
| Release | Ubuntu Desktop 24.04.5.1 LTS, the Desktop rebuild of 24.04.5 | The same release on every host | [ADR-001](../adr/ADR-001-ubuntu-24-04-lts-on-every-host.md) |
| Image and kernel | Desktop, with its default HWE kernel (7.0) | The machine is used at its own screen; the GA kernel (6.8) has no driver for the board's RTL8126 network chip | [ADR-009](../adr/ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) |
| Ubuntu disk | Its own SSD with its own EFI system partition, ext4, no LVM, no encryption; USB4 enclosure during the trial, internal slot if it passes | Windows never depends on it, and it never depends on Windows | [ADR-009](../adr/ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) |
| Starting Windows | Only from the firmware boot menu, never from GRUB | Starting Windows through shim and GRUB changes what BitLocker measures | [ADR-009](../adr/ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) |
| Default boot | Ubuntu first when its SSD is connected | Ubuntu is the workstation's default system | [ADR-003](../adr/ADR-003-the-workstation-boots-native-ubuntu-not-wsl2.md) |
| USB4 mode | P or U, chosen by the test of section 8 | Keeps the trial from losing its root filesystem | Section 8 |
| BitLocker | Suspended from section 3 until section 20 | The firmware and the boot chain change in between | Sections 3 and 20 |
| Monitor | On the RTX 5080, as before | Windows is used as before; section 19 measures what the desktop takes | Section 19 |
| Restore on AC/Power Loss | Power Off | Nothing resumes a training run after a power cut | Section 6 |
| Suspend | Disabled | Open bug with kernel 7.0 and RTX 50 cards on resume; the USB4 tunnels | Section 15 |
| Updates | Security updates install by themselves, never an automatic reboot; kernel and NVIDIA packages only by hand, between runs | A driver update during a series breaks new CUDA processes until a reboot | Sections 14 and 30 |
| NVIDIA driver | 580, open kernel modules, precompiled and signed by Canonical | NVIDIA's long-term branch, until June 2028; RTX 50 cards need the open modules; no key to enroll | Section 18 |
| Smoke-test stack | uv 0.13.0, Python 3.12, PyTorch 2.14.1 with CUDA 13.0 wheels, nnU-Net 2.8.1 | CUDA 13.0 is the 580 driver's own version; each project pins its own stack | Sections 23 and 25 |
| Clock | Ubuntu keeps the hardware clock in local time | Mexico City has had no daylight saving time since 2022, which is where this mode causes trouble | Section 12 |
| Fast Startup | Off | Shutting Windows down must really shut it down | Section 3 |
| Secure Boot variables (db, KEK, dbx) and the 2023 certificates | Changed only by Windows Update; Ubuntu only reads them (secureboot-db masked, fwupd's UEFI items declined) | Windows handles BitLocker during those updates | Section 16 |

## Part A. Windows: inventory and preparation

### 1. What you need

- A USB stick of 8 GB or more. Writing the image erases it.
- The Ubuntu SSD in the UGREEN USB4 enclosure, with the USB-C to USB-C cable
  that came with the enclosure. Everything on the SSD will be erased.
- The BitLocker recovery key of the Windows disk, readable from another device:
  on paper, or through https://aka.ms/myrecoverykey if it is saved in a
  Microsoft account. Section 3 checks that it is the right one.
- A wired network connection.
- The monitor and keyboard you normally use.
- An afternoon for sections 1 to 21, and a night for the training test of
  section 26.

**Check:** you can read the recovery key on a device other than this PC.

### 2. Inventory from Windows (read-only)

Connect the enclosure, with the SSD inside, directly to one of the board's two
rear USB4 ports. Use that same port for the rest of this guide. If Windows
offers to initialize or format the SSD, cancel: nothing on the Windows side
touches it.

Open PowerShell as administrator. Nothing in this section changes the system.
Keep the output in a private note outside this repository: it holds serial
numbers and, in one command, the recovery key.

Disks and partitions:

```powershell
# Every physical disk: identity, bus, sector size and size
Get-PhysicalDisk | Format-Table DeviceId, FriendlyName, SerialNumber, BusType, LogicalSectorSize, PhysicalSectorSize, Size -AutoSize

# Which disk holds Windows (IsBoot) and its EFI system partition (IsSystem)
Get-Disk | Format-Table Number, FriendlyName, SerialNumber, BusType, PartitionStyle, IsBoot, IsSystem, Size -AutoSize

# Partitions of every disk: System (EFI), Reserved, Basic and Recovery
Get-Partition | Format-Table DiskNumber, PartitionNumber, DriveLetter, Type, Size -AutoSize
```

Over USB4 the enclosure can appear with BusType `NVMe` (a PCIe tunnel) or `USB`.
BusType alone therefore does not tell it apart from the Windows disk: use model,
serial number and size. For an NVMe disk, Windows often shows as serial number
the disk's EUI-64 identifier, in groups like `0025_3881_…`, instead of the
controller's serial number; section 7 shows where Linux lists both.

BitLocker:

```powershell
# Encryption and protection state of the Windows volume
manage-bde -status C:

# Key protectors and the TPM's "PCR Validation Profile".
# This also PRINTS THE RECOVERY PASSWORD: never paste its output anywhere public.
manage-bde -protectors -get C:
```

`PCR Validation Profile: 7, 11` means BitLocker relies on the Secure Boot
measurement; `0, 2, 4, 11` means it measures the firmware, the option ROMs of
the cards and the boot code directly. With two GPUs whose firmware loads UEFI
drivers, `0, 2, 4, 11` is likely. Section 3 lists the events that matter either
way.

Also run `msinfo32` as administrator and read, under *System Summary*: *BIOS
Mode* (expected: UEFI), *Secure Boot State* and *PCR7 Configuration*.

Secure Boot:

```powershell
Confirm-SecureBootUEFI        # True = Secure Boot is on

# Certificates the firmware trusts to boot (db) and to update db (KEK)
$db  = [System.Text.Encoding]::ASCII.GetString((Get-SecureBootUEFI db).bytes)
$kek = [System.Text.Encoding]::ASCII.GetString((Get-SecureBootUEFI KEK).bytes)
$db  -match 'Microsoft Corporation UEFI CA 2011'    # signs Ubuntu 24.04's boot loader: must be True
$db  -match 'Microsoft UEFI CA 2023'
$db  -match 'Microsoft Option ROM UEFI CA 2023'
$db  -match 'Windows UEFI CA 2023'
$kek -match 'Microsoft Corporation KEK 2K CA 2023'
```

The rest:

```powershell
# The firmware's boot entries and their order
bcdedit /enum firmware

# Fast Startup: 1 = on, 0 = off
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled

# Firmware version
Get-CimInstance Win32_BIOS | Format-List SMBIOSBIOSVersion, ReleaseDate
```

Fill in this table in your private note:

| Item | Value |
|---|---|
| Windows disk: model, serial number, size, disk number | |
| Its EFI system partition: size | |
| Ubuntu SSD: model, serial number, size, BusType, LogicalSectorSize | |
| BitLocker: protection status, PCR Validation Profile, recovery key ID | |
| Secure Boot: on or off; `Microsoft Corporation UEFI CA 2011` in db; which 2023 certificates | |
| Fast Startup | |
| Firmware version | |

**Check:** the table is complete. **STOP** if *BIOS Mode* is not UEFI, or if
`Microsoft Corporation UEFI CA 2011` is not in db: Ubuntu 24.04's installer and
boot loader are signed through that certificate and do not start with Secure
Boot on. If Secure Boot is off and `Get-SecureBootUEFI` finds no db at all, the
firmware has no keys yet: section 6 installs them, then repeat this check.

### 3. Prepare Windows

#### Confirm the recovery key

In the output of `manage-bde -protectors -get C:`, the *Numerical Password*
protector has an ID like `{1A2B3C4D-…}`. The recovery screen asks for the key
whose ID starts with the same eight characters. Find that ID in your saved key:
paper, file, or https://aka.ms/myrecoverykey. On Windows 11 with device
encryption, the key is saved in the Microsoft account used at the first
sign-in. If you have no copy, make one before going on (Start → *Manage
BitLocker* → *Back up your recovery key*), never on the Windows disk itself.

#### Turn off Fast Startup

With Fast Startup on, *Shut down* hibernates the Windows kernel session instead
of ending it. This guide starts other systems and plugs and unplugs a disk
between Windows sessions, so Windows must really shut down.

Control Panel → *Hardware and Sound* → *Power Options* → *Choose what the power
buttons do* → *Change settings that are currently unavailable* → clear *Turn on
fast startup (recommended)* → *Save changes*.

```powershell
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled   # now 0
```

#### Suspend BitLocker

Skip this part if `manage-bde -status C:` showed no encryption.

Microsoft lists, among the events that put a BitLocker volume into recovery:
firmware upgrades, changes to the boot manager, changes to the measurements
(PCRs) BitLocker checks, and turning off or clearing the TPM. With the profile
`0, 2, 4, 11`, changing a GPU or its firmware counts too, because PCR 2
measures the cards' option ROMs. The firmware settings of section 6, the new
boot entries of section 10 and the first starts of both systems all fall on
that list. Microsoft's answer for planned changes is to suspend protection
first:

```powershell
manage-bde -protectors -disable C: -RebootCount 0   # 0 = suspended until you turn it back on
manage-bde -status C:                               # Protection Status: Protection Off
```

The volume stays encrypted, but while protection is suspended its key is kept
on the disk in the clear: anyone holding the disk could read it. Section 20
turns protection back on. Do not leave it suspended.

**Check:** `HiberbootEnabled` is 0, `manage-bde -status C:` shows *Protection
Off*, and you hold the recovery key whose ID matches.

### 4. Download and verify the image

From https://releases.ubuntu.com/noble/ download into one folder:

- `ubuntu-24.04.5.1-desktop-amd64.iso`
- `SHA256SUMS`
- `SHA256SUMS.gpg`

The first Desktop image of 24.04.5 was withdrawn because its installer crashed
when *Extended selection* was chosen (Launchpad bug 2167127); it was republished
as 24.04.5.1 on 2026-09-15. It installs the HWE kernel 7.0.

Integrity, in PowerShell from that folder:

```powershell
$expected = ((Select-String -Path .\SHA256SUMS -Pattern 'ubuntu-24.04.5.1-desktop-amd64.iso').Line -split ' ')[0]
$actual   = (Get-FileHash -Algorithm SHA256 .\ubuntu-24.04.5.1-desktop-amd64.iso).Hash
$expected; $actual
$actual -eq $expected     # True (PowerShell compares strings without regard to case)
```

Authenticity needs `gpg`: Gpg4win on Windows, or any Linux machine, such as the
service host:

```bash
gpg --keyid-format long --verify SHA256SUMS.gpg SHA256SUMS
# If it says "No public key", fetch Ubuntu's image signing keys and retry:
gpg --keyid-format long --keyserver hkp://keyserver.ubuntu.com \
    --recv-keys 0x46181433FBB75451 0xD94AA3F0EFE21092
gpg --keyid-format long --list-keys --with-fingerprint \
    0x46181433FBB75451 0xD94AA3F0EFE21092
```

The fingerprints must be exactly:

```text
C598 6B4F 1257 FFA8 6632  CBA7 4618 1433 FBB7 5451
8439 38DF 228D 22F7 B374  2BC0 D94A A3F0 EFE2 1092
```

**Check:** `$actual -eq $expected` prints `True`, and gpg reports `Good
signature from "Ubuntu CD Image Automatic Signing Key (2012)
<cdimage@ubuntu.com>"` with one of those fingerprints. A warning that the key
"is not certified with a trusted signature" is expected; a fingerprint mismatch
or `BAD signature` is not: delete the files and download them again.

### 5. Write the USB stick with Rufus

Get Rufus only from https://rufus.ie or https://github.com/pbatard/rufus/releases,
and prefer the portable build (`rufus-<version>p.exe`). Check its signature
before running it:

```powershell
Get-AuthenticodeSignature .\rufus-<version>p.exe | Format-List Status, SignerCertificate
```

`Status` must be `Valid` and the signer Akeo Consulting (older releases: "Pete
Batard - Open Source Developer"). Any other signer, or none: delete the file.

Unplug the USB4 enclosure and every other USB storage device, so the stick is
the only drive Rufus can offer. Then:

1. **Device:** the stick; its size must match.
2. **Boot selection:** *Disk or ISO image* → **SELECT** → the verified ISO.
3. **Partition scheme:** GPT. **Target system:** UEFI (non CSM).
4. **START.** Accept the download of additional files if asked. When Rufus
   reports an ISOHybrid image, keep **Write in ISO Image mode**.
5. Confirm the warning only if the device is the stick.

**Check:** Rufus reports *READY*. Reconnect the enclosure to the same rear USB4
port as before.

## Part B. Firmware

### 6. Firmware settings

Press F2 or Del at power-on to enter the firmware setup. The one-time boot menu
is on F11 on ASRock boards; the start-up screen shows the key. The menu names
below come from ASRock's *AMD 800 Series Motherboard Software/BIOS Setup Guide*
(v1.1, February 2026), written for this board family. If your firmware version
names something differently, use its equivalent and note it here.

Read-only first: write down or photograph the current value of every setting in
the table before changing anything.

| Setting (menu) | Value | Why |
|---|---|---|
| Boot > CSM | Disabled | UEFI only; CSM also turns Secure Boot off |
| Security > Secure Boot > Secure Boot | Enabled | Ubuntu starts through its signed shim |
| Security > Secure Boot > Secure Boot Mode | Unchanged if Secure Boot is already on; Standard only when no keys are installed | ASRock's guide: in Standard mode the firmware loads its own factory keys, which can drop certificates Windows Update added |
| Advanced > PCI Configuration > Above 4G Decoding | Enabled | Large memory windows for two GPUs; required by Re-Size BAR |
| Advanced > PCI Configuration > Re-Size BAR Support | Enabled | Full GPU memory window |
| Boot > Fast Boot | Disabled, permanently | ASRock: with Fast Boot "you won't be able to boot from an USB storage device", and during the trial the Ubuntu SSD is one |
| Advanced > ACPI Configuration > Restore on AC/Power Loss | Power Off | Nothing resumes a training run after a power cut. ASRock's guide documents only Power On and Power Off |
| Advanced > Onboard Devices Configuration > Display Priority | External Graphic, unless the current value already shows the firmware screens on your monitor | The monitor is on the RTX 5080: firmware screens and the boot menu must appear there |
| Advanced > CPU Configuration > AMD fTPM Switch | Unchanged (AMD CPU fTPM) | BitLocker's key is sealed in the TPM |
| H/W Monitor | Curves for the CPU and case fans | The cooling that protects the hardware lives in the firmware (section 28) |

Secure Boot keys:

- If msinfo32 showed *Secure Boot State: On*, only read *Security > Secure
  Boot*. Do not change *Secure Boot Mode*, and do not use *Install Default
  Secure Boot Keys* or *Clear Secure Boot Keys*: factory keys can lack
  certificates that Windows Update has added since, and once Windows' own boot
  manager is signed with a 2023 certificate, Windows would no longer start.
- If Secure Boot was off but keys are installed, set *Secure Boot* to Enabled.
- If no keys are installed (Windows found no db in section 2), use *Install
  Default Secure Boot Keys*, enable Secure Boot, start Windows and repeat the
  Secure Boot commands of section 2.

If the firmware ever offers to reset or clear the fTPM, for example after a CPU
or firmware change, decline: clearing the TPM is one of Microsoft's recovery
triggers, and a cleared TPM no longer holds BitLocker's key.

If the stick is refused with a message such as *Secure Boot Violation* or
*Invalid signature*, the firmware's db lacks `Microsoft Corporation UEFI CA
2011`; section 2 should have caught it. Canonical states that existing Ubuntu
installation media require that certificate, and the installed boot loader is
signed through it too. The fix, with BitLocker suspended: if the factory keys
include it, *Install Default Secure Boot Keys* restores it; check again from
Windows afterwards, and let Windows Update add the 2023 certificates back
(section 16). Running with Secure Boot off is a new decision with its own
record, not a quiet change.

**Check:** with the stick inserted, the boot menu (F11) lists it as a UEFI
device, and Windows still starts from *Windows Boot Manager*.

## Part C. Live session: look before writing

Nothing in this part writes to any disk: the live system runs from the stick.

GRUB, the boot menu of the stick, reads the keyboard as US English whatever
your layout. On a Latin American keyboard, the key to the right of `0` types
`-` (with Shift, `_`) and the next key types `=`.

### 7. Identify the three devices

1. The enclosure is on its rear USB4 port, connected directly with its own
   cable. The stick goes in another port.
2. Power on, press F11 and choose the stick's UEFI entry.
3. In the stick's menu, choose the default entry (*Try or Install Ubuntu* on
   24.04 media). If the screen stays black, restart and choose the entry with
   *safe graphics* in its name.
4. The installer opens. Choose your language, accessibility options and
   keyboard; on *Internet connection* choose *Use wired connection*; on *Try or
   install Ubuntu* choose *Try Ubuntu 24.04.5 LTS* (the release number may read
   slightly differently). The live desktop appears.
5. Open a terminal (Ctrl+Alt+T).

```bash
# Every block device with its identity and transport (read-only)
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,FSTYPE,PARTTYPENAME,MOUNTPOINTS

# Stable names built from model and serial number
ls -l /dev/disk/by-id/ | grep -v -- '-part'
```

What to expect:

- **Windows disk:** `TRAN` nvme; model and serial number as in section 2;
  partitions *EFI System*, *Microsoft reserved*, *Microsoft basic data* (FSTYPE
  `BitLocker` if encrypted) and *Windows recovery environment*.
- **Ubuntu SSD:** the size of section 2; `TRAN` nvme if the enclosure runs a
  PCIe tunnel, usb if it runs as a USB disk. As a USB disk, the model or serial
  number shown can be the enclosure bridge's instead of the SSD's.
- **The stick:** `TRAN` usb, one partition mounted at `/cdrom`.

`lsblk` shows the controller's serial number. If Windows showed an EUI-64 instead
(section 2), look for it in `/dev/disk/by-id`: each NVMe disk has a
`nvme-<model>_<serial>` link and a `nvme-eui.<identifier>` link, the identifier
being Windows' value in lowercase, without its underscores and dots.

Write down which name is which, for this boot only.

**STOP.** Go on only when the Windows disk is matched to section 2 by its serial
number, and the other two devices by size, model and transport.

**Check:** you know which device is the Windows disk, which is the Ubuntu SSD
and which is the stick.

### 8. Test how the USB4 enclosure behaves

When Linux loads its USB4 driver (`thunderbolt`), by default it tears down the
tunnels the firmware set up, and creates PCIe tunnels again only for devices
that get authorized. On Ubuntu Desktop the bolt service can authorize the
enclosure later, by itself. If the SSD runs as a USB disk and then switches to
PCIe while it holds the root filesystem, the USB disk disappears and Linux loses
its root filesystem. These mechanisms are in the kernel's source and
documentation (October 2026); whether this firmware and this enclosure trigger
them is unknown until tested. Here the live system runs from the stick, so
nothing is at stake.

Two boots, both read-only.

#### Boot 1: defaults

In the live session of section 7, wait two minutes after the desktop appears,
then:

```bash
cat /sys/module/thunderbolt/parameters/host_reset                    # Y: firmware tunnels are reset when the driver loads
grep -H . /sys/bus/thunderbolt/devices/domain*/security              # user: PCIe tunnels need authorization
grep -H . /sys/bus/thunderbolt/devices/domain*/iommu_dma_protection  # 1: bolt authorizes new devices by itself
boltctl list                                                         # the enclosure: status, authorized, policy, speed
lsblk -o NAME,SIZE,MODEL,TRAN                                        # the SSD right now: nvme or usb
journalctl -k -b | grep -iE 'thunderbolt|uas|nvme|disconnect' | tail -n 40   # what happened since power-on
```

Then watch for five minutes whether the SSD disappears or appears again (Ctrl+C
to stop):

```bash
udevadm monitor --kernel --subsystem-match=block
```

If GNOME shows a notification about a new or unknown Thunderbolt or USB4
device, do not authorize it; note it.

Write down: `host_reset`, `security`, `iommu_dma_protection`, whether the SSD
is nvme or usb after two minutes, and whether the journal or `udevadm` shows it
disappearing and appearing again (a change of mode).

#### Boot 2: keep the firmware's tunnels

1. Restart, press F11 and choose the stick again.
2. In the stick's menu, highlight the entry you used in section 7 and press `e`.
3. Move to the line that starts with `linux` and to its end. If the line
   contains ` --- `, type a space and `thunderbolt.host_reset=0` at the end. If
   it does not, type ` --- thunderbolt.host_reset=0`.
4. Press Ctrl+X (or F10) to start. Choose *Try Ubuntu* again, open a terminal,
   and repeat the commands of boot 1, plus:

```bash
cat /proc/cmdline                                     # thunderbolt.host_reset=0 is there
cat /sys/module/thunderbolt/parameters/host_reset     # N
grep -H . /sys/bus/thunderbolt/devices/*-*/{authorized,boot} 2>/dev/null   # boot 1: the firmware's tunnel was kept
```

#### Choose the mode

| What boot 2 shows when the desktop appears | Mode | Parameters for section 9 |
|---|---|---|
| The SSD as nvme, with `authorized` 1 and `boot` 1 | **P**: Linux keeps the PCIe tunnel the firmware built | `thunderbolt.host_reset=0` |
| The SSD as usb | **U**: the SSD stays a USB disk and nothing authorizes a PCIe tunnel | `thunderbolt.host_reset=0 systemd.mask=bolt.service` |
| The SSD is not visible | **STOP** | |

In mode P the SSD runs over PCIe from the start of every boot, and bolt finds
it already authorized. In mode U, masking bolt means Ubuntu authorizes no USB4
or Thunderbolt device while the trial lasts (no docks, no external GPUs), and
the SSD runs at the USB speed that `lsusb -t` reports (10 or 20 Gbps).

On **STOP**, the external trial is not viable with this firmware: go to section
27 and decide whether to move the SSD inside without it.

**Check:** you have a mode, P or U, and its parameters; or a STOP.

### 9. Boot for the install and fingerprint the Windows disk

1. Restart, press F11 and choose the stick. Press `e` on the entry you used in
   section 7 and add your mode's parameters exactly as in boot 2, after ` --- `. The installer
   copies everything after ` --- ` into the installed system's boot
   configuration (curtin's `get_carryover_params`), so Ubuntu's first boot uses
   them too.
2. Start, choose *Try Ubuntu*, open a terminal.

Identify the devices again, because their names can differ from section 7:

```bash
cat /proc/cmdline                     # your mode's parameters, after ---
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,FSTYPE,PARTTYPENAME,MOUNTPOINTS
lsblk -o NAME,LOG-SEC,PHY-SEC         # logical sector size of each disk, kept for section 21
```

**STOP** until each device is matched again, as in section 7.

Watch the SSD for five minutes (Ctrl+C to stop):

```bash
udevadm monitor --kernel --subsystem-match=block     # no "remove" or "add" lines for the SSD
```

**STOP** if the SSD disappears or appears again: the chosen mode does not hold.
Go back to section 8.

Fingerprint the Windows disk. These commands only read it; the two files live in
the live session's memory until you restart:

```bash
sudo sfdisk --dump /dev/<windows-disk> > ~/win-gpt-before.txt   # its partition table
sudo sha256sum /dev/<windows-esp> > ~/win-esp-before.sha256      # every byte of its EFI system partition
cat ~/win-gpt-before.txt ~/win-esp-before.sha256
```

**Check:** devices matched, the SSD stable for five minutes, both fingerprint
files written. Do not restart until section 11 has compared them.

## Part D. Install

### 10. Run the installer

Start the installer from the live desktop (its *Install Ubuntu* icon). The
labels below come from the 24.04 installer's source code; check them on screen.

1. **Language, accessibility, keyboard:** your choices.
2. **Internet connection:** *Use wired connection*.
3. If it asks again, **Try or install Ubuntu:** *Install Ubuntu*.
4. **How would you like to install Ubuntu?** *Interactive installation*.
5. **Applications:** *Default selection*.
6. **Optimise your computer:** leave both boxes unchecked, *Install third-party
   software for graphics and Wi-Fi hardware* and *Download and install support
   for additional media formats*. The NVIDIA driver is installed in section 18,
   with the branch and the module source chosen there; the installer would pick
   its own.
7. **Disk setup:** the installer found Windows and preselects *Install Ubuntu
   alongside …*. Choose **Erase disk and install Ubuntu**. Not *alongside*,
   which would shrink Windows and share its disk, and not *Manual
   installation*.
   - *Advanced features...*: keep **None**: no LVM, no encryption, no ZFS.
8. **Choose where to install Ubuntu:** *Select drive:* starts on the first disk,
   which can be the Windows disk. Select the Ubuntu SSD by size and model. *The
   entire disk will be used:* then lists the SSD's current partitions, never
   *Microsoft reserved* or *BitLocker* ones.
   **STOP:** the drive shown is the Ubuntu SSD.
9. **Create your account:** your name, your computer's name, your username and
   a password; keep *Require my password to log in*.
10. **Select your timezone:** Mexico City.
11. **Review your choices:** under *The partition tables of the following
    devices are changed:* exactly one device, the Ubuntu SSD. *Disk encryption*
    shows *None*.
    **STOP, point of no return:** *Install* erases the SSD. Press it only if the
    SSD is the only device listed.
12. When it finishes, choose **Continue testing**, not *Restart now*.

**Check:** the installer reports that the installation finished, and you are
back on the live desktop.

### 11. Before restarting: check what changed

In the same live session as section 9:

```bash
# 1. The Windows disk's partition table and EFI partition are exactly as they were
sudo sfdisk --dump /dev/<windows-disk> | diff ~/win-gpt-before.txt - && echo "Windows partition table unchanged"
sudo sha256sum /dev/<windows-esp> | diff ~/win-esp-before.sha256 - && echo "Windows EFI partition unchanged"

# 2. The SSD now holds an EFI system partition and an ext4 root
lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME,MOUNTPOINTS /dev/<ubuntu-disk>

# 3. The firmware's new "ubuntu" entry points to the SSD's EFI partition
sudo efibootmgr -v
lsblk -o NAME,PARTUUID /dev/<ubuntu-disk>     # the EFI partition's PARTUUID appears in the ubuntu entry

# 4. Your mode's parameters reached the installed system
grep GRUB_CMDLINE_LINUX_DEFAULT /target/etc/default/grub 2>/dev/null \
  || echo "/target is not mounted: check this in section 12"
```

**Check:** both "unchanged" lines print; the SSD has an *EFI System* partition
of about 1 GiB and an ext4 partition filling the rest; the `ubuntu` entry
carries the PARTUUID of the SSD's EFI partition; the parameters are in
`GRUB_CMDLINE_LINUX_DEFAULT`, or, if `/target` was not mounted, section 12
checks them.

If a Windows fingerprint differs, **STOP**. Keep the `diff` output, start
nothing else, and do not try to repair anything. Restart into the firmware boot
menu, start *Windows Boot Manager*, and confirm that Windows works before going
on.

Then restart from the system menu and remove the stick when asked.

## Part E. Base system

### 12. First boot

The firmware starts the first entry of its boot order, normally the new `ubuntu`
entry. If Windows starts instead, restart, press F11 and choose `ubuntu`;
section 20 sets the order.

GRUB shows a menu with Ubuntu and *Windows Boot Manager*, because the installer
found Windows; an arrow key stops its countdown, and if the menu does not appear,
press Esc while the machine starts. **Do not start Windows from this menu**;
section 13 explains why and removes the entry. If section 11 could not confirm
your mode's parameters, press `e` on the Ubuntu entry, add them at the end of the
`linux` line for this boot, and press Ctrl+X.

Log in and open a terminal. Read-only checks:

```bash
grep PRETTY_NAME /etc/os-release                      # Ubuntu 24.04.5 LTS
uname -r                                              # 7.0.0-…-generic: the HWE kernel
[ -d /sys/firmware/efi ] && echo UEFI || echo Legacy  # UEFI
mokutil --sb-state                                    # SecureBoot enabled
cat /proc/cmdline                                     # your mode's parameters
grep GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub     # the same parameters, kept for every boot
findmnt -n -o SOURCE,FSTYPE /                         # the SSD (nvme… in mode P, sd… in mode U), ext4
findmnt -n -o SOURCE /boot/efi                        # the SSD's EFI partition, never the Windows disk
findmnt --fstab -o SOURCE,TARGET,FSTYPE               # / and /boot/efi listed by /dev/disk/by-uuid/…
swapon --show                                         # /swap.img, 8G on this machine
ls /boot/efi/EFI/BOOT /boot/efi/EFI/ubuntu            # BOOTX64.EFI fallback copy; shimx64.efi and grubx64.efi
ip -br addr                                           # the wired interface is UP, with an address
ping -c 3 archive.ubuntu.com                          # network and name resolution
timedatectl                                           # Time zone: America/Mexico_City
```

If the parameters are in `/proc/cmdline` (because you typed them) but not in
`/etc/default/grub`, add them at the end of the quoted value of
`GRUB_CMDLINE_LINUX_DEFAULT` with `sudo nano /etc/default/grub`, then run
`sudo update-grub`.

About the network: the board's wired chip, a Realtek RTL8126 (5 GbE), has a
Linux driver since kernel 6.9. It works on this HWE kernel and would not on
24.04's GA kernel (6.8). Do not switch to the GA kernel.

#### The hardware clock

Windows keeps the hardware clock in local time and Linux, by default, in UTC, so
each system shows the wrong time for a while after the other one ran. Here
Ubuntu adapts. systemd warns that a hardware clock in local time "will create
various problems with time zone changes and daylight saving adjustments";
Mexico City has had no daylight saving time since 2022, which removes the second
problem. Microsoft calls the opposite choice, the `RealTimeIsUniversal` registry
value in Windows, undocumented and unsupported.

Do it once the system clock is right, so that the hardware clock is written
from it:

```bash
timedatectl | grep -E 'synchronized|RTC in local TZ'    # System clock synchronized: yes; RTC in local TZ: no
sudo timedatectl set-local-rtc 1                        # writes the hardware clock from the system clock, in local time
timedatectl | grep 'RTC in local TZ'                    # yes; timedatectl then prints its warning
```

Do not add `--adjust-system-clock`: that option works the other way round. It
sets the system clock from the hardware clock, which at this point may hold the
UTC that Ubuntu wrote or the local time that Windows wrote.

If you ever live where daylight saving time applies, undo it with
`sudo timedatectl set-local-rtc 0` and revisit the decision.

**Check:** every line matches its comment; root and `/boot/efi` are on the SSD;
the parameters are in both `/proc/cmdline` and `/etc/default/grub`.

### 13. Keep Ubuntu away from the Windows disk

#### No Windows entry in GRUB

Starting *Windows Boot Manager* from GRUB runs Windows after shim and GRUB, so
BitLocker measures a different boot chain and asks for the recovery key. Windows
starts from the firmware boot menu instead (F11 → *Windows Boot Manager*).
Turning off os-prober also stops `update-grub` from probing the Windows disk.

```bash
grep -rn OS_PROBER /etc/default/grub /etc/default/grub.d/ 2>/dev/null   # read-only: current setting
grep -i "menuentry.*windows" /boot/grub/grub.cfg                       # read-only: the Windows entry
```

```bash
echo 'GRUB_DISABLE_OS_PROBER=true' | sudo tee /etc/default/grub.d/90-no-os-prober.cfg
sudo update-grub
grep -i "menuentry.*windows" /boot/grub/grub.cfg || echo "no Windows entry"
```

With one system left in it, GRUB hides its menu. To reach it (recovery mode, an
older kernel), press Esc once while the machine starts.

#### The Windows disk hidden from the desktop

The *Files* app lists the Windows partitions under *Other Locations*, and one
click mounts them read-write: with your password for an unencrypted volume, or
with the recovery key, which you keep at hand, for a BitLocker one. Nothing in
this guide needs them. One udev rule tells the desktop's disk service (udisks)
to ignore that disk and its partitions.

Read-only first, the Windows disk's serial number as udev sees it:

```bash
udevadm info --query=property --name=/dev/<windows-disk> | grep -E '^ID_(MODEL|SERIAL_SHORT)='
```

`ID_MODEL` and `ID_SERIAL_SHORT` must be the Windows disk's, as identified in
section 7. (If the output has no `ID_SERIAL_SHORT`, use `ID_SERIAL` and its value
in the rule instead.) Then write the rule with that serial number:

```bash
echo 'ENV{ID_SERIAL_SHORT}=="<windows-serial>", ENV{UDISKS_IGNORE}="1"' \
  | sudo tee /etc/udev/rules.d/99-hide-windows-disk.rules
```

It applies from the next start. Then:

```bash
udevadm info --query=property --name=/dev/<windows-disk> | grep UDISKS_IGNORE   # UDISKS_IGNORE=1
udevadm info --query=property --name=/dev/<windows-esp>  | grep UDISKS_IGNORE   # its partitions too
```

To see the disk again in *Files*, remove that rule file and restart.

**Check:** no Windows entry in GRUB; after a restart the menu stays hidden, Esc
shows it, and Windows still starts from F11; `UDISKS_IGNORE=1` on the Windows
disk and its partitions, and *Files* no longer lists them.

### 14. Updates without automatic reboots

Bring the system up to date once, and restart:

```bash
sudo apt update && sudo apt full-upgrade
sudo reboot
```

What runs by itself (read-only):

```bash
cat /etc/apt/apt.conf.d/20auto-upgrades     # both values "1": daily package lists and unattended upgrades
apt-config dump | grep -E '^Unattended-Upgrade::(Allowed-Origins|Automatic-Reboot|Package-Blacklist)'
```

Unattended upgrades install security updates only, and `Automatic-Reboot` is
absent or `"false"`; both mean no automatic reboot. Keep it that way: the service
host's reboot file does not belong on this machine.

The kernel and the NVIDIA driver change only by hand, between runs (section 30).
A driver update applied while CUDA work runs leaves new processes and
`nvidia-smi` failing until the next reboot. Exclude them from unattended
upgrades:

```bash
sudo tee /etc/apt/apt.conf.d/51unattended-upgrades-workstation >/dev/null <<'EOF'
// GPU workstation: the kernel and the NVIDIA driver change only by hand,
// between runs (install-ubuntu-gpu-workstation.md, section 30).
// Each entry is a Python regular expression matched from the start of a
// package name: "linux-" covers kernels, their NVIDIA modules and firmware.
// secureboot-db writes the firmware's Secure Boot variables, which on this
// dual-boot machine only Windows changes (section 16).
Unattended-Upgrade::Package-Blacklist {
    "linux-";
    "nvidia-";
    "libnvidia-";
    "xserver-xorg-video-nvidia-";
    "secureboot-db";
};
EOF
apt-config dump | grep 'Package-Blacklist::'
sudo unattended-upgrades --dry-run --debug 2>&1 | tail -n 20
```

The desktop's *Software Updater* still offers these updates. Installing them from
there during a run has the same effect, so install them between runs.

**Check:** `apt-config dump` lists the five entries, and the dry run ends
without errors.

### 15. No suspend, and what systemd-oomd does

Suspend stays off on this machine:

- Kernel 7.0 with NVIDIA's open driver hangs when an RTX 50 card resumes from
  suspend (Launchpad bug 2149963: confirmed, no fix as of October 2026).
- During the trial, resuming would also have to rebuild the USB4 tunnels that
  hold the root filesystem.

Ubuntu already disables automatic suspend on AC power; masking the targets also
blocks it from the menu and the power button.

```bash
gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout   # 0 = never, Ubuntu's default
systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target
```

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target   # masked, four times
```

When the bug is fixed, unmask the same four targets with
`sudo systemctl unmask`. Blanking or locking the screen is not suspend; both can
stay as they are.

Ubuntu Desktop also runs **systemd-oomd**. When memory pressure on your session
stays above 50% for 20 seconds, it kills whole groups of processes, starting
with those reclaiming the most memory. A training started from a terminal is a
candidate. It stays enabled; section 26 measures memory, and this is where to see
whether it acted:

```bash
oomctl                                      # what it watches and the current pressure
journalctl -u systemd-oomd --since today    # every kill is logged here
```

**Check:** the four targets are `masked`.

### 16. Secure Boot certificates on a dual-boot machine

Microsoft's 2011 UEFI certificates expired in June 2026 (the KEK on 24 June, the
third-party UEFI CA on 27 June), and *Windows Production PCA 2011* expires on
19 October 2026. Machines keep starting; new boot components are signed with the
2023 certificates, which have to be in the firmware's db and KEK. Canonical's
rotation post (references) explains what it means for Ubuntu.

On this machine **only Windows changes the firmware's Secure Boot variables**
(db, KEK and the revocation list, dbx), and Windows Update handles BitLocker
while doing so. The same changes made from Ubuntu alter what BitLocker measures
outside Windows, and can end on the recovery screen.

Ubuntu Desktop installs one service that writes them by itself: secureboot-db
runs at every start and adds the revocations it ships to dbx. Its first runs fell
inside the BitLocker suspension, so they are harmless; from now on it stays off:

```bash
systemctl is-enabled secureboot-db.service   # read-only: enabled
sudo systemctl mask secureboot-db.service
systemctl is-enabled secureboot-db.service   # masked
```

Section 14 already keeps its package out of unattended upgrades. Everything else
in Ubuntu only reads:

```bash
mokutil --db  | grep 'Subject:'     # certificates trusted to boot
mokutil --kek | grep 'Subject:'     # certificates trusted to update db
```

`Microsoft Corporation UEFI CA 2011` is there: Ubuntu would not have started
without it. The update is complete when these appear too:

```text
Subject: C=US, O=Microsoft Corporation, CN=Microsoft UEFI CA 2023
Subject: C=US, O=Microsoft Corporation, CN=Microsoft Option ROM UEFI CA 2023
Subject: C=US, O=Microsoft Corporation, CN=Microsoft Corporation KEK 2K CA 2023
```

In Windows, the System log records the progress: event 1808 means the device is
fully updated, 1801 that the update is not applied yet. If the command finds no
events, Windows has logged neither state so far.

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=1801,1808} -MaxEvents 5 | Format-List TimeCreated, Id, Message
```

Do not run `sudo fwupdmgr update` for the *UEFI CA*, *UEFI KEK* or *UEFI dbx*
items on this machine, and decline them in the *Software* app. If Windows never
applies the update, applying it from Ubuntu with BitLocker suspended first is a
decision for its own record.

**Check:** `secureboot-db.service` is masked; you know which certificates are
present, and that Windows, not Ubuntu, adds the 2023 ones.

## Part F. NVIDIA driver

### 17. Read-only checks

```bash
lspci -nn -d 10de::0300        # NVIDIA display controllers: two lines, one per GPU
lsmod | grep -E '^(nvidia|nouveau)\b' || echo "no NVIDIA or nouveau module loaded"
uname -r; mokutil --sb-state
sudo ubuntu-drivers list       # available drivers, and the packages that provide their kernel modules
```

The in-kernel `nouveau` driver may be loaded until NVIDIA's is installed; that is
normal.

In the `ubuntu-drivers list` output, look for `nvidia-driver-580-open` with
`kernel modules provided by linux-modules-nvidia-580-open-generic-hwe-24.04`:
that package is the set of precompiled, Canonical-signed modules for this
kernel.

**STOP** if `lspci` shows only one GPU: check its seating, its power cables and
the firmware before installing a driver, which cannot fix a missing device.

**Check:** two GPUs on the bus, and `nvidia-driver-580-open` listed with
precompiled modules.

### 18. Install the 580 driver with open, signed modules

Why these:

- **580** is NVIDIA's long-term support branch, until June 2028, and every CUDA
  13.x runtime runs on it. Without a branch, `ubuntu-drivers install` may pick a
  newer, shorter-lived one.
- **Open kernel modules:** NVIDIA supports Blackwell cards (RTX 50) only with
  them.
- **Precompiled and signed by Canonical:** they load with Secure Boot on, with
  no key to enroll. Modules built locally by DKMS are not signed with Canonical's
  key and need a Machine Owner Key (MOK).
- Not a `-server` branch: Ubuntu's desktop documentation tells desktops to avoid
  them.

```bash
sudo ubuntu-drivers install nvidia:580-open
```

If, during the install, a screen asks you to choose a password to configure
Secure Boot, the driver fell back to DKMS: there were no precompiled modules for
your exact kernel. That path works with one more step. Choose a password; at the
next start, in the blue MOK management screen, choose *Enroll MOK* →
*Continue* → *Yes*, type the password, and reboot. The full upgrade of section
14 usually avoids this, because the precompiled modules are published for the
current kernel.

Before restarting, see which path was taken:

```bash
dpkg -l | grep -E '^ii +(linux-modules-nvidia|nvidia-dkms)'   # expected: linux-modules-nvidia-580-open-…, and no nvidia-dkms
sudo reboot
```

After the restart:

```bash
cat /proc/driver/nvidia/version     # NVIDIA UNIX Open Kernel Module for x86_64  580.…
modinfo -F license nvidia           # Dual MIT/GPL: the open modules
modinfo -F signer nvidia            # not empty: the module is signed
modinfo -n nvidia                   # its file: not under …/updates/dkms/
```

**Check:** the open module of the 580 branch is loaded, signed, and not built by
DKMS; or, on the fallback path, its key is enrolled (`mokutil --list-enrolled`
shows it).

### 19. Verify both GPUs

```bash
nvidia-smi        # both GPUs, driver 580.…, "CUDA Version: 13.0"
nvidia-smi -L     # one line per GPU, with its UUID
nvidia-smi --query-gpu=index,name,uuid,pci.bus_id,memory.total,memory.used,driver_version --format=csv
```

**STOP** if only one GPU appears.

`nvidia-smi` numbers GPUs by PCI bus; CUDA programs number them fastest first
unless told otherwise (`CUDA_DEVICE_ORDER`). The two numberings can disagree,
so this guide selects GPUs by UUID: write down `<uuid-5080>` and `<uuid-4070>`
in your private note.

With the monitor on the RTX 5080, the desktop uses part of its memory. Note
`memory.used` on each GPU at idle, with nothing else running: that is what the
desktop takes.

**Check:** two GPUs of about 16 and 12 GB, the same driver version, the UUIDs
written down, the idle memory noted.

## Part G. Boot validation

### 20. Cases A, B and C, then BitLocker back on

#### Case A: SSD connected, Ubuntu from the boot menu

1. Run `systemctl poweroff`, wait until the PC is off, power on, press F11 and
   choose `ubuntu`.
2. In Ubuntu:

```bash
nvidia-smi -L                                   # two GPUs
ip -br addr && ping -c 3 archive.ubuntu.com     # network
findmnt -n -o SOURCE /                          # the SSD
```

**Check A:** Ubuntu starts, both GPUs are listed, and the network works.

#### Case B: SSD disconnected, Windows alone

1. Run `systemctl poweroff`. When the PC is off, unplug the enclosure.
2. Power on and touch nothing.
3. In Windows, as administrator, run `bcdedit /enum firmware` and note whether
   the `ubuntu` entry is still there. Some firmware deletes the entries of disks
   it no longer finds.

**Check B:** Windows starts by itself, with no recovery screen. BitLocker is
still suspended; the real test comes at the end of this section.

#### Case C: SSD reconnected, both entries

1. Shut Windows down (a full shutdown, now that Fast Startup is off) and
   reconnect the enclosure to the same port.
2. Power on and press F11: *Windows Boot Manager* and `ubuntu` are listed. If
   `ubuntu` is gone, choose the SSD's own entry, shown with its model or the
   enclosure's name: its fallback loader recreates the `ubuntu` entry and starts
   Ubuntu.
3. In Ubuntu, read the boot order:

```bash
sudo efibootmgr     # BootOrder, then one line per entry: Boot0001* ubuntu, Boot0000* Windows Boot Manager, …
```

Ubuntu goes first when its SSD is connected. If it does not, set the order:
every number of `BootOrder`, with `ubuntu`'s first and the rest in their current
order:

```bash
sudo efibootmgr -o XXXX,YYYY,…    # XXXX = ubuntu
sudo efibootmgr                   # BootOrder now starts with XXXX
```

**Check C:** both entries exist, and a cold start with the SSD connected lands
in Ubuntu.

#### BitLocker back on

1. Start Windows from the boot menu (F11 → *Windows Boot Manager*), with the SSD
   connected.
2. As administrator:

```powershell
manage-bde -protectors -enable C:
manage-bde -status C:              # Protection Status: Protection On
manage-bde -protectors -get C:     # note the PCR Validation Profile (this prints the recovery password)
```

3. Restart Windows twice: once with the SSD connected (F11 → *Windows Boot
   Manager*), and once without it (shut down, unplug, power on).

**Check:** no recovery screen in either case. If one appears, type the key, note
in which case, and record it before the trial goes on: a recovery screen at
every start with the SSD connected would make the trial impractical.

From here on BitLocker protects the disk again. Firmware updates, Secure Boot
changes and starting Windows from GRUB would all ask for the key; section 30
says when to suspend it.

## Part H. The USB4 disk during the trial

### 21. Stability, readiness to move, and rules

#### Stability and link, every few boots

```bash
findmnt -n -o SOURCE /       # nvme… in mode P, sd… in mode U
boltctl list                 # mode P: authorized, and its speed (40 Gb/s = 2 lanes * 20 Gb/s); mode U: bolt is masked, so it reports no service
lsusb -t                     # mode U: the SSD's line shows Driver=uas and its speed (10000M or 20000M)

# Disconnects, resets, I/O errors or filesystem errors, in this boot and the previous one
journalctl -k -b    | grep -iE 'disconnect|reset|timeout|I/O error|EXT4-fs (error|warning)'
journalctl -k -b -1 | grep -iE 'disconnect|reset|timeout|I/O error|EXT4-fs (error|warning)'

# Did the previous boot end cleanly? Its log should end with the shutdown
journalctl --list-boots | tail -n 3
journalctl -b -1 -n 15 --no-pager
```

The filter is broad on purpose; ignore lines about other devices and look for
the SSD's name. If the SSD vanished, the journal on it could not record it: the
previous boot's log then simply stops, without the usual shutdown messages
(services stopping, *Reached target … Power-Off* or *Reboot*).

**Check:** no disconnect, reset or I/O error on the SSD and no EXT4 error, in
any boot, and every previous boot ended with a normal shutdown. Count your cold
starts for criterion 1 of section 27.

#### Ready to move inside? (once)

These checks tell whether the installation will start unchanged from an internal
slot (section 31):

```bash
findmnt --fstab -o SOURCE,TARGET                             # mounted by /dev/disk/by-uuid/…, not by a /dev name
ls /boot/efi/EFI/BOOT/BOOTX64.EFI                            # fallback loader: the firmware finds the disk in any slot
grep -E '^CONFIG_BLK_DEV_NVME=' /boot/config-$(uname -r)     # y: the NVMe driver is built in; m: then the next line must count more than 0
lsinitramfs /boot/initrd.img-$(uname -r) | grep -c '/nvme'
lsblk -o NAME,LOG-SEC,PHY-SEC /dev/<ubuntu-disk>            # the logical sector size Linux sees now
```

The logical sector size matters only in mode U. Some USB bridges report a sector
size different from the SSD's own; a partition table written through such a
bridge cannot be read once the SSD sits in a slot. In mode P Linux sees the SSD
directly, so there is nothing to compare. In mode U, compare with the SSD's own
format:

```bash
sudo apt install smartmontools
sudo smartctl -d sntasmedia -a /dev/<ubuntu-disk> | sed -n '/Supported LBA Sizes/,/^$/p'   # "+" marks the format in use
```

`-d sntasmedia` is smartmontools' device type for NVMe disks behind ASMedia USB
bridges; the smartmontools of Ubuntu 24.04 does not recognise the enclosure's
ASM2464PD chip by itself. If it cannot read the disk, use the
`LogicalSectorSize` that Windows reported in section 2, if Windows saw the SSD as
`NVMe`.

**Check:** fstab uses UUIDs, the fallback loader exists, the NVMe driver is
available at boot, and the logical sector size matches the SSD's own. If it does
not, plan to reinstall after the move (section 31).

#### Optional: TRIM, health and speed

```bash
lsblk --discard /dev/<ubuntu-disk>     # DISC-GRAN and DISC-MAX other than 0: TRIM reaches the SSD
systemctl is-enabled fstrim.timer      # enabled: Ubuntu trims once a week
```

In mode U, zeros mean the bridge does not pass TRIM on to Linux. For a trial,
leave it so.

Health: `sudo smartctl -a /dev/<ubuntu-disk>` in mode P, or
`sudo smartctl -d sntasmedia -a /dev/<ubuntu-disk>` in mode U. Look at
*Critical Warning* (0x00), *Percentage Used* and *Temperature*.

Speed, writing nothing to the disk except one temporary file:

```bash
sudo apt install fio
# --readonly makes fio refuse any write: these two runs only read the raw disk
sudo fio --readonly --name=seqread --filename=/dev/<ubuntu-disk> --rw=read --bs=1M \
    --direct=1 --ioengine=libaio --iodepth=32 --runtime=30 --time_based
sudo fio --readonly --name=randread --filename=/dev/<ubuntu-disk> --rw=randread --bs=4k \
    --direct=1 --ioengine=libaio --iodepth=64 --numjobs=4 --group_reporting --runtime=30 --time_based
# 2 GiB written to a temporary file in your home folder, deleted at the end
fio --name=write2g --filename="$HOME/fio.tmp" --size=2G --rw=write --bs=1M \
    --direct=1 --ioengine=libaio --iodepth=16 --unlink=1
```

Keep the numbers: the same runs after section 31 measure what the internal slot
gains.

#### Rules while the root filesystem lives in the enclosure

- Never unplug the enclosure or its cable while Ubuntu runs. Linux loses its root
  filesystem (ext4 shuts down when its disk disappears), the system stops, and
  anything not yet written is lost.
- One rear USB4 port, always the same, connected directly with the enclosure's
  own cable: no hubs, docks or extension cables.
- Leave the enclosure alone in *Settings → Privacy & Security → Thunderbolt*: in
  mode P it is already authorized, and in mode U bolt is masked.
- If the SSD is missing at power-on, the firmware starts the next entry,
  Windows. Reconnect the SSD with the PC off.
- nnU-Net saves a checkpoint every 50 epochs and resumes with `--c`, so a lost
  root filesystem costs at most the epochs since the last checkpoint.

**Check:** you know these rules, and the stability check has run on every boot so
far.

## Part I. Training stack

### 22. Driver, CUDA runtime and CUDA Toolkit

Three different things, often confused:

- **The NVIDIA driver** (system-wide, section 18): kernel modules and `libcuda`.
  There is one per machine, and it sets the newest CUDA version programs can use:
  13.0 for the 580 driver, and any CUDA 13.x through CUDA's minor-version
  compatibility.
- **The CUDA runtime and libraries** (per project): PyTorch's wheels bring their
  own, such as cuBLAS, cuDNN and NCCL, as Python packages. Each project pins its
  own; nothing is installed system-wide.
- **The CUDA Toolkit** (the `nvcc` compiler, headers and tools): needed only to
  compile CUDA code yourself. Training with PyTorch and nnU-Net does not need it.
  Triton, which `torch.compile` uses, brings its own `ptxas` but needs a C
  compiler at runtime, and nnU-Net turns `torch.compile` on by default.

```bash
sudo apt install build-essential curl     # gcc and C headers for Triton; curl for the downloads below
gcc --version
command -v nvcc || echo "no CUDA Toolkit (expected)"
```

**Check:** `gcc` is installed and `nvcc` is not.

### 23. uv, Python and PyTorch

uv, from its official installer, at the version this guide was checked with:

```bash
curl -LsSf https://astral.sh/uv/0.13.0/install.sh | sh    # installs uv into ~/.local/bin
```

Open a new terminal, so that `~/.local/bin` is on your `PATH`, then:

```bash
uv --version      # uv 0.13.0
```

A throwaway project, with Python managed by uv and PyTorch from PyTorch's CUDA
13.0 index. This is the configuration uv's documentation recommends: the index
is explicit, so it serves only `torch`.

```bash
mkdir -p ~/smoke/torch-check && cd ~/smoke/torch-check
uv python install 3.12
uv python pin 3.12       # writes .python-version
cat > pyproject.toml <<'EOF'
[project]
name = "torch-check"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = ["torch==2.14.1"]

[tool.uv.sources]
torch = [{ index = "pytorch-cu130", marker = "sys_platform == 'linux'" }]

[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true
EOF
uv sync
```

Why these versions (October 2026): PyTorch 2.14.1 is the current release. Its
CUDA 13.0 and 13.2 builds include Blackwell (compute capability 12.0); its 12.6
build does not. The RTX 4070 (8.9) runs the builds' 8.6 code. CUDA 13.0 is the
580 driver's own version. PyTorch 2.15, due on 28 October 2026, makes its stable
builds with CUDA 13.2 only, which also runs on the 580 driver.

A check that both GPUs compute:

```bash
cat > check_gpus.py <<'EOF'
"""Smoke test: PyTorch sees both GPUs and can compute on each."""
import torch

print("torch", torch.__version__, "| CUDA runtime", torch.version.cuda)
print("compiled for", torch.cuda.get_arch_list())
assert torch.cuda.is_available(), "CUDA is not available"
count = torch.cuda.device_count()
for i in range(count):
    p = torch.cuda.get_device_properties(i)
    print(f"cuda:{i}  {p.name}  uuid={getattr(p, 'uuid', 'n/a')}  "
          f"{p.total_memory / 2**30:.1f} GiB  capability {p.major}.{p.minor}")
    x = torch.randn(4096, 4096, device=f"cuda:{i}")
    print(f"cuda:{i}  matmul ok, sum={(x @ x).sum().item():.3e}")
assert count == 2, f"expected 2 GPUs, found {count}"
EOF
uv run python check_gpus.py
```

And one that `torch.compile` builds and runs a kernel on each:

```bash
cat > check_compile.py <<'EOF'
"""Smoke test: torch.compile builds and runs a kernel on each GPU."""
import torch


def f(x):
    return torch.sin(x) + 2 * x


compiled = torch.compile(f)
for i in range(torch.cuda.device_count()):
    x = torch.randn(1_000_000, device=f"cuda:{i}")
    torch.testing.assert_close(compiled(x), f(x))
    print(f"cuda:{i}  torch.compile ok")
EOF
uv run python check_compile.py
```

**Check:** two devices; names and UUIDs match `nvidia-smi -L` (PyTorch may print
the UUID without the `GPU-` prefix); about 16 and 12 GiB; capabilities 12.0 and
8.9; the matmul and `torch.compile` pass on both. Note which GPU PyTorch calls
`cuda:0`, rather than assuming it.

### 24. PCIe link under load

GPUs lower their PCIe link speed when idle; NVIDIA documents that the current
values "may be reduced when the GPU is not in use". Read the link under load.

What to expect: with two cards, the board runs its two GPU slots at x8 each
(ASRock). The RTX 5080 is a PCIe 5.0 card and the RTX 4070 a PCIe 4.0 card. Under
load, expect the 5080 at Gen5 x8 and the 4070 at Gen4 x8. Neither the x8 nor the
4070's Gen4 is a fault.

```bash
cd ~/smoke/torch-check
cat > load_gpus.py <<'EOF'
"""Keep every GPU busy for 60 seconds so that its PCIe link runs at full speed."""
import time

import torch

xs = [torch.randn(8192, 8192, device=f"cuda:{i}") for i in range(torch.cuda.device_count())]
end = time.time() + 60
while time.time() < end:
    for x in xs:
        x @ x
    for i in range(len(xs)):
        torch.cuda.synchronize(i)
EOF
uv run python load_gpus.py &      # 60 seconds, in the background
sleep 20
nvidia-smi --query-gpu=index,name,pcie.link.gen.gpucurrent,pcie.link.gen.max,pcie.link.gen.gpumax,pcie.link.gen.hostmax,pcie.link.width.current,pcie.link.width.max --format=csv
sudo lspci -vv -d 10de::0300 | grep -E '^[0-9a-f]|LnkCap:|LnkSta:'
wait
```

How to read it:

- `gpucurrent` is the generation in use now; `gpumax` is what the GPU supports;
  `hostmax` is what the slot's root port supports; `max` is the most this GPU can
  reach in this system.
- In `lspci`, `LnkCap` is what the device can do and `LnkSta` what was
  negotiated. `(downgraded)` next to the width is expected here: x8 of x16.

**Check:** under load, each GPU's generation equals its `max`, and its width is
x8. If a generation stays below `max` under load, or a width below x8, check the
card's seating and *Advanced > AMD PBS > PCIe x16 Link Speed* (Auto) before
training.

### 25. nnU-Net on a small public dataset

nnU-Net needs three folders: `nnUNet_raw`, `nnUNet_preprocessed` and
`nnUNet_results`. They go on the Linux filesystem (ext4 on the Ubuntu SSD), never
on the Windows disk: NTFS through Linux is slow, and that volume is encrypted
anyway. During the trial everything lives on the USB4 SSD. Preprocessed data is
read at every training iteration, so it is the part that gains most from fast
storage. The paths below serve this test only and are set per terminal session;
each project decides its own layout.

```bash
mkdir -p ~/smoke/nnunet && cd ~/smoke/nnunet
uv python pin 3.12
cat > pyproject.toml <<'EOF'
[project]
name = "nnunet-check"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = ["torch==2.14.1", "nnunetv2==2.8.1"]

[tool.uv.sources]
torch = [{ index = "pytorch-cu130", marker = "sys_platform == 'linux'" }]

[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true
EOF
uv sync
uv run python -c "import torch; print(torch.__version__, torch.version.cuda)"   # 2.14.1+cu130 13.0
```

nnU-Net's documentation asks for PyTorch to be installed before nnU-Net, so that
nnU-Net does not bring in a default PyTorch build. Here uv resolves both together
and takes `torch` only from the CUDA index; the last line confirms it.

```bash
cat > env.sh <<'EOF'
# nnU-Net folders for the smoke test. In each new terminal: source ~/smoke/nnunet/env.sh
export nnUNet_raw="$HOME/smoke/nnunet/data/raw"
export nnUNet_preprocessed="$HOME/smoke/nnunet/data/preprocessed"
export nnUNet_results="$HOME/smoke/nnunet/data/results"
# nnU-Net's benchmark trainers accept only fold 0, so for benchmarks each GPU
# writes to its own results folder
export RESULTS_5080="$HOME/smoke/nnunet/data/bench-5080"
export RESULTS_4070="$HOME/smoke/nnunet/data/bench-4070"
EOF
source env.sh
mkdir -p "$nnUNet_raw" "$nnUNet_preprocessed" "$nnUNet_results" "$RESULTS_5080" "$RESULTS_4070" download ~/smoke/logs
```

The dataset is *Task04_Hippocampus* of the Medical Segmentation Decathlon: small
and public (CC BY-SA 4.0). Its official distribution is the Decathlon's Google
Drive folder, linked from medicaldecathlon.com; MONAI's mirror allows a
command-line download and publishes its MD5 checksum:

```bash
cd ~/smoke/nnunet/download
curl -LO https://msd-for-monai.s3-us-west-2.amazonaws.com/Task04_Hippocampus.tar
md5sum Task04_Hippocampus.tar      # 9d24dba78a72977dbd1d2e110310f31b
tar -xf Task04_Hippocampus.tar
cd ~/smoke/nnunet
uv run nnUNetv2_convert_MSD_dataset -i download/Task04_Hippocampus
uv run nnUNetv2_plan_and_preprocess -d 4 --verify_dataset_integrity
```

Each GPU alone, for five epochs, with nnU-Net's benchmark trainer. Each run is
pinned to a UUID, so nothing depends on how the GPUs are numbered. The benchmark
trainers stop with an error on any fold other than 0, so both GPUs run fold 0,
each into its own results folder. `nnUNet_n_proc_DA=8` matches the runs of
section 26, so the times compare:

```bash
source env.sh
CUDA_VISIBLE_DEVICES=<uuid-5080> nnUNet_n_proc_DA=8 nnUNet_results="$RESULTS_5080" \
    uv run nnUNetv2_train 4 3d_fullres 0 -tr nnUNetTrainerBenchmark_5epochs
CUDA_VISIBLE_DEVICES=<uuid-4070> nnUNet_n_proc_DA=8 nnUNet_results="$RESULTS_4070" \
    uv run nnUNetv2_train 4 3d_fullres 0 -tr nnUNetTrainerBenchmark_5epochs

# Keep the results: the runs of section 26 write to the same place
F="Dataset004_Hippocampus/nnUNetTrainerBenchmark_5epochs__nnUNetPlans__3d_fullres/fold_0/benchmark_result.json"
cp "$RESULTS_5080/$F" ~/smoke/logs/alone-5080.json
cp "$RESULTS_4070/$F" ~/smoke/logs/alone-4070.json
cat ~/smoke/logs/alone-*.json
```

If `torch.compile` fails inside nnU-Net, putting `nnUNet_compile=f` in front of
the command turns it off. Note it, because it changes the speed.

**Check:** both runs finish, and each `benchmark_result.json` reports its epoch
time.

### 26. Two independent trainings, one per GPU

There is no DDP here: each GPU trains its own fold, as nnU-Net's documentation
recommends for several GPUs. For each training, nnU-Net starts
`nnUNet_n_proc_DA` data-augmentation processes for training (12 by default) and
half as many for validation, so two trainings with the defaults would start 36
processes on 24 threads. With `nnUNet_n_proc_DA=8`, each starts 8 plus 4: 24 in
all, plus the two main processes. Start there and measure.

Runs go in `tmux`, which keeps them alive if the terminal closes and lets you
come back to them, later also over SSH. `tmux new -s smoke` starts a session;
inside it, Ctrl+b then c opens a new window, Ctrl+b then n moves to the next one,
and Ctrl+b then d leaves the session running; `tmux attach -t smoke` comes back.

```bash
sudo apt install htop tmux
tmux new -s smoke
```

Window 0 holds the monitors, one log per run. Start them before each run, with
that run's name, and stop them when it ends:

```bash
cd ~/smoke/logs
RUN=together      # one name per run: together, nodataloading, night
# Both GPUs every 5 s: utilization, memory, temperature, power, clocks and throttle reasons
nvidia-smi --query-gpu=timestamp,index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.sm,clocks_event_reasons.active --format=csv,nounits -l 5 > "gpu-$RUN.csv" &
# Memory, swap, run queue (r) and I/O wait (wa), every 5 s
vmstat -w 5 > "vmstat-$RUN.log" &
```

When the run has ended, stop them in the same window:

```bash
kill %1 %2
```

Both benchmarks at once, started together. In window 1, for the RTX 5080:

```bash
cd ~/smoke/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-5080> nnUNet_n_proc_DA=8 nnUNet_results="$RESULTS_5080" \
    uv run nnUNetv2_train 4 3d_fullres 0 -tr nnUNetTrainerBenchmark_5epochs
```

In window 2, for the RTX 4070:

```bash
cd ~/smoke/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-4070> nnUNet_n_proc_DA=8 nnUNet_results="$RESULTS_4070" \
    uv run nnUNetv2_train 4 3d_fullres 0 -tr nnUNetTrainerBenchmark_5epochs
```

While they run, watch `htop` in another window (are all 24 threads busy? is swap
in use?) and `free -h`. When both have finished, keep the results:

```bash
cd ~/smoke/nnunet && source env.sh
F="Dataset004_Hippocampus/nnUNetTrainerBenchmark_5epochs__nnUNetPlans__3d_fullres/fold_0/benchmark_result.json"
cp "$RESULTS_5080/$F" ~/smoke/logs/together-5080.json
cp "$RESULTS_4070/$F" ~/smoke/logs/together-4070.json
```

Repeat both at once with the benchmark trainer that feeds the GPU without
loading any data, with the monitors under `RUN=nodataloading`. In window 1:

```bash
CUDA_VISIBLE_DEVICES=<uuid-5080> nnUNet_results="$RESULTS_5080" \
    uv run nnUNetv2_train 4 3d_fullres 0 -tr nnUNetTrainerBenchmark_5epochs_noDataLoading
```

In window 2, at the same time:

```bash
CUDA_VISIBLE_DEVICES=<uuid-4070> nnUNet_results="$RESULTS_4070" \
    uv run nnUNetv2_train 4 3d_fullres 0 -tr nnUNetTrainerBenchmark_5epochs_noDataLoading
```

When both have finished:

```bash
F="Dataset004_Hippocampus/nnUNetTrainerBenchmark_5epochs_noDataLoading__nnUNetPlans__3d_fullres/fold_0/benchmark_result.json"
cp "$RESULTS_5080/$F" ~/smoke/logs/nodataloading-5080.json
cp "$RESULTS_4070/$F" ~/smoke/logs/nodataloading-4070.json
```

The night run, with the monitors under `RUN=night`: nnU-Net's default trainer
(1000 epochs) on fold 0 and fold 1 at once. This trainer takes any fold, and both
runs write to the common results folder. In window 1, the RTX 5080 on fold 0:

```bash
cd ~/smoke/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-5080> nnUNet_n_proc_DA=8 uv run nnUNetv2_train 4 3d_fullres 0
```

In window 2, the RTX 4070 on fold 1:

```bash
cd ~/smoke/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-4070> nnUNet_n_proc_DA=8 uv run nnUNetv2_train 4 3d_fullres 1
```

nnU-Net writes each epoch's duration to the training log in each fold's folder.
When the runs are over, summarize each GPU log:

```bash
cd ~/smoke/logs
# Per run and GPU: peak memory (MiB), mean utilization (%), peak temperature (C), mean power (W)
for f in gpu-*.csv; do
  echo "== $f"
  awk -F', ' 'NR > 1 { g = $2; n[g]++; u[g] += $4; p[g] += $8
                       if ($5 > m[g]) m[g] = $5; if ($7 > t[g]) t[g] = $7 }
              END { for (g in n) printf "GPU %s: peak memory %d MiB, utilization %.0f%%, peak %d C, power %.0f W\n",
                                        g, m[g], u[g] / n[g], t[g], p[g] / n[g] }' "$f"
done
```

Record:

| Measure | RTX 5080 | RTX 4070 | Source |
|---|---|---|---|
| Epoch time, alone (benchmark) | | | `alone-*.json` |
| Epoch time, both at once | | | `together-*.json` |
| Epoch time without data loading, both at once | | | `nodataloading-*.json` |
| Epoch time, night run | | | each fold's training log |
| Peak GPU memory | | | `gpu-together.csv`, `gpu-night.csv` |
| Mean utilization, peak temperature, mean power against the limit | | | the same logs |
| Throttle reasons seen | | | the same logs, last column |
| System memory and swap at the peak | | | `vmstat-<run>.log`, `free -h` |
| Run queue `r` against 24 threads; I/O wait `wa` | | | `vmstat-<run>.log` |
| systemd-oomd kills | | | `journalctl -u systemd-oomd` |

How to read it:

- If the benchmark without data loading is much faster than the normal one, data
  loading limits training: a run queue above 24 points at the CPU, a high `wa` at
  the disk.
- If the times together are close to the times alone, the two trainings do not
  get in each other's way. If they are much slower together, they compete for
  CPU, memory or disk: adjust `nnUNet_n_proc_DA`.
- The 4070's epoch time against the 5080's shows what the second GPU adds. This
  dataset is tiny: decide the role of the 4070 by repeating this section with
  the real dataset and model.

**Check:** the night run finishes both folds without errors, the table is
filled, and systemd-oomd killed nothing.

## Part J. Decide, then finish

### 27. Go/no-go: move the SSD inside?

| # | Criterion | Measured in | Result |
|---|---|---|---|
| 1 | Boot: five consecutive cold starts with no crash, reset or change of mode in the journal | Section 21 | |
| 2 | GPUs: both visible with the 580 open driver and Secure Boot on | Sections 19 and 23 | |
| 3 | Training: PyTorch, `torch.compile` and nnU-Net on each GPU; two trainings at once through a night without errors | Sections 23 to 26 | |
| 4 | Windows: starts alone with the SSD unplugged, and BitLocker asks for no key | Section 20 | |
| 5 | Disk: low I/O wait while training | Section 26 | |
| 6 | Daily use: Ubuntu Desktop works for local work | Your judgement | |

How to read the result:

- **2 or 3 fails:** moving the SSD will not fix it. Do not take the PC apart; the
  problem is in the driver or the training stack.
- **1 or 5 fails, with 2 to 4 passing:** that is what the internal slot fixes.
  Move the SSD (section 31).
- **Everything passes:** the internal slot no longer decides whether it works. It
  removes the risk of a disconnect during long runs and gives a faster disk;
  weigh that against taking the PC apart.
- **Section 8 ended in STOP**, with no stable USB4 mode: the trial could not run
  externally. Decide whether to move the SSD inside without it. If you do, follow
  steps 2 to 5 of section 31 for the physical move, then install from section 7
  with the SSD already in its slot: skip section 8, add no parameters in sections
  9 and 12, and skip what section 21 says about the enclosure.

Record the table and the decision in a decision record.

**Check:** every criterion has a result, and the decision is recorded.

### 28. Sensors, fans and lighting (optional)

The fan curves that protect the hardware live in the firmware (*H/W Monitor*,
section 6). Linux reads the sensors. Each GPU's fans follow the NVIDIA firmware
and driver automatically; nothing is set here.

```bash
sudo apt install lm-sensors
sensors                      # k10temp: Tctl, Tccd1, Tccd2 (CPU); nvme: Composite (mode P)
sudo modprobe nct6775        # driver for the board's main monitoring chip, a Nuvoton NCT6796D-S
sensors                      # if the driver binds: an nct6799-isa-… block with fan speeds and voltages
sudo dmesg | grep -i nct6775 # if it does not: the reason, for example an ACPI resource conflict
```

If the new readings make sense, load the driver at every start:

```bash
echo nct6775 | sudo tee /etc/modules-load.d/nct6775.conf
```

The board has a second monitoring chip, an NCT6686D. Its Linux driver (`nct6683`)
only reads, and only on boards it recognises; do not force it.

GPU temperatures and fans:
`nvidia-smi --query-gpu=index,name,temperature.gpu,fan.speed --format=csv`.

Lighting and fan software is optional, and nothing here promises it works:

- **OpenRGB** lists no ASRock board by model. It supports *ASRock Polychrome USB*
  controllers (USB ID `26ce:01a2`), ASRock's SMBus lighting controllers, and
  several Lian Li hubs (USB vendor `0cf2`). See what this machine has with
  `lsusb | grep -iE '26ce|0cf2'`. Official builds: https://openrgb.org.
- **CoolerControl** controls only fans whose driver exposes writable PWM
  channels, and a fan that the firmware also controls ends up with two masters.
  Documentation: https://docs.coolercontrol.org.
- The simplest path is to set the lighting once, from Windows or the firmware.
  Whether it holds in Ubuntu depends on the controller: check after starting
  Ubuntu.

**Check:** `sensors` shows the CPU temperature, and `nvidia-smi` the temperature
of both GPUs.

### 29. SSH

Only once the machine works locally, that is, after section 20 passed. Ubuntu
Desktop does not install an SSH server.

```bash
sudo apt install openssh-server
systemctl status ssh.socket --no-pager     # active (listening): sshd starts at the first connection
ssh-import-id gh:<github-user>             # your public keys from GitHub into ~/.ssh/authorized_keys
```

From the laptop, `ssh <user>@<lan-ip>` must log in with the key. Then refuse
passwords. Read-only first: for each setting `sshd` keeps the first value it
reads, and it reads the files in `/etc/ssh/sshd_config.d/` in name order:

```bash
sudo sshd -T | grep -i '^passwordauthentication'    # effective value
ls /etc/ssh/sshd_config.d/
```

```bash
echo 'PasswordAuthentication no' | sudo tee /etc/ssh/sshd_config.d/00-local.conf
sudo sshd -t && sudo systemctl restart ssh
sudo sshd -T | grep -i '^passwordauthentication'    # passwordauthentication no
```

From the laptop:

```bash
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password <user>@<lan-ip>
# expected: Permission denied (publickey)
```

Access from outside the house comes with Tailscale, in its own guide.

**Check:** login with the key works, and login with a password is refused.

### 30. Maintenance between runs

Kernel and NVIDIA updates, between runs only:

```bash
sudo apt update
apt list --upgradable 2>/dev/null | grep -E '^(linux-|nvidia-|libnvidia-|xserver-xorg-video-nvidia-)' \
  || echo "no kernel or NVIDIA updates"
sudo apt full-upgrade
sudo reboot
```

After the restart:

```bash
nvidia-smi -L                                            # both GPUs
cd ~/smoke/torch-check && uv run python check_gpus.py    # both compute
```

If an NVIDIA package was upgraded and the machine was not restarted,
`nvidia-smi` and new CUDA programs fail with *Failed to initialize NVML:
Driver/library version mismatch*: the new libraries do not match the kernel
module still loaded. A restart fixes it, and it is the reason these updates
wait for the gap between runs.

If a new kernel misbehaves, press Esc while the machine starts, choose *Advanced
options for Ubuntu*, and start the previous kernel.

Firmware (BIOS) updates:

1. In Windows: `manage-bde -protectors -disable C: -RebootCount 0`. ASRock notes
   that a BIOS update can bring up the BitLocker recovery screen.
2. Update with *Instant Flash*, then apply section 6 again: an update can reset
   settings and boot entries. The Ubuntu SSD still starts through its fallback
   loader if its entry is gone (section 20, case C).
3. Start Windows from the boot menu, run `manage-bde -protectors -enable C:`, and
   restart once.

**Check:** after each round of maintenance, both GPUs are listed, the smoke test
passes, and BitLocker protection is on.

### 31. Move the SSD inside (only if section 27 says so)

Before opening the PC:

1. The checks of section 21 under *Ready to move inside?* pass. If the logical
   sector size did not match, plan to reinstall from section 7 once the SSD is in
   its slot.
2. In Windows: `manage-bde -protectors -disable C: -RebootCount 0`. Taking the
   GPUs out and putting them back is a planned hardware change.
3. Note which slot each GPU is in and which power cables it uses: they go back
   the same way.

The move:

4. Shut down, switch the power supply off and unplug it. Take the SSD out of the
   enclosure and install it in a free slot among M2_2, M2_3 and M2_4 (PCIe Gen4
   x4, from the chipset). ASRock lists no lane sharing between these slots and
   the GPU slots, which stay at x8 each. Follow the board manual for the slot's
   screw and heatsink. The Windows disk stays where it is.
5. Put the GPUs back in their slots, with their cables.

First start:

6. In the firmware, the new disk is detected; the boot menu (F11) shows `ubuntu`
   or the SSD's own entry.
7. In Ubuntu, read-only:

```bash
findmnt -n -o SOURCE /                              # /dev/nvme…: the SSD, now in its slot
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,MOUNTPOINTS    # TRAN nvme
grep GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub   # still carries the trial's USB4 parameters
```

8. Remove the trial's USB4 parameters; they would change how any USB4 device
   behaves from now on:

```bash
sudo sed -i -e 's/ *thunderbolt\.host_reset=0//g' -e 's/ *systemd\.mask=bolt\.service//g' /etc/default/grub
grep GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub   # without them, typically "quiet splash"
sudo update-grub
sudo reboot
```

9. After the restart, repeat the checks of section 12: root and `/boot/efi` on
   the SSD, Secure Boot on, and `/proc/cmdline` without the trial's parameters.
   Then `nvidia-smi -L`: the GPUs' indexes may change with the new bus layout,
   their UUIDs do not. If the trial ran in mode U, `boltctl list` works again.
10. Start Windows from the boot menu, run `manage-bde -protectors -enable C:`, and
    restart once: no recovery screen.
11. Repeat the benchmarks of section 26 and the `fio` runs of section 21, and
    compare them with the trial's numbers.
12. Update this guide's status line and the decision record of section 27.

**Check:** Ubuntu starts from the internal slot with the default kernel
parameters, Windows starts from the boot menu with BitLocker on, and the new
numbers are recorded.

## Next

- **Access from outside the house:** Tailscale, in its own guide.
- **A UPS** is worth considering for long runs: with *Power Off* after a power
  cut nothing starts again by itself, and a run is lost back to its last
  checkpoint.

## References

Ubuntu and Canonical:

- *Ubuntu 24.04.5 LTS released*:
  https://discourse.ubuntu.com/t/ubuntu-24-04-5-lts-released/87608
- Kernel lifecycle and HWE: https://ubuntu.com/kernel/lifecycle
- *How to verify your Ubuntu download*:
  https://ubuntu.com/tutorials/how-to-verify-ubuntu
- *Create a bootable USB stick with Rufus on Windows*:
  https://ubuntu.com/tutorials/create-a-usb-stick-on-windows
- Desktop installer source, 24.04 branch (screen labels and page order):
  https://github.com/canonical/ubuntu-desktop-provision/tree/ubuntu/24.04
- curtin, carry-over of kernel parameters after `---`:
  https://github.com/canonical/curtin/blob/master/curtin/commands/install_grub.py
- *Microsoft UEFI CA rotation: What it means for Ubuntu users and vendors*:
  https://discourse.ubuntu.com/t/microsoft-uefi-ca-rotation-what-it-means-for-ubuntu-users-and-vendors/82652
- Secure Boot in Ubuntu:
  https://documentation.ubuntu.com/security/docs/security-features/platform-protections/secure-boot/
- *Install NVIDIA drivers* (Desktop):
  https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/
- Launchpad bug 2149963 (kernel 7.0, open driver, RTX 50, resume):
  https://bugs.launchpad.net/bugs/2149963
- Launchpad bug 2167127 (the withdrawn 24.04.5 Desktop image):
  https://bugs.launchpad.net/bugs/2167127

Microsoft:

- *BitLocker recovery overview*:
  https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/recovery-overview
- *BitLocker FAQ*:
  https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/faq
- `manage-bde -protectors`:
  https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/manage-bde-protectors
- Windows Secure Boot certificate expiration (KB5062710):
  https://support.microsoft.com/help/5062710

NVIDIA, PyTorch, uv and nnU-Net:

- Open kernel modules (R580 README):
  https://download.nvidia.com/XFree86/Linux-x86_64/580.95.05/README/kernel_open.html
- Driver branches and their support periods:
  https://docs.nvidia.com/datacenter/tesla/drivers/supported-drivers-and-cuda-toolkit-versions.html
- `nvidia-smi`: https://docs.nvidia.com/deploy/nvidia-smi/index.html
- CUDA environment variables:
  https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html
- PyTorch release matrix: https://github.com/pytorch/pytorch/blob/main/RELEASE.md
- uv with PyTorch: https://docs.astral.sh/uv/guides/integration/pytorch/
- nnU-Net documentation:
  https://github.com/MIC-DKFZ/nnUNet/tree/master/documentation
- Medical Segmentation Decathlon: https://medicaldecathlon.com
- MONAI's mirror and checksums:
  https://github.com/Project-MONAI/MONAI/blob/dev/monai/apps/datasets.py

Linux:

- USB4 and Thunderbolt: https://docs.kernel.org/admin-guide/thunderbolt.html
- `boltctl`: https://gitlab.freedesktop.org/bolt/bolt/-/blob/master/docs/boltctl.1.txt
- Kernel command line understood by systemd (`systemd.mask=`):
  https://www.freedesktop.org/software/systemd/man/latest/kernel-command-line.html
- `timedatectl`: https://www.freedesktop.org/software/systemd/man/latest/timedatectl.html
- `oomd.conf` (systemd-oomd):
  https://www.freedesktop.org/software/systemd/man/latest/oomd.conf.html
- Hardware monitoring drivers: https://docs.kernel.org/hwmon/nct6775.html,
  https://docs.kernel.org/hwmon/nct6683.html and
  https://docs.kernel.org/hwmon/k10temp.html
- smartmontools and USB bridges: https://www.smartmontools.org/wiki/USB
- `fio`: https://fio.readthedocs.io/en/latest/fio_doc.html

Hardware:

- ASRock X870E Taichi Lite, specifications:
  https://www.asrock.com/mb/AMD/X870E%20Taichi%20Lite/index.asp
- ASRock X870E Taichi Lite, user manual:
  https://download.asrock.com/Manual/X870E%20Taichi%20Lite.pdf
- ASRock, *AMD 800 Series Motherboard Software/BIOS Setup Guide*:
  https://download.asrock.com/Manual/Software/AMD%20X870/Software_BIOS%20Setup%20Guide_English.pdf
- UGREEN 40 Gbps M.2 NVMe enclosure:
  https://us.ugreen.com/products/ugreen-40gbps-m-2-nvme-enclosure-with-cooling-fan
- Rufus: https://rufus.ie and https://github.com/pbatard/rufus/releases
