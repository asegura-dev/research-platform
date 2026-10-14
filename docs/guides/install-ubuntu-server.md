# Install Ubuntu Server on a single-OS host

> **Scope:** single-OS service hosts only. Do not use this guide on a
> machine that keeps Windows or another operating system, such as the
> dual-boot GPU workstation, which gets
> [its own guide](install-ubuntu-gpu-workstation.md). Step 6 erases a
> whole disk, step 10 enables automatic reboots, and BitLocker, dual boot
> and GPU drivers are not covered here.

> **Status:** written from official documentation on 2026-10-09; not yet run
> end to end. After its first complete run on real hardware, this line
> records the date and the versions it was verified with.

This guide installs Ubuntu Server as the only operating system on a machine
that runs always-on services (in this platform: the mini PC that hosts
Forgejo, the CI runner, ntfy and the experiment tracker).

Every step ends with a check. Every destructive step is preceded by
read-only commands, and nothing destructive runs until those checks match
what you expect.

Placeholders used throughout:

- `<release>`: the Ubuntu release, `24.04` in this platform.
- `<iso>`: the server image file name, `ubuntu-24.04.5-live-server-amd64.iso`
  (24.04.5 is the final planned point release of 24.04).
- `<hostname>`, `<user>`, `<github-user>`, `<lan-ip>`.

Never commit real hostnames, addresses, topics or tokens to this repository.

## Decisions this guide depends on

Each one has its decision record; the guide assumes the values in the second
column.

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| Ubuntu release | 24.04 LTS on every machine; revisit at 26.04.2 or after the critical experiments | One set of guides and scripts; a mature userland while the thesis runs | [ADR-001](../adr/ADR-001-ubuntu-24-04-lts-on-every-host.md) |
| Image | Ubuntu Server (not Desktop) | No GUI on a headless host; the GA kernel by default | [ADR-002](../adr/ADR-002-ubuntu-server-not-desktop-on-every-host.md) |
| Secure Boot | Enabled, with the 2023 Microsoft certificates applied (step 8) | The 2011 CA expired in June 2026, so new shims will be signed with the 2023 CA | [ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md) |
| Disk encryption | No LUKS passphrase | A passphrase prompt at boot blocks unattended restarts after a power cut | [ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md) |
| LVM allocation | Root volume uses the whole volume group | The guided layout may leave part of the disk unallocated | [ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md) |
| Automatic reboots | Allowed at a fixed hour on service hosts only | Kernel security fixes need a reboot; the workstation must never reboot during a training run | [ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md) |

## 0. Before you wipe anything

### 0a. Decide whether you need to reinstall

If the machine already runs the chosen release and you know its history,
you may not need this guide. Run these read-only commands and keep the
output:

```bash
cat /etc/os-release                                   # current release
[ -d /sys/firmware/efi ] && echo UEFI || echo Legacy  # boot mode
lsblk -f                                              # disks, partitions, filesystems
sudo vgs 2>/dev/null                                  # LVM volume groups and free space
mokutil --sb-state                                    # Secure Boot state (apt install mokutil if missing)
systemctl list-units --type=service --state=running   # what runs today
```

Reinstall if any of these is true: the boot mode is Legacy, it is a Desktop
install you do not need, the disk layout is not the one you decided, or you
cannot account for what is installed.

**Check:** anything on this disk that you want to keep is copied to another
machine. Reinstalling erases the whole disk.

### 0b. Update the Secure Boot certificates while the old system still boots

Microsoft's 2011 UEFI certificate expired in June 2026, so new shims will be
signed with the 2023 certificate; as of October 2026 none has been published
for 24.04 yet. Canonical warns that installation media released later may
require it, while existing media, 24.04.5 and 26.04.1 included, still use the
2011 certificate. If the machine currently runs Ubuntu, apply the certificate
update now, from the system you are about to replace; then any installer
boots with Secure Boot on.

Read-only first:

```bash
mokutil --db  | grep 'Subject:'    # certificates trusted to boot
mokutil --kek | grep 'Subject:'    # certificates trusted to update db
fwupdmgr --version                 # org.freedesktop.fwupd must be 2.0.0 or later
```

If `Microsoft UEFI CA 2023` is already listed in `db`, skip to step 1.
Otherwise:

```bash
sudo fwupdmgr refresh
sudo fwupdmgr update
```

Follow the prompts and reboot if asked. The update arrives as separate
items (Windows Production PCA, UEFI CA, KEK CA and UEFI dbx); availability
varies by vendor and some devices get only part of it.

**Check:** `mokutil --db | grep 'Subject:'` lists `Microsoft UEFI CA 2023`.
If no update is offered, note it: step 5 covers what to do if the installer
is then refused by Secure Boot.

## 1. What you need

- A USB stick larger than the ISO file. Writing the image erases the stick.
- A second computer to download, verify and write the image.
- A monitor and a keyboard for the target machine, attached until step 11
  passes. They are your way back in if SSH is not working yet.
- The keys that open the firmware setup and the one-time boot menu of the
  target machine (vendor-specific; often Del, F2, F7, F11 or F12).
- An Ethernet cable. This guide assumes a wired connection.
- An SSH key on your laptop whose public half is on GitHub. The installer
  imports it, so the first login is key-only. If you do not have one, on the
  laptop (PowerShell or a Linux shell):

  ```bash
  ssh-keygen -t ed25519
  ```

  Add the contents of `~/.ssh/id_ed25519.pub` in GitHub under Settings →
  SSH and GPG keys.

**Check:** `https://github.com/<github-user>.keys` shows your public key,
and `ssh-keygen -lf ~/.ssh/id_ed25519.pub` gives you the fingerprint you
will compare in step 6.

## 2. Download the image and its checksums

From `https://releases.ubuntu.com/<release>/` download three files into the
same folder:

- `<iso>`, the latest point release of the server image
- `SHA256SUMS`
- `SHA256SUMS.gpg`

For 24.04.5, only the Desktop image was rebuilt (as 24.04.5.1); the server
image is still `ubuntu-24.04.5-live-server-amd64.iso`.

**Check:** the three files are in the same folder and the ISO name matches
a line in `SHA256SUMS`.

## 3. Verify the download

Two checks: the checksum file is signed by Ubuntu, and the ISO matches the
checksum file.

### On Ubuntu (preferred: gpg is installed and the keys usually are too)

```bash
gpg --keyid-format long --verify SHA256SUMS.gpg SHA256SUMS
```

If it says `No public key`, fetch the Ubuntu CD image keys and retry:

```bash
gpg --keyid-format long --keyserver hkp://keyserver.ubuntu.com \
    --recv-keys 0x46181433FBB75451 0xD94AA3F0EFE21092
gpg --keyid-format long --list-keys --with-fingerprint \
    0x46181433FBB75451 0xD94AA3F0EFE21092
```

The fingerprints must be exactly:

```
C598 6B4F 1257 FFA8 6632  CBA7 4618 1433 FBB7 5451
8439 38DF 228D 22F7 B374  2BC0 D94A A3F0 EFE2 1092
```

Then verify the ISO against the signed checksum file:

```bash
sha256sum -c SHA256SUMS 2>&1 | grep OK
```

**Check:** `gpg` reports `Good signature from "Ubuntu CD Image Automatic
Signing Key (2012) <cdimage@ubuntu.com>"` and `sha256sum` prints `OK` next
to the ISO. A warning that the key "is not certified with a trusted
signature" is expected; a fingerprint mismatch or `BAD signature` is not.
If anything fails, delete the files and download again.

### On Windows

PowerShell computes the hash without extra software:

```powershell
Get-FileHash -Algorithm SHA256 .\<iso>
```

Compare it with the line for that ISO in `SHA256SUMS`. Rufus can also show
the checksum of the selected ISO (the tick-mark button next to the image
selector). To verify the signature on Windows, install Gpg4win and run the
same `gpg` commands as above; without it you have only checked integrity,
not authenticity.

**Check:** the hash matches character by character.

## 4. Write the USB stick

### On Windows with Rufus (the tool Ubuntu's own tutorial uses)

#### Get Rufus and verify it

Rufus is free and open source (GPLv3). Copies circulate on unofficial
download sites, so get it only from its official sources:

- https://rufus.ie
- https://github.com/pbatard/rufus/releases

Prefer the portable build (`rufus-<version>p.exe`): it runs without
installation. Before running it, check its digital signature (read-only):

```powershell
Get-AuthenticodeSignature .\rufus-<version>p.exe | Format-List Status, SignerCertificate
```

**Check:** `Status` is `Valid` and the signer is Akeo Consulting, the
developer's company (some older releases were signed as "Pete Batard -
Open Source Developer"). Rufus needs administrator rights, so Windows
shows a UAC prompt; it should name the same verified publisher. Any other
signer, or no signature at all: delete the file.

#### Write the stick

Read-only first: unplug every other USB storage device so the stick is the
only removable drive, and note its size.

1. Insert the stick and launch Rufus.
2. **Device:** select the stick. Confirm the size matches the stick, not
   another drive.
3. **Boot selection:** *Disk or ISO image* → **SELECT** → the verified ISO.
4. **Partition scheme:** GPT. **Target system:** UEFI (non CSM).
5. **START.** If Rufus asks to download additional files, accept. When it
   reports an ISOHybrid image, keep **Write in ISO Image mode** and confirm.
6. Rufus warns that everything on the device will be destroyed. Confirm only
   if the device is the stick.

**Check:** Rufus reports *READY* with no errors.

### On Ubuntu with `dd`

`dd` writes to whatever device you name, including your system disk. Run
the read-only check first and identify the stick by size, model and
transport (`usb`):

```bash
lsblk -d -o NAME,SIZE,MODEL,TRAN
```

Only after the stick is unambiguously identified (for example `/dev/sdX`),
unmount its partitions and write:

```bash
sudo umount /dev/sdX?* 2>/dev/null
sudo dd if=<iso> of=/dev/sdX bs=4M status=progress oflag=sync
```

**Check:** `dd` ends without errors and `lsblk -f` shows the stick with the
installer's filesystem label.

These commands were written against GNU coreutils (Ubuntu 24.04 and
earlier). Ubuntu 26.04 replaces most core utilities with a Rust
reimplementation; if you write the stick from a 26.04 machine and `dd`
rejects an option, use Rufus instead.

## 5. Prepare the firmware of the target machine

Menu names vary by vendor; look for the equivalent option.

| Setting | Value | Why |
|---|---|---|
| Boot mode | UEFI; disable CSM or Legacy if present | GPT disk, modern boot path |
| Secure Boot | Enabled | Ubuntu boots with Secure Boot through its signed shim |
| Restore on AC power loss (also "AC back", "After power failure") | Power on | The host must come back alone after a power cut |
| Boot order | USB first for the install, or use the one-time boot menu key | Boot the installer |
| Firmware "fast boot" | Disable if the USB stick is not detected | Some firmwares skip USB initialization |

If the installer is refused with a message such as "Secure Boot Violation"
or "Invalid signature", the firmware does not trust the certificate that
signed the installer. In order of preference: apply step 0b from a running
Linux system, install the vendor's latest firmware, or disable Secure Boot
for the install, apply step 8 afterwards and re-enable it. If the firmware
never accepts the 2023 certificate, running with Secure Boot disabled is a
new decision record that supersedes that part of
[ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md), not something
to leave undocumented.

**Check:** with the stick inserted, the one-time boot menu lists it as a
UEFI device, and the installer menu appears.

## 6. Install

Boot from the stick and choose *Try or Install Ubuntu Server*.

1. **Language and keyboard:** your choices.
2. **Type of install:** *Ubuntu Server* (not minimized).
3. **Network:** the wired interface should get an address by DHCP. Write
   down `<lan-ip>`; you need it for the first SSH login.
4. **Proxy and mirror:** leave the defaults unless your network requires a
   proxy.
5. **Storage:**
   - *Use an entire disk*. Read-only check on this screen: pick the internal
     disk by size and model, never the USB stick.
   - Keep *Set up this disk as an LVM group*.
   - Leave *Encrypt the LVM group with LUKS* unchecked (see the decisions
     table).
   - On the summary screen, look at the size of `ubuntu-lv` against the
     volume group. Several reports show the guided layout leaving part of a
     large disk unallocated. If it does, edit `ubuntu-lv` and set it to the
     maximum, or fix it after install (step 9).
   - Confirming this screen erases the disk. Last read-only check: the
     selected device is the one you intend to wipe.
6. **Profile:** your name, `<hostname>`, `<user>` and a strong password
   (you need it for `sudo`).
7. **Ubuntu Pro:** skip for now.
8. **SSH:** check *Install OpenSSH server*. Choose *Import SSH key → from
   GitHub* and enter `<github-user>`; confirm the fingerprint shown matches
   the one from step 1. If the screen offers to allow password
   authentication over SSH, leave it off.
9. **Featured snaps:** select nothing. Services are installed later by
   their own guides.
10. Wait for *Install complete*, choose *Reboot now* and remove the stick
    when prompted.

**Check:** the machine boots into Ubuntu without the stick.

## 7. First login and verification

If you connected to this address before the reinstall, your laptop still
remembers the old host key and SSH will refuse the new one. Read-only
check, then remove only that entry from your own `known_hosts`:

```bash
ssh-keygen -F <lan-ip>     # shows an old entry, if any
ssh-keygen -R <lan-ip>     # removes it
```

From your laptop:

```bash
ssh <user>@<lan-ip>
```

Confirm that password login is refused (key-only):

```bash
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password <user>@<lan-ip>
# expected: Permission denied (publickey)
```

If password login is accepted, find out why before changing anything. For
each setting, `sshd` keeps the first value it reads, and another file in
`/etc/ssh/sshd_config.d/` (for example one written by the installer) may
already set it. Read-only first:

```bash
sudo sshd -T | grep -i '^passwordauthentication'   # effective value
ls /etc/ssh/sshd_config.d/                          # files read in this order
```

Then add an override whose name sorts before the others, test the
configuration and restart the daemon (open sessions stay connected):

```bash
echo 'PasswordAuthentication no' | sudo tee /etc/ssh/sshd_config.d/00-local.conf
sudo sshd -t && sudo systemctl restart ssh
```

Repeat the password test from the laptop before you close your working
session.

On the host, read-only checks:

```bash
cat /etc/os-release                                   # the release you chose
[ -d /sys/firmware/efi ] && echo UEFI || echo Legacy  # expected: UEFI
mokutil --sb-state                                    # expected: SecureBoot enabled
df -h /                                               # root size as decided
sudo vgs                                              # VFree as decided
timedatectl                                           # time zone and NTP sync
grep -n RECORDFAIL /etc/default/grub || echo "not set: default applies"
```

About the last line: if a boot is interrupted (for example by a power cut),
GRUB records the failure and shows its menu on the next boot. Ubuntu
changed the default wait for that case from "forever" to 30 seconds so
headless servers come back on their own. If someone set
`GRUB_RECORDFAIL_TIMEOUT=-1`, remove it and run `sudo update-grub`.

Set the time zone if needed (example value):

```bash
sudo timedatectl set-timezone America/Mexico_City
```

**Check:** every line above matches the decisions table.

## 8. Secure Boot certificates on the new system

Do this even if you did step 0b, and before enabling automatic reboots.
Canonical warns that installations without the 2023 certificate stop
receiving shim security fixes, and that from Q4 2026 updates to stable
releases may require it, with package management failures if it is
missing.

Read-only first:

```bash
fwupdmgr --version                 # org.freedesktop.fwupd must be 2.0.0 or later
mokutil --db  | grep 'Subject:'
mokutil --kek | grep 'Subject:'
```

The rollout is complete when these appear:

```
Subject: C=US, O=Microsoft Corporation, CN=Microsoft UEFI CA 2023
Subject: C=US, O=Microsoft Corporation, CN=Microsoft Option ROM UEFI CA 2023
Subject: C=US, O=Microsoft Corporation, CN=Microsoft Corporation KEK 2K CA 2023
```

If any is missing:

```bash
sudo fwupdmgr refresh
sudo fwupdmgr update
```

**Check:** the subjects above are listed after the reboot fwupd asks for.
If your vendor offers no update, record which certificates are present in a
new decision record, and decide there whether to keep Secure Boot on
(it would supersede that part of
[ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md)).

## 9. Fix the LVM allocation (only if step 6 left space unallocated)

Read-only first:

```bash
sudo vgs
sudo lvs
```

If `VFree` is larger than you decided to keep, extend the root volume and
its filesystem:

```bash
sudo lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
```

**Check:** `df -h /` shows the new size and `sudo vgs` shows the free space
you intended.

## 10. Updates and the automatic reboot policy

Bring the system up to date and reboot once:

```bash
sudo apt update && sudo apt full-upgrade
sudo reboot
```

`unattended-upgrades` installs security updates automatically, but by
default it does not reboot when an update (a kernel, for instance) needs
it. On a service host this platform allows a reboot at a fixed hour. Read
first:

```bash
systemctl status unattended-upgrades --no-pager
dpkg -s update-notifier-common >/dev/null && echo installed || echo missing
```

Automatic reboots need `update-notifier-common`; install it if it is
missing. Then put the policy in its own file instead of editing the
packaged `50unattended-upgrades`:

```bash
sudo tee /etc/apt/apt.conf.d/52unattended-upgrades-local >/dev/null <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
```

The workstation does not get this file: a training run must never be cut
by an automatic reboot. Its reboots are manual, between runs.

**Check:** `sudo unattended-upgrades --dry-run --debug` runs without
errors, and the log under `/var/log/unattended-upgrades/` shows activity
after a day.

## 11. The power-cut test

This is the test that proves the host is ready to be left alone. Do it now,
before any service holds data.

1. With the host running, cut the power at the wall (not the power button).
2. Restore power and do not touch the machine.
3. From your laptop, wait for SSH to answer again.

**Check:** the host powers on by itself, boots without a keyboard and
answers SSH within a few minutes. If it does not power on, revisit the
"Restore on AC power loss" setting; if it stops at the GRUB menu, revisit
the `RECORDFAIL` check in step 7. Once it passes, the monitor and keyboard
can go.

## Next

In order: Tailscale (remote access without open ports), Docker, ntfy,
healthchecks (the host heartbeat), Forgejo and its runner, and the
experiment tracker. Each has its own guide.

## References

- Ubuntu tutorial, *How to verify your Ubuntu download*:
  https://ubuntu.com/tutorials/how-to-verify-ubuntu
- Ubuntu Desktop documentation, *Create a bootable USB stick* (Rufus, `dd`,
  balenaEtcher):
  https://documentation.ubuntu.com/desktop/en/latest/how-to/create-a-bootable-usb-stick
- Ubuntu tutorial, *Create a bootable USB stick with Rufus on Windows*:
  https://ubuntu.com/tutorials/create-a-usb-stick-on-windows
- Rufus, official site and releases: https://rufus.ie and
  https://github.com/pbatard/rufus/releases
- Canonical, *Microsoft UEFI CA rotation: What it means for Ubuntu users
  and vendors*:
  https://discourse.ubuntu.com/t/microsoft-uefi-ca-rotation-what-it-means-for-ubuntu-users-and-vendors/82652
- GRUB recordfail default changed to 30 seconds (Launchpad bug 1443735):
  https://lists.snapcraft.io/archives/foundations-bugs/2015-June/243953.html
- Ubuntu community wiki, *AutomaticSecurityUpdates*:
  https://help.ubuntu.com/community/AutomaticSecurityUpdates
