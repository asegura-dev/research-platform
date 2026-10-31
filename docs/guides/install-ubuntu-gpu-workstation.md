# Install Ubuntu Desktop on the GPU workstation

> **Scope:** the dual-boot GPU workstation only. Windows keeps its internal
> NVMe disks, which the install never writes to; afterwards, Ubuntu writes to
> the data disk only if you open it (section 13). Ubuntu Desktop goes on its own
> internal NVMe SSD, in M2_1, with its own EFI system partition and boot loader.
> For a single-OS service host, use
> [install-ubuntu-server.md](install-ubuntu-server.md). Stress tests and
> benchmarks come next, in
> [validate-gpu-workstation.md](validate-gpu-workstation.md).

> **Status:** written from official documentation and source code on
> 2026-10-13. First run on 2026-10-21, through section 20, with Ubuntu 24.04.5
> LTS, kernel 7.0.0-38-generic, NVIDIA driver 580.178.04 (open modules, signed
> by Canonical), Secure Boot on, and Windows 11 with BitLocker; rewritten from
> that run on 2026-10-22. Section 22 ran on 2026-10-28 and was revised from it;
> section 23 ran without problems by 2026-10-29; section 21 has not run yet.
> The wired port is still to be checked: it reported DOWN, and the run used
> Wi-Fi.

> **History:** until that run, this guide put the SSD in a USB4 enclosure first,
> as a trial before opening the PC. The enclosure disconnected, in Windows and
> in the middle of the install, so the SSD went inside without the trial
> ([ADR-010](../adr/ADR-010-the-ubuntu-ssd-goes-inside-the-workstation.md)).
> That version is in the repository's history:
> `git show 8141750:docs/guides/install-ubuntu-gpu-workstation.md`.

How to follow it:

- Every section ends with a **Check:**. Do not start the next section until it
  passes.
- **STOP** marks a point where you confirm something before going on.
- Read-only commands come first. A command that changes something comes after
  them, and only once their output matches what the section expects.
- Outputs quoted here are examples; names, serial numbers and versions on your
  machine will differ.
- Copy commands from this guide instead of typing them: open it in a browser on
  the PC itself, in Windows and, from section 9 on, in Firefox in Ubuntu (the
  repository is public). In a terminal, paste with Ctrl+Shift+V. Replace every
  `<placeholder>` before pressing Enter.
- When something does not look as a section expects, read *If something goes
  wrong*, near the end, before improvising.

## Hardware

| Part | Model |
|---|---|
| Board | ASRock X870E Taichi Lite, firmware 4.10 at the first run |
| CPU | AMD Ryzen 9 7900X, 12 cores, 24 threads |
| Memory | 64 GB DDR5 |
| GPUs | NVIDIA RTX 5080 16 GB (Blackwell, PCIe 5.0), which drives the monitor, and RTX 4070 12 GB (Ada, PCIe 4.0) |
| Windows disk | WD_BLACK SN850X 1 TB: Windows 11, encrypted with BitLocker |
| Windows data disk | Kingston KC3000 1 TB (SKC3000S1024G) in a chipset slot, M2_2 to M2_4: an NTFS data volume, also encrypted; optional |
| Ubuntu disk | Kingston FURY Renegade 2 TB (SFYRD2000G) in M2_1 |

## Placeholders

- `<windows-eui>`, `<data-eui>` and `<ubuntu-eui>`: the NVMe identifiers of the
  Windows disk, the Windows data disk and the Ubuntu SSD, as Linux writes them
  in `/dev/disk/by-id/nvme-eui.<identifier>`. Sections 2 and 8 read them from
  Windows; section 9 checks them in Linux.
- `<uuid-5080>` and `<uuid-4070>`: the GPUs' UUIDs as `nvidia-smi -L` prints
  them (`GPU-…`).
- `<user>`, `<github-user>`, `<lan-ip>`.

Linux device names such as `nvme0n1` are not identities: they can change from
one boot to the next, and on this machine they did. The commands below reach
each disk through its `/dev/disk/by-id/nvme-eui.…` link, which does not change.
Steps marked "if there is one" concern the Windows data disk; skip them without
it.

Never commit serial numbers, NVMe identifiers, GPU UUIDs, hostnames, addresses,
or BitLocker recovery keys and their IDs to this repository.

## Decisions this guide depends on

| Decision | Value here | Why | Record |
|---|---|---|---|
| Release | Ubuntu Desktop 24.04.5.1 LTS, the Desktop rebuild of 24.04.5 | The same release on every host | [ADR-001](../adr/ADR-001-ubuntu-24-04-lts-on-every-host.md) |
| Image and kernel | Desktop, with its default HWE kernel (7.0) | The machine is used at its own screen; the GA kernel (6.8) has no driver for the board's RTL8126 network chip | [ADR-009](../adr/ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) |
| Ubuntu disk | Its own SSD with its own EFI system partition, ext4, no LVM, no encryption | Windows never depends on it, and it never depends on Windows | [ADR-009](../adr/ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) |
| Slot | M2_1, inside the PC; no USB4 enclosure | M2_1 is on the CPU's lanes; over USB4 the enclosure disconnected | [ADR-010](../adr/ADR-010-the-ubuntu-ssd-goes-inside-the-workstation.md) |
| Starting Windows | Only from the firmware boot menu, never from GRUB | Windows never depends on Ubuntu's boot loader, and BitLocker always measures the same boot chain | [ADR-009](../adr/ADR-009-the-workstation-runs-ubuntu-desktop-on-its-own-disk.md) |
| Default boot | Ubuntu first | Ubuntu is the workstation's default system | [ADR-003](../adr/ADR-003-the-workstation-boots-native-ubuntu-not-wsl2.md) |
| BitLocker | On in Windows. Protection of C: suspended before any firmware, disk or boot change made while it is encrypted (section 3, or section 7 once Windows has encrypted itself), and back on at the end | The firmware, the disks and the boot chain change in between | Sections 3, 7 and 20 |
| Monitor | On the RTX 5080, as before | Windows is used as before; section 19 measures what the desktop takes | Section 19 |
| Restore on AC/Power Loss | Power Off | Nothing resumes a training run after a power cut | Section 6 |
| Suspend | Disabled | Open bug with kernel 7.0 and RTX 50 cards on resume | Section 15 |
| Updates | Security updates install by themselves, never an automatic reboot; kernel and NVIDIA packages only by hand, between runs | A driver update during a series breaks new CUDA processes until a reboot | Sections 14 and 23 |
| NVIDIA driver | 580, open kernel modules, precompiled and signed by Canonical | NVIDIA's long-term branch, until June 2028; RTX 50 cards need the open modules; no key to enroll | Section 18 |
| Clock | Ubuntu keeps the hardware clock in local time | Mexico City has had no daylight saving time since 2022, which is where this mode causes trouble | Section 12 |
| Fast Startup | Off | Shutting Windows down must really shut it down | Section 3 |
| Secure Boot variables (db, KEK, dbx) and the 2023 certificates | Changed only by Windows Update; Ubuntu only reads them (secureboot-db masked, fwupd's UEFI items declined) | Windows handles BitLocker during those updates | Section 16 |

## Part A. Windows: inventory and preparation

### 1. What you need

- A USB stick of 8 GB or more. Writing the image erases it.
- The Ubuntu SSD, an M.2 2280 NVMe drive. The install erases it: if it was used
  before, copy anything it holds that is still needed, from any PC.
- The BitLocker recovery key of each encrypted Windows volume, readable from
  another device: on paper, or through https://aka.ms/myrecoverykey when it is
  saved in a Microsoft account, as Windows' device encryption does. Sections 3
  and 7 check that they are the right ones.
- A network connection: a cable, or a Wi-Fi network and its password.
- The board manual, for the M.2 slots and their heatsinks.
- The monitor and keyboard you normally use, and an afternoon.

**Check:** you can read the recovery keys on a device other than this PC, or
there are none because Windows is not encrypted, which section 2 confirms.

### 2. Inventory from Windows (read-only)

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

# Volumes and how full they are
Get-Volume | Format-Table DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining -AutoSize

# The name Linux gives each NVMe disk in /dev/disk/by-id (meaningful for NVMe disks only)
Get-PhysicalDisk | Format-Table DeviceId, FriendlyName, BusType, Size, @{Label='Linux name'; Expression={'nvme-eui.' + ("$($_.SerialNumber)".ToLower() -replace '[_.\s]', '')}} -AutoSize
```

For an NVMe disk, Windows often shows as serial number a namespace identifier,
not the controller's serial number: 32 hexadecimal digits in groups of four,
with a final dot, such as `1A2B_3C4D_…_9E8F.`; Kingston drives start theirs with
sixteen zeros. Linux shows the same identifier in a `nvme-eui.<identifier>`
link: Windows' value in lowercase, without its underscores and final dot, all
its digits (32 on these drives). The last command prints that name for each
NVMe disk, and section 9 checks it. Note it for the Windows disk
(`<windows-eui>`) and for the data disk (`<data-eui>`).

BitLocker:

```powershell
# Encryption and protection state of every volume
manage-bde -status

# Key protectors of C: and the TPM's "PCR Validation Profile".
# This also PRINTS THE RECOVERY PASSWORD: never paste its output anywhere public.
manage-bde -protectors -get C:
```

`PCR Validation Profile: 7, 11` means BitLocker relies on the Secure Boot
measurement; it is the profile Windows sealed here when it encrypted itself with
Secure Boot on. `0, 2, 4, 11` means it measures the firmware, the cards' option
ROMs and the boot code directly. Section 3 lists the events that matter either
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
| Windows disk: model, size, disk number, Linux name (`<windows-eui>`) | |
| Its EFI system partition: partition number and size | |
| Windows data disk, if there is one: model, size, disk number, drive letter, Linux name (`<data-eui>`) | |
| The Ubuntu SSD, if it is already in the PC: model, size, what its volumes hold | |
| BitLocker, per volume: conversion status and protection status; for C:, the PCR Validation Profile and the recovery key ID | |
| Secure Boot: on or off; `Microsoft Corporation UEFI CA 2011` in db; which 2023 certificates | |
| Fast Startup | |
| Firmware version | |

**Check:** the table is complete. **STOP** if *BIOS Mode* is not UEFI, or if
`Microsoft Corporation UEFI CA 2011` is not in db: Ubuntu 24.04's installer and
boot loader are signed through that certificate and do not start with Secure
Boot on. If Secure Boot is off and `Get-SecureBootUEFI` finds no db at all (an
error ending in `0xC0000100`), the firmware has no keys yet, as on this machine:
section 6 installs them, and section 7 repeats this check.

### 3. Prepare Windows

#### Confirm the recovery keys

Skip this part if `manage-bde -status` showed no encrypted volume.

In the output of `manage-bde -protectors -get C:`, the *Numerical Password*
protector has an ID like `{1A2B3C4D-…}`. The recovery screen asks for the key
whose ID starts with the same eight characters. Find that ID in your saved keys:
paper, file, or https://aka.ms/myrecoverykey, which lists each key with its ID
and drive. Do the same for the data disk, with `manage-bde -protectors -get`
and its letter. With device encryption, Windows 11 saves the keys in the
Microsoft account used at the first sign-in. If you have no copy, make one
before going on, never on the Windows disks themselves: *Back up your recovery
key*, in *Manage BitLocker* in the Control Panel or in *Settings → Privacy &
security → Device encryption*.

#### Turn off Fast Startup

With Fast Startup on, *Shut down* hibernates the Windows kernel session instead
of ending it. This guide starts other systems between Windows sessions, and
Ubuntu can open the data disk, so Windows must really shut down.

Control Panel → *Hardware and Sound* → *Power Options* → *Choose what the power
buttons do* → *Change settings that are currently unavailable* → clear *Turn on
fast startup (recommended)* → *Save changes*.

```powershell
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled   # now 0
```

If the value is still 1, or the checkbox is missing, set the same registry value
that the checkbox controls, from PowerShell as administrator, and read it again:

```powershell
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled   # now 0
```

#### Device encryption: Windows can encrypt itself

Microsoft's BitLocker overview: "If a device doesn't initially qualify for
device encryption, but then a change is made that causes the device to qualify
(for example, by turning on Secure Boot), device encryption enables BitLocker
automatically". It covers the system drive and the fixed data drives, and saves
the recovery keys in the Microsoft account.

On this machine Secure Boot was off, with no keys installed. After section 6
turned it on, Windows began encrypting C: and the data disk by itself, without
asking (XTS-AES 128, used space only). This guide follows that path: section 7
waits for the encryption to finish, then suspends protection.

To keep Windows unencrypted instead, set the registry value Microsoft documents,
before section 6. Leaving Windows unencrypted is a decision of its own, and the
BitLocker steps of sections 7 and 20 then do not apply. In PowerShell as
administrator, read-only first:

```powershell
Test-Path 'HKLM:\SYSTEM\CurrentControlSet\Control\BitLocker'    # True
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\BitLocker' -Name PreventDeviceEncryption -ErrorAction SilentlyContinue   # nothing yet
```

If `Test-Path` printed False, create the key first with
`New-Item 'HKLM:\SYSTEM\CurrentControlSet\Control\BitLocker'`. Never add
`-Force` to it: on an existing key it can replace the key with an empty one.
Then:

```powershell
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\BitLocker' -Name PreventDeviceEncryption -Type DWord -Value 1
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\BitLocker' -Name PreventDeviceEncryption   # PreventDeviceEncryption : 1
```

#### Suspend BitLocker

Only if `manage-bde -status` shows C: encrypted: *Fully Encrypted* (in Spanish,
*Cifrado completo*), or *Encryption in Progress* (*Cifrado en progreso*). In the
second case, wait until it reads *Fully Encrypted* and find its keys as section
7 describes, then suspend here, before section 6. If Windows is not encrypted
at all, section 7 does this once Windows has encrypted itself.

Microsoft lists, among the events that put a BitLocker volume into recovery:
firmware upgrades, changes to the boot manager, changes to the measurements
(PCRs) BitLocker checks, and turning off or clearing the TPM. With the profile
`0, 2, 4, 11`, changing a GPU or its firmware counts too, because PCR 2
measures the cards' option ROMs. The firmware settings of section 6, the disks
moved in section 8 and the new boot entry of section 10 are planned changes of
that kind. Microsoft's answer for planned changes is to suspend protection
first:

```powershell
manage-bde -protectors -disable C: -RebootCount 0   # 0 = suspended until you turn it back on
manage-bde -status C:                               # Protection Status: Protection Off
```

Only C: needs it: Windows unlocks the data disk by itself once C: is unlocked
(among its protectors, an *External Key*, required for automatic unlocking).
The volume stays encrypted, but while protection is suspended its key is kept
on the disk in the clear: anyone holding the disk could read it. Section 20
turns protection back on. Do not leave it suspended.

**Check:** `HiberbootEnabled` is 0; you hold the recovery key of each encrypted
volume, with matching IDs; if C: was encrypted, it now shows *Protection Off*;
if you chose to keep Windows unencrypted, `PreventDeviceEncryption` is 1.

### 4. Download and verify the image

From https://releases.ubuntu.com/noble/ download into one folder:

- `ubuntu-24.04.5.1-desktop-amd64.iso`
- `SHA256SUMS`
- `SHA256SUMS.gpg`

A browser may save `SHA256SUMS` as `SHA256SUMS.txt`: the content is the same,
so use the name on disk in the commands below.

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
service host. The commands are the same in PowerShell, each on one line:

```bash
gpg --keyid-format long --keyserver hkp://keyserver.ubuntu.com --recv-keys 0x46181433FBB75451 0xD94AA3F0EFE21092
gpg --keyid-format long --list-keys --with-fingerprint 0x46181433FBB75451 0xD94AA3F0EFE21092
gpg --keyid-format long --verify SHA256SUMS.gpg SHA256SUMS
```

If the first command hangs or fails, the network blocks the keyserver's port:
use `hkps://` instead of `hkp://`.

The fingerprints must be exactly:

```text
C598 6B4F 1257 FFA8 6632  CBA7 4618 1433 FBB7 5451
8439 38DF 228D 22F7 B374  2BC0 D94A A3F0 EFE2 1092
```

**Check:** `$actual -eq $expected` prints `True`, and gpg reports
`Good signature from "Ubuntu CD Image Automatic Signing Key (2012) <cdimage@ubuntu.com>"`
with one of those fingerprints. A warning that the key "is not certified with a
trusted signature" is expected; a fingerprint mismatch or `BAD signature` is
not: delete the files and download them again.

### 5. Write the USB stick with Rufus

Get Rufus only from https://rufus.ie or https://github.com/pbatard/rufus/releases,
and prefer the portable build (`rufus-<version>p.exe`). Check its signature
before running it:

```powershell
Get-AuthenticodeSignature .\rufus-<version>p.exe | Format-List Status, SignerCertificate
```

`Status` must be `Valid` and the signer Akeo Consulting (older releases: "Pete
Batard - Open Source Developer"). Any other signer, or none: delete the file.

Unplug every other USB storage device, so the stick is the only drive Rufus can
offer. Then:

1. **Device:** the stick; its size must match.
2. **Boot selection:** *Disk or ISO image* → **SELECT** → the verified ISO.
3. **Partition scheme:** GPT. **Target system:** UEFI (non CSM).
4. **START.** Accept the download of additional files if asked. When Rufus
   reports an ISOHybrid image, keep **Write in ISO Image mode**.
5. Confirm the warning only if the device is the stick.

**Check:** Rufus reports *READY*.

## Part B. Firmware and hardware

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
| Boot > Fast Boot | Disabled | ASRock: with Fast Boot "you won't be able to boot from an USB storage device", and the installer, like any rescue system, starts from a USB stick |
| Advanced > ACPI Configuration > Restore on AC/Power Loss | Power Off | Nothing resumes a training run after a power cut. ASRock's guide documents only Power On and Power Off |
| Advanced > Onboard Devices Configuration > Display Priority | External Graphic, unless the current value already shows the firmware screens on your monitor | The monitor is on the RTX 5080: firmware screens and the boot menu must appear there |
| Advanced > CPU Configuration > AMD fTPM Switch | Unchanged (AMD CPU fTPM) | BitLocker's key is sealed in the TPM |
| H/W Monitor | Curves for the CPU and case fans | The cooling that protects the hardware lives in the firmware (section 21) |

Secure Boot keys:

- If msinfo32 showed *Secure Boot State: On*, only read *Security > Secure
  Boot*. Do not change *Secure Boot Mode*, and do not use *Install Default
  Secure Boot Keys* or *Clear Secure Boot Keys*: factory keys can lack
  certificates that Windows Update has added since, and once Windows' own boot
  manager is signed with a 2023 certificate, Windows would no longer start.
- If Secure Boot was off but keys are installed, set *Secure Boot* to Enabled.
- If no keys are installed (Windows found no db in section 2), as on this
  machine, in this order: *CSM* Disabled, *Secure Boot Mode* Standard, *Install
  Default Secure Boot Keys*, *Secure Boot* Enabled, then save with F10. Section
  7 starts Windows and checks the result. If Windows refuses to start, set
  *Secure Boot* back to Disabled: Windows starts as before, and the case needs
  its own decision before going on.

After saving, the first start can stay black for a minute or more while the
board retrains its memory: wait before touching anything. If no picture appears
on the RTX 5080's monitor, plug the monitor into the board's own HDMI port,
which the CPU's graphics drive. As a last resort, turn the PC off, unplug the
power supply, press the *Clear CMOS* button on the rear panel, and apply this
section again: that button restores the factory settings.

If the firmware ever offers to reset or clear the fTPM, for example after a CPU
or firmware change, decline: clearing the TPM is one of Microsoft's recovery
triggers, and a cleared TPM no longer holds BitLocker's key.

If the stick is refused with a message such as *Secure Boot Violation* or
*Invalid signature*, the firmware's db lacks
`Microsoft Corporation UEFI CA 2011`; section 2 should have caught it.
Canonical states that existing Ubuntu installation media require that
certificate, and the installed boot loader is signed through it too. The fix,
with BitLocker suspended if Windows is encrypted: if the factory keys include
it, *Install Default Secure Boot Keys* restores it; check again from Windows
afterwards, and let Windows Update add the 2023 certificates back (section 16).
Running with Secure Boot off is a new decision with its own record, not a quiet
change.

**Check:** with the stick inserted, the boot menu (F11) lists it as a UEFI
device, and Windows still starts from *Windows Boot Manager*.

### 7. Back in Windows: encryption, keys and suspension

Start Windows from the boot menu (F11 → *Windows Boot Manager*). In PowerShell
as administrator, read-only first:

```powershell
Confirm-SecureBootUEFI     # True
manage-bde -status         # each volume: Conversion Status, Percentage Encrypted, Protection Status
```

Repeat the Secure Boot commands of section 2 as well:
`Microsoft Corporation UEFI CA 2011` must now be in db; if it is not, see the
last paragraphs of section 6 before going on. Then, by what
`manage-bde -status` shows:

- **C: suspended in section 3** (*Fully Encrypted*, *Protection Off*): go on to
  section 8.
- **Every volume Fully Decrypted**, with `PreventDeviceEncryption` set to 1 in
  section 3: Windows stays unencrypted; go on to section 8.
- **Encryption in Progress** (in Spanish, *Cifrado en progreso*) on C: or on
  the data disk: device encryption started by itself, as section 3 describes.
  This was the case here. Leave Windows running, and do not start the firmware
  setup or the stick, until every encrypted volume reads *Fully Encrypted*. With
  used space only, it can still take hours.

Once it has finished:

```powershell
manage-bde -status     # C: and the data disk: Fully Encrypted
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-BitLocker/BitLocker Management'; Id=892,897} | Format-List TimeCreated, Id, Message
```

On this machine Windows logged event 897 when it backed up a volume's recovery
information to the Microsoft account, with its *Protector GUID*: the first eight
characters are the key ID that https://aka.ms/myrecoverykey shows. Find both
keys there, from another device. Event 892 listed the PCRs the key was sealed
to, `[7,11]`, with Secure Boot as their source. If `Get-WinEvent` finds no
events, look the keys up by the IDs that `manage-bde -protectors -get` prints
for each volume.

Then suspend protection of C:, for the reasons of section 3:

```powershell
manage-bde -protectors -disable C: -RebootCount 0
manage-bde -status C:     # Protection Status: Protection Off
```

**Check:** Secure Boot is on; every volume is either *Fully Encrypted*, with its
recovery key found from another device, or unencrypted on purpose; if C: is
encrypted, it shows *Protection Off*.

### 8. Put the Ubuntu SSD in M2_1

M2_1 is the slot for the Ubuntu SSD
([ADR-010](../adr/ADR-010-the-ubuntu-ssd-goes-inside-the-workstation.md)). It is
wired to the CPU (PCIe 5.0 x4), and ASRock's specifications call it "the first
priority for M.2 installation". M2_2 to M2_4 hang off the chipset (PCIe 4.0 x4).
A PCIe 4.0 SSD links at Gen4 x4 in any of them; in M2_1 its reads do not share
the chipset's link to the CPU with USB, SATA and the network.

If M2_1 already holds a disk, as the Windows data disk did here, that disk moves
to M2_2, M2_3 or M2_4. Windows recognizes a disk by its own identifiers, not by
its slot: a moved data disk keeps its drive letter and its automatic unlock. The
Windows disk stays where it is.

1. Note which slot each GPU is in and which power cables it uses, in case one
   has to come out to reach a slot: they go back the same way.
2. Shut Windows down, switch the power supply off and unplug it.
3. Install the disks, following the board manual for each slot's heatsink and
   latch. If a heatsink's thermal pad still has its protective film, remove it.
4. If a GPU came out, put it back with its cables. Push the RTX 5080's 12V-2x6
   power plug fully home, until its latch clicks: a plug left partly seated can
   overheat.
5. Power on and start Windows from the boot menu (F11 → *Windows Boot Manager*).
   If Windows offers to initialize or format the new disk, cancel. In
   PowerShell as administrator:

```powershell
Get-PhysicalDisk | Format-Table DeviceId, FriendlyName, BusType, Size, @{Label='Linux name'; Expression={'nvme-eui.' + ("$($_.SerialNumber)".ToLower() -replace '[_.\s]', '')}} -AutoSize
manage-bde -status     # the data disk: Unlocked, as before; C: still Protection Off
```

Note the Ubuntu SSD's Linux name (`<ubuntu-eui>`) next to the others. If an old
volume on it got a drive letter, Windows can read it: copy now anything still
needed, because section 10 erases it.

**Check:** Windows lists the Ubuntu SSD with the other NVMe disks; the data disk
opens without asking for a key; C: still shows *Protection Off*, or Windows is
unencrypted on purpose.

## Part C. Live session: look before writing

Nothing in this part writes to any disk: the live system runs from the stick.

GRUB menus, on the stick and later on the SSD, read the keyboard as US English
whatever your layout: on a Latin American keyboard, the key to the right of `0`
types `-` (with Shift, `_`), and the next key types `=`. It matters only when
*If something goes wrong* asks you to type in one.

### 9. Identify the devices and fingerprint the Windows disks

1. Put the stick in a USB port on the board's rear panel, not on the front panel
   or a hub. The installer reads from the stick until the end, and a stick that
   drops for a moment comes back under another name and makes the install fail
   (*If something goes wrong*, section 10).
2. Power on, press F11 and choose the stick's UEFI entry.
3. In the stick's menu, choose the default entry (*Try or Install Ubuntu* on
   24.04 media). If the screen stays black, restart and choose the entry with
   *safe graphics* in its name.
4. The installer opens. Language: your choice; English is recommended, because
   every screen and every command's output then match this guide (the desktop
   can switch to Spanish later, in *Settings*). Accessibility: your options.
   Keyboard: your keyboard's own layout, for example *Spanish (Latin
   American)*; with the wrong layout, typed commands come out wrong. On
   *Internet connection* choose *Use wired connection*, or *Connect to a Wi-Fi
   network* and your network; on *Try or install Ubuntu* choose *Try Ubuntu
   24.04.5 LTS* (the release number may read slightly differently). The live
   desktop appears.
5. Open a terminal (Ctrl+Alt+T). Do not open the Windows disks in *Files*:
   nothing in this guide needs them.

```bash
# Every block device with its model, transport, file system and partition type (read-only)
lsblk -o NAME,SIZE,MODEL,TRAN,FSTYPE,PARTTYPENAME,MOUNTPOINTS

# The NVMe identifiers, and the name each one points to in this boot
ls -l /dev/disk/by-id/ | grep nvme-eui | grep -v -- '-part'
```

What to expect on this machine:

- **Windows disk** (WD_BLACK SN850X, 931.5G): partitions *EFI System* (200M,
  vfat), *Microsoft reserved*, *Microsoft basic data* with FSTYPE `BitLocker`,
  and *Windows recovery environment*.
- **Windows data disk** (KINGSTON SKC3000S1024G, 953.9G): *Microsoft reserved*
  and *Microsoft basic data* (`BitLocker`).
- **Ubuntu SSD** (KINGSTON SFYRD2000G, 1.8T): whatever it held. If it held a
  Windows volume, it shows *Microsoft* partitions too: go by model, size and
  identifier, never by partition types.
- **The stick:** `TRAN` usb, one partition mounted at `/cdrom`.

In a narrow terminal `lsblk` cuts the MODEL column short (`KINGSTO`): the sizes
and the identifiers tell the two Kingston disks apart.

Set one variable per disk, with the identifiers of sections 2 and 8, and check
that each one resolves. The variables live only in this terminal: keep it open
until section 11.

```bash
W=/dev/disk/by-id/nvme-eui.<windows-eui>    # the Windows disk
E="$W-part1"                                # its EFI system partition: partition 1, or the number section 2 gave
D=/dev/disk/by-id/nvme-eui.<data-eui>       # the Windows data disk, if there is one
U=/dev/disk/by-id/nvme-eui.<ubuntu-eui>     # the Ubuntu SSD
ls -l "$W" "$E" "$D" "$U"                   # four links: ../../nvme…n1, its …p1, and two other disks
lsblk -o NAME,SIZE,MODEL,PARTTYPENAME "$W"  # the Windows disk and its partitions
```

Without a data disk, leave out the `D=` line, `"$D"` in the `ls -l` line, and
the lines marked "if there is one". *No such file or directory* means a
mistyped identifier.

**STOP.** Go on only when `W`, `D` and `U` point to three different disks, each
disk's model and size match sections 2 and 8, and the partition that `E` points
to is the one `lsblk` lists as *EFI System* on the Windows disk.

Fingerprint the Windows disks. These commands only read them; the files live in
the live session's memory until you restart. Windows writes to its EFI
partition each time it starts, so these fingerprints compare only within this
live session: after a restart, take them again.

```bash
sudo sfdisk --dump "$W" > ~/win-gpt-before.txt           # its partition table
sudo sha256sum "$E" > ~/win-esp-before.sha256             # every byte of its EFI system partition
sudo sfdisk --dump "$D" > ~/win-data-gpt-before.txt      # if there is one: its partition table
cat ~/win-*-before.*
```

**Check:** each identifier resolves to the right disk, the fingerprint files are
written, and this terminal stays open. Do not restart until section 11 has
compared them.

## Part D. Install

### 10. Run the installer

If the SSD's old volume shows as mounted (in the dock or in *Files*), unmount it
first with its eject icon. Then start the installer from the live desktop (its
*Install Ubuntu* icon). The labels below come from the 24.04 installer, in
English; check them on screen.

1. **Language, accessibility, keyboard:** as in section 9.
2. **Internet connection:** as in section 9.
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
   which can be a Windows disk. Select the Ubuntu SSD: the name that
   `ls -l "$U"` pointed to, with its model and size. *The entire disk will be
   used:* then lists its current partitions; if they include *Microsoft
   reserved* or NTFS ones, judge by name, size and model, not by partition
   types.
   **STOP:** the drive shown is the Ubuntu SSD.
9. **Create your account:** your name, your computer's name, your username and
   a password; keep *Require my password to log in*.
10. **Select your timezone:** Mexico City.
11. **Review your choices**, on the page titled *Ready to install*. Under
    *General*: *Disk setup* reads *Erase disk and install Ubuntu*, and
    *Installation disk* the Ubuntu SSD's name. Under *Security & more*: *Disk
    encryption* and *Proprietary software* read *None*. Under *Partitions*, two
    lines, both on that disk: its partition 1 formatted as fat32, used for
    `/boot/efi`, and its partition 2 formatted as ext4, used for `/`.
    **STOP, point of no return:** *Install* erases that disk. Press it only if
    the installation disk is the Ubuntu SSD.
12. When it finishes, choose **Continue testing**, not *Restart now*: section
    11 still needs this session and its terminal.

**Check:** the installer reports that the installation finished, and you are
back on the live desktop.

### 11. Before restarting: check what changed

In the terminal of section 9:

```bash
# 1. The Windows disks' partition tables and EFI partition are exactly as they were
sudo sfdisk --dump "$W" | diff ~/win-gpt-before.txt - && echo "Windows partition table unchanged"
sudo sha256sum "$E" | diff ~/win-esp-before.sha256 - && echo "Windows EFI partition unchanged"
sudo sfdisk --dump "$D" | diff ~/win-data-gpt-before.txt - && echo "Windows data disk unchanged"   # if there is one

# 2. The SSD now holds an EFI system partition and an ext4 root
lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME,MOUNTPOINTS "$U"

# 3. The firmware's new "ubuntu" entry points to the SSD's EFI partition
sudo efibootmgr -v
lsblk -o NAME,PARTUUID "$U"     # the EFI partition's PARTUUID appears in the ubuntu entry
```

**Check:** every "unchanged" line prints; the SSD has an *EFI System* partition
of about 1 GiB and an ext4 partition filling the rest; the `ubuntu` entry
carries the PARTUUID of the SSD's EFI partition.

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
found Windows; an arrow key stops its countdown. **Do not start Windows from
this menu**; section 13 explains why and removes the entry.

Log in and open a terminal. Read-only checks:

```bash
grep PRETTY_NAME /etc/os-release                      # Ubuntu 24.04.5 LTS
uname -r                                              # 7.0.0-…-generic: the HWE kernel
[ -d /sys/firmware/efi ] && echo UEFI || echo Legacy  # UEFI
mokutil --sb-state                                    # SecureBoot enabled
readlink -f /dev/disk/by-id/nvme-eui.<ubuntu-eui>     # the Ubuntu SSD's name in this boot, for example /dev/nvme2n1
findmnt -n -o SOURCE,FSTYPE /                         # that name with p2, ext4
findmnt -n -o SOURCE /boot/efi                        # that name with p1: never a Windows disk
findmnt --fstab -o SOURCE,TARGET,FSTYPE               # / and /boot/efi listed by /dev/disk/by-uuid/…
swapon --show                                         # /swap.img
sudo ls /boot/efi/EFI/BOOT /boot/efi/EFI/ubuntu       # EFI/BOOT: BOOTX64.EFI and fbx64.efi (the fallback path); EFI/ubuntu: shimx64.efi, grubx64.efi, BOOTX64.CSV
ip -br addr                                           # the interface in use, wired (enp…) or Wi-Fi (wlp…): UP, with an address
ping -c 3 archive.ubuntu.com                          # network and name resolution
timedatectl                                           # Time zone: America/Mexico_City
```

About the network: the board's wired chip, a Realtek RTL8126 (5 GbE), has a
Linux driver since kernel 6.9. This HWE kernel includes it and 24.04's GA
kernel (6.8) does not: do not switch to the GA kernel. On the first run the
wired port reported DOWN and the machine used Wi-Fi. With a cable plugged in,
the wired interface should come up; if it does not, see *If something goes
wrong*.

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

**Check:** every line matches its comment; root and `/boot/efi` are on the
Ubuntu SSD; *RTC in local TZ* reads yes.

### 13. Keep Ubuntu away from the Windows disks

#### No Windows entry in GRUB

Starting *Windows Boot Manager* from GRUB runs Windows after shim and GRUB: with
BitLocker on, it measures a different boot chain and asks for the recovery key,
and Windows would depend on Ubuntu's boot loader. Windows starts from the
firmware boot menu instead (F11 → *Windows Boot Manager*). Turning off
os-prober also stops `update-grub` from probing the Windows disks.

`/boot/grub/grub.cfg` is readable only by root: every `grep` of it needs `sudo`,
or it fails with *Permission denied*.

```bash
grep -rn OS_PROBER /etc/default/grub /etc/default/grub.d/ 2>/dev/null   # read-only: current setting
sudo grep -ci 'menuentry.*windows' /boot/grub/grub.cfg                 # read-only: 1 or more, the Windows entry
```

```bash
echo 'GRUB_DISABLE_OS_PROBER=true' | sudo tee /etc/default/grub.d/90-no-os-prober.cfg
sudo update-grub
sudo grep -ci 'menuentry.*windows' /boot/grub/grub.cfg                 # 0
```

With one system left in it, GRUB hides its menu. To reach it (recovery mode, an
older kernel), press Esc once while the machine starts.

#### The Windows disks hidden from the desktop

The *Files* app lists the Windows partitions under *Other Locations*, and one
click mounts them read-write: with your password for an unencrypted volume, or
with its recovery key for a BitLocker one. Nothing in this guide needs them. A
udev rule tells the desktop's disk service (udisks) to ignore a disk and its
partitions, by the disk's serial number.

The Windows disk is always hidden. The data disk is hidden too, unless Ubuntu
needs files from it: on this machine it stays visible, for the files it shares
with Windows.

Read-only first, the Windows disk as udev sees it:

```bash
udevadm info --query=property --name=/dev/disk/by-id/nvme-eui.<windows-eui> | grep -E '^ID_(MODEL|SERIAL_SHORT)='
```

`ID_MODEL` must be the Windows disk's model. The rule is written from the
serial number read in place, and only if it is not empty:

```bash
S=$(udevadm info --query=property --name=/dev/disk/by-id/nvme-eui.<windows-eui> | sed -n 's/^ID_SERIAL_SHORT=//p')
echo "$S"     # the Windows disk's serial number: not empty
[ -n "$S" ] && printf 'ENV{ID_SERIAL_SHORT}=="%s", ENV{UDISKS_IGNORE}="1"\n' "$S" | sudo tee /etc/udev/rules.d/99-hide-windows-disks.rules
```

To hide the data disk as well, repeat that block with `<data-eui>`, and with
`sudo tee -a` in place of `sudo tee`, which would replace the file.

The rule applies from the next start. After restarting:

```bash
udevadm info --query=property --name=/dev/disk/by-id/nvme-eui.<windows-eui> | grep UDISKS_IGNORE         # UDISKS_IGNORE=1
udevadm info --query=property --name=/dev/disk/by-id/nvme-eui.<windows-eui>-part1 | grep UDISKS_IGNORE   # its partitions too
```

To see a disk again in *Files*, remove its line from that file and restart.

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

The kernel and the NVIDIA driver change only by hand, between runs (section 23).
A driver update applied while CUDA work runs leaves new processes and
`nvidia-smi` failing until the next reboot. Exclude them from unattended
upgrades:

```bash
sudo tee /etc/apt/apt.conf.d/51unattended-upgrades-workstation >/dev/null <<'EOF'
// GPU workstation: the kernel and the NVIDIA driver change only by hand,
// between runs (install-ubuntu-gpu-workstation.md, "Maintenance between runs").
// Each entry is a Python regular expression matched from the start of a
// package name: "linux-" covers kernels, their NVIDIA modules and firmware.
// secureboot-db writes the firmware's Secure Boot variables, which on this
// dual-boot machine only Windows changes.
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

If an update ever asks on which EFI system partitions to install GRUB, select
only the line that shows `/boot/efi`: the Ubuntu SSD's, about 1 GiB, with the
SSD's model. Never select one of about 200 MB with no path after its size: that
is the Windows disk's, and GRUB would be written onto the Windows disk.

**Check:** `apt-config dump` lists the five entries, and the dry run ends
without errors.

### 15. No suspend, and what systemd-oomd does

Suspend stays off on this machine: kernel 7.0 with NVIDIA's open driver hangs
when an RTX 50 card resumes from suspend (Launchpad bug 2149963: confirmed, no
fix as of October 2026).

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
candidate. It stays enabled; the stress tests and the soak test of
[validate-gpu-workstation.md](validate-gpu-workstation.md) check whether it
acted, and this is where to see it:

```bash
oomctl                                      # what it watches and the current pressure
journalctl -u systemd-oomd --since today    # every kill is logged here
```

**Check:** the four targets are `masked`.

### 16. Secure Boot certificates on a dual-boot machine

Microsoft's 2011 UEFI certificates expired in June 2026 (the KEK on 24 June, the
third-party UEFI CA on 27 June), and *Windows Production PCA 2011* expired on
19 October 2026. Machines keep starting; new boot components are signed with
the 2023 certificates, which have to be in the firmware's db and KEK.
Canonical's rotation post (references) explains what it means for Ubuntu.

On this machine **only Windows changes the firmware's Secure Boot variables**
(db, KEK and the revocation list, dbx), and Windows Update handles BitLocker
while doing so. The same changes made from Ubuntu alter what BitLocker measures
outside Windows, and can end on the recovery screen.

Ubuntu Desktop installs one service that writes them by itself: secureboot-db
runs at every start and adds the revocations it ships to dbx. Its first runs
happened before BitLocker was back on, so they are harmless; from now on it
stays off:

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
your exact kernel. That path works with one more step. Choose a password of 8
to 16 characters, lowercase letters and digits only: the blue screen where you
type it again reads the keyboard as US English, like GRUB. At the next start
that blue MOK management screen counts down from 10 seconds: press a key before
it ends, then choose *Enroll MOK* → *Continue* → *Yes*, type the password, and
reboot. If you miss it, the key is not enrolled and the driver does not load:
run `sudo update-secureboot-policy --enroll-key`, choose the password again, and
restart. The full upgrade of section 14 usually avoids all this, because the
precompiled modules are published for the current kernel.

Before restarting, see which path was taken:

```bash
dpkg -l | grep -E '^ii +(linux-modules-nvidia|nvidia-dkms)'   # expected: linux-modules-nvidia-580-open-…, and no nvidia-dkms
sudo reboot
```

If the desktop does not appear after the restart, or the login screen returns
after you log in, see *If something goes wrong*. After the restart:

```bash
cat /proc/driver/nvidia/version     # NVIDIA UNIX Open Kernel Module for x86_64  580.…
modinfo -F license nvidia           # Dual MIT/GPL: the open modules
modinfo -F signer nvidia            # not empty: the module is signed
modinfo -n nvidia                   # its file: …/kernel/nvidia-580-open/nvidia.ko, not under …/updates/dkms/
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
so the guides select GPUs by UUID: write down `<uuid-5080>` and `<uuid-4070>`
in your private note. The validation guide also writes them into its own
`env.sh` (its section 6), so that its commands carry none.

With the monitor on the RTX 5080, the desktop uses part of its memory. Note
`memory.used` on each GPU at idle, with nothing else running: that is what the
desktop takes. On the first run it was about 340 MiB on the RTX 5080 and 15 MiB
on the RTX 4070.

**Check:** two GPUs of about 16 and 12 GB, the same driver version, the UUIDs
written down, the idle memory noted.

## Part G. Boot validation

### 20. Boot order, Windows from the boot menu, BitLocker back on

#### Ubuntu by default

1. Run `systemctl poweroff`, wait until the PC is off, power on and touch
   nothing: Ubuntu starts.
2. In Ubuntu:

```bash
sudo efibootmgr                                 # BootOrder, then one line per entry: Boot0001* ubuntu, Boot0000* Windows Boot Manager, …
nvidia-smi -L                                   # two GPUs
ip -br addr && ping -c 3 archive.ubuntu.com     # network
findmnt -n -o SOURCE /                          # the Ubuntu SSD
```

If Windows started instead, or `BootOrder` does not start with `ubuntu`'s
number, set the order: every number of `BootOrder`, with `ubuntu`'s first and
the rest in their current order:

```bash
sudo efibootmgr -o XXXX,YYYY,…    # XXXX = ubuntu
sudo efibootmgr                   # BootOrder now starts with XXXX
```

If `ubuntu` is ever missing from the boot menu, for example after a firmware
update, choose the SSD's own entry, shown with its model: its fallback loader
recreates the `ubuntu` entry and starts Ubuntu.

**Check:** a cold start lands in Ubuntu, with both GPUs and the network.

#### Windows from the boot menu, and BitLocker back on

Skip the BitLocker commands if Windows is not encrypted.

1. Restart, press F11 and choose *Windows Boot Manager*. Windows starts with no
   recovery screen.
2. As administrator:

```powershell
manage-bde -protectors -enable C:
manage-bde -status                 # C: Protection On; the data disk Unlocked
manage-bde -protectors -get C:     # the PCR Validation Profile: 7, 11 here (this prints the recovery password)
```

3. Restart Windows through F11 → *Windows Boot Manager*.

**Check:** no recovery screen, and the data disk opens without a key. If a
recovery screen appears, now or at a later start, type the key, and note what
changed before it.

From here on BitLocker protects the disk again. Firmware updates, Secure Boot
changes and starting Windows from GRUB would all ask for the key; section 23
says when to suspend it.

Every restart of Windows now lands in Ubuntu, including the restarts Windows
Update needs to finish: when Windows restarts, press F11 and choose *Windows
Boot Manager*.

## Part H. After the install

### 21. Sensors, fans and lighting (optional)

The fan curves that protect the hardware live in the firmware (*H/W Monitor*,
section 6). Linux reads the sensors. Each GPU's fans follow the NVIDIA firmware
and driver automatically; nothing is set here.

```bash
sudo apt install lm-sensors
sensors                      # k10temp: Tctl, Tccd1, Tccd2 (CPU); nvme: Composite, one per SSD
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

### 22. SSH

Only once the machine works locally, that is, after section 20 passed. Ubuntu
Desktop does not install an SSH server.

```bash
sudo apt install openssh-server
systemctl status ssh.socket --no-pager     # active (listening): sshd starts at the first connection
sudo systemctl start ssh                   # starts it now, so that sshd -T works below
ssh-import-id gh:<github-user>             # your public keys from GitHub into ~/.ssh/authorized_keys
for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done   # this machine's host key fingerprints
```

Write the fingerprints, with their types, in your private note: a computer
connecting for the first time compares one of them. From another computer,
`ssh <user>@<lan-ip>` must log in with the key; how to give a computer its key,
and what the first connection asks, is in
[appendix A of the server guide](install-ubuntu-server.md#appendix-a-connect-from-another-computer).

Then refuse passwords. Until `sshd` has started since the machine booted,
`sshd -T` and `sshd -t` stop with *Missing privilege separation directory:
/run/sshd*: that directory appears when it starts and goes when it stops, hence
the `systemctl start` above. Read-only first: for each setting `sshd` keeps the
first value it reads, and it reads the files in `/etc/ssh/sshd_config.d/` in
name order:

```bash
sudo sshd -T | grep -i '^passwordauthentication'    # effective value
ls /etc/ssh/sshd_config.d/
```

```bash
echo 'PasswordAuthentication no' | sudo tee /etc/ssh/sshd_config.d/00-local.conf
sudo sshd -t && sudo systemctl restart ssh
sudo sshd -T | grep -i '^passwordauthentication'    # passwordauthentication no
```

From the other computer:

```bash
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password <user>@<lan-ip>
# expected: Permission denied (publickey)
```

The first option keeps your key out of the attempt and the second asks for a
password: the workstation must refuse before any password prompt. If it asks
for one, do not type it; press Ctrl+C and look at the effective value again.
Once the computer has a short name for the workstation (`workstation`, Tailscale
guide, section 6), the same test is
`ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password workstation`.

Access from outside the house comes with Tailscale, in its own guide.

**Check:** login with the key works, and login with a password is refused.

### 23. Maintenance between runs

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
nvidia-smi -L                                       # both GPUs
cd ~/bench/nnunet && uv run python check_gpus.py    # both compute (created by section 6 of the validation guide)
```

If an NVIDIA package was upgraded and the machine was not restarted,
`nvidia-smi` and new CUDA programs fail with *Failed to initialize NVML:
Driver/library version mismatch*: the new libraries do not match the kernel
module still loaded. A restart fixes it, and it is the reason these updates
wait for the gap between runs.

If a new kernel misbehaves, press Esc while the machine starts, choose *Advanced
options for Ubuntu*, and start the previous kernel.

Firmware (BIOS) updates:

1. If Windows is encrypted, in Windows:
   `manage-bde -protectors -disable C: -RebootCount 0`. ASRock notes that a
   BIOS update can bring up the BitLocker recovery screen.
2. Update with *Instant Flash*, then apply section 6 again: an update can reset
   settings, boot entries and the Secure Boot keys. The Ubuntu SSD still starts
   through its fallback loader if its entry is gone (section 20).
3. Start Windows from the boot menu; if it is encrypted, run
   `manage-bde -protectors -enable C:` and restart once.

**Check:** after each round of maintenance, both GPUs are listed, the GPU check
passes, and, if Windows is encrypted, BitLocker protection is on.

## If something goes wrong

The install never writes to the Windows disks. Before *Install* in section 10,
only Windows' own files and settings, the firmware, the stick and the slot of
the data disk change. Find what you see below and do what the last column says. If
that does not fix it, stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 4 | The hash or the signature does not match | Delete the three files and download them again. Never write a stick from an image that failed either check. |
| 4 | `gpg --recv-keys` hangs or fails | Use `hkps://` instead of `hkp://`: the network blocks the keyserver's port. |
| 6 | After saving, the screen stays black | Wait a minute or more: the board can be retraining its memory. Then try the board's HDMI port, and last, the Clear CMOS button (section 6). |
| 6 | Windows does not start after enabling Secure Boot | Set *Secure Boot* back to Disabled: Windows starts as before. |
| 6, 9 | The stick is missing from the F11 menu | Check that *Fast Boot* and *CSM* are Disabled, try another rear USB port, or write the stick again (section 5). |
| 6, 9 | *Secure Boot Violation* or *Invalid signature* when starting the stick | The firmware's db lacks Microsoft's 2011 UEFI CA: last paragraphs of section 6. |
| 7, 8 | Windows shows the BitLocker recovery screen | From another device, open https://aka.ms/myrecoverykey and type the key whose ID the screen shows. Once in Windows, suspend protection (section 3) before the next change. |
| 8 | After the move, the data disk asks for its key | Unlock it once with its recovery key, then, in PowerShell as administrator, `manage-bde -autounlock -enable D:` with its letter. |
| 9 | A black screen after choosing *Try or Install Ubuntu* | Restart and choose the entry with *safe graphics* in its name. |
| 9 | The live system stops at a text prompt because it cannot find its medium | Write the stick again, choosing Rufus's *DD Image* mode. |
| 9 | `ls -l` prints *No such file or directory* for an identifier | Compare it with Windows' value: lowercase, no underscores, no final dot, all its digits. `ls -l /dev/disk/by-id/` lists every link; a disk whose Windows serial number is not a namespace identifier has a `nvme-<model>_<serial>` link instead. |
| 10 | The installer says the SSD is in use | Unmount the SSD's old volume in *Files* (its eject icon), then go back one screen. |
| 10 | The installer fails, and `/var/log/installer/subiquity-server-debug.log` shows *Failed to use fsimage '///cdrom/casper/minimal.en.squashfs' doesn't exist or is invalid* | The stick dropped for a moment and came back under another name (`sda` became `sdb`), and the live system lost its files. Turn the PC off, put the stick in a rear USB port of the board, and repeat from section 9: the Windows disks were not written, and the SSD is erased again. |
| 10 | The installer crashes or freezes, the power fails, or *Restart now* was pressed | The Windows disks were not written, but the fingerprints of section 9 are lost. Start Windows from F11 to confirm that it works, then repeat from section 9: the new install replaces the broken one and its boot entry. |
| 11 | A Windows fingerprint differs | **STOP**, as section 11 says. |
| 12 | A black screen at the first start | Restart; in the GRUB menu (Esc while the PC starts, if it does not show) press `e` on the Ubuntu entry, add a space and `nomodeset` at the end of the line that starts with `linux`, and press Ctrl+X. Add it at each start until section 18 installs the driver. |
| 12 | A `grub>` prompt instead of the menu | Type `normal` and press Enter. |
| 12 | An `(initramfs)` prompt that asks for a manual check | Type `fsck -y` and the device it names, then `exit`. |
| 12 | No network, or the wired interface DOWN with a cable plugged in | Check the cable and the other end, and that `uname -r` shows the 7.0 kernel. `nmcli device` should list the wired interface; if it does not, `sudo dmesg` should mention its driver, `r8169`. Wi-Fi works meanwhile. |
| 13 | `grep` on `/boot/grub/grub.cfg` prints *Permission denied* | The file is readable only by root: put `sudo` in front, as section 13 does. |
| 14, 23 | An update asks where to install GRUB | Select only the line that shows `/boot/efi` (the Ubuntu SSD's EFI partition, about 1 GiB), never one of about 200 MB (the Windows disk's). |
| 17, 19 | Only one GPU | **STOP**: its seating and its power cables. |
| 18 | The desktop does not appear after the driver, or the login screen returns | Restart, press Esc while the PC starts to show the GRUB menu, press `e` on the Ubuntu entry and add `module_blacklist=nvidia,nvidia_drm,nvidia_modeset,nvidia_uvm`: Ubuntu starts with the basic display driver. **STOP** and keep the output of `journalctl -b -1 -p err`. To return to the state before the driver: `sudo apt purge '?installed ?name(^nvidia-)' '?installed ?name(^libnvidia-)' '?installed ?name(^linux-modules-nvidia-)' '?installed ?name(^xserver-xorg-video-nvidia-)'`, then restart. If apt's list of packages to remove names `linux-firmware`, `linux-image` or `linux-generic`, answer n. |
| 18 | The blue MOK screen went by without a key press | `sudo update-secureboot-policy --enroll-key`, choose the password again, restart, and press a key when the blue screen appears. |
| 20 | *Windows Boot Manager* is missing from the F11 menu | Choose the entry with the Windows disk's model: the firmware starts Windows' own fallback loader. |
| 20 | Windows offers to format a disk | Always *Cancel*: it is the Ubuntu SSD, which Windows cannot read. |
| 20 | A Windows restart lands in Ubuntu | Restart and choose *Windows Boot Manager* in the F11 menu. |
| 22 | `sshd -T` or `sshd -t` prints *Missing privilege separation directory: /run/sshd* | `sshd` has not started since the machine booted: `sudo systemctl start ssh`, then repeat the command. |

### Going back to Windows only

At any point, Windows can be the default system again: in the firmware, put
*Windows Boot Manager* first in the boot order and save with F10. Windows then
starts by itself, with its disks as they were, and Ubuntu only from F11. The
settings of sections 3 and 6 can stay.

To remove Ubuntu as well, delete its firmware entry from Windows. In an
administrator PowerShell, list the entries with `bcdedit /enum firmware` and
delete only the one whose description is `ubuntu`, with
`bcdedit /delete '<identifier>'`: paste the identifier exactly as bcdedit prints
it, braces included, inside the single quotes, which PowerShell needs around
braces. Never delete `{bootmgr}`. To reuse the SSD in Windows, format only the
disk with the SSD's model and size.

## Next

- **Before it trains for real:**
  [validate-gpu-workstation.md](validate-gpu-workstation.md): stability, the
  SSD, power limits, nnU-Net benchmarks and a soak test.
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

- *BitLocker overview* (device encryption, and `PreventDeviceEncryption`):
  https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/
- *BitLocker recovery overview*:
  https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/recovery-overview
- *BitLocker FAQ*:
  https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/faq
- `manage-bde -protectors`:
  https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/manage-bde-protectors
- `manage-bde -autounlock`:
  https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/manage-bde-autounlock
- Windows Secure Boot certificate expiration (KB5062710):
  https://support.microsoft.com/help/5062710

NVIDIA:

- Open kernel modules (R580 README):
  https://download.nvidia.com/XFree86/Linux-x86_64/580.95.05/README/kernel_open.html
- Driver branches and their support periods:
  https://docs.nvidia.com/datacenter/tesla/drivers/supported-drivers-and-cuda-toolkit-versions.html
- `nvidia-smi`: https://docs.nvidia.com/deploy/nvidia-smi/index.html
- CUDA environment variables:
  https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html

Linux:

- Kernel parameters (`module_blacklist=`, `nomodeset`):
  https://docs.kernel.org/admin-guide/kernel-parameters.html
- `timedatectl`: https://www.freedesktop.org/software/systemd/man/latest/timedatectl.html
- `oomd.conf` (systemd-oomd):
  https://www.freedesktop.org/software/systemd/man/latest/oomd.conf.html
- Hardware monitoring drivers: https://docs.kernel.org/hwmon/nct6775.html,
  https://docs.kernel.org/hwmon/nct6683.html and
  https://docs.kernel.org/hwmon/k10temp.html

Hardware:

- ASRock X870E Taichi Lite, specifications (M.2 slots, and M2_1 as "the first
  priority for M.2 installation"):
  https://www.asrock.com/mb/AMD/X870E%20Taichi%20Lite/index.asp
- ASRock X870E Taichi Lite, user manual:
  https://download.asrock.com/Manual/X870E%20Taichi%20Lite.pdf
- ASRock, *AMD 800 Series Motherboard Software/BIOS Setup Guide*:
  https://download.asrock.com/Manual/Software/AMD%20X870/Software_BIOS%20Setup%20Guide_English.pdf
- Rufus: https://rufus.ie and https://github.com/pbatard/rufus/releases
