# Install Ubuntu Server on a single-OS host

> **Scope:** single-OS service hosts only. Do not use this guide on a
> machine that keeps Windows or another operating system, such as the
> dual-boot GPU workstation, which gets
> [its own guide](install-ubuntu-gpu-workstation.md). Step 6 erases a
> whole disk, step 10 enables automatic reboots, and BitLocker, dual boot
> and GPU drivers are not covered here.

> **Status:** run end to end once, in October 2026, on the service host: steps 1
> to 11, and the power-cut test passed, with the host powering on and starting
> by itself as soon as power returned. The host runs on Wi-Fi. Its firmware
> holds no Secure Boot keys, and the factory keys it offers stop at a test
> platform key and the 2011 certificates, so the host runs without Secure Boot
> ([ADR-011](../adr/ADR-011-the-service-host-runs-without-secure-boot.md)). The
> time zone of step 7d and the volume of step 9 were skipped and set on
> 2026-10-25, and a typo in step 10's file stopped apt until that day. Revised
> from that run on 2026-10-23 and 2026-10-25: SSH from the start (steps 7 and
> 12, appendices A and B), the firmware without keys (step 8), and checks that
> catch each of those misses.

This guide installs Ubuntu Server as the only operating system on a machine
that runs always-on services (in this platform: the mini PC that hosts
Forgejo, the CI runner, ntfy and the experiment tracker).

After the install, the machine is used from another computer, over SSH. If you
have never used SSH, read step 7 slowly: it shows what you will see and what
each answer means. Appendix B lists the commands you will use most.

Every step ends with a check. Every destructive step is preceded by
read-only commands, and nothing destructive runs until those checks match
what you expect.

Placeholders used throughout:

- `<release>`: the Ubuntu release, `24.04` in this platform.
- `<iso>`: the server image file name, `ubuntu-24.04.5-live-server-amd64.iso`
  (24.04.5 is the final planned point release of 24.04).
- `<hostname>`, `<user>`, `<github-user>`, `<lan-ip>`.
- `server`: the short name your computers use for this host (step 12b); any
  name works.

Replace each placeholder, angle brackets included, with its value.

Never commit real hostnames, addresses, fingerprints, topics or tokens to this
repository. They go in your private note.

## Decisions this guide depends on

Each one has its decision record; the guide assumes the values in the second
column.

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| Ubuntu release | 24.04 LTS on every machine; revisit at 26.04.2 or after the critical experiments | One set of guides and scripts; a mature userland while the thesis runs | [ADR-001](../adr/ADR-001-ubuntu-24-04-lts-on-every-host.md) |
| Image | Ubuntu Server (not Desktop) | No GUI on a headless host; the GA kernel by default | [ADR-002](../adr/ADR-002-ubuntu-server-not-desktop-on-every-host.md) |
| Remote access | OpenSSH, keys only, imported from GitHub | No password to guess or steal; each computer gets in with its own key (appendix A) | [ADR-002](../adr/ADR-002-ubuntu-server-not-desktop-on-every-host.md) |
| Secure Boot | Enabled, with the 2023 Microsoft certificates applied (step 8); the current service host runs without it | The 2011 CA expired in June 2026, so new shims will be signed with the 2023 CA | [ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md), [ADR-011](../adr/ADR-011-the-service-host-runs-without-secure-boot.md) |
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
mokutil --sb-state                            # "Platform is in Setup Mode" means no keys at all (step 8)
mokutil --db  | grep -E 'Subject:|is empty'   # certificates trusted to boot
mokutil --kek | grep -E 'Subject:|is empty'   # certificates trusted to update db
dpkg-query -W fwupd                           # fwupd must be 2.0.8 or later (step 8)
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
- An Ethernet cable. This guide assumes a wired connection. Wi-Fi, which the
  installer also sets up, works too, but then the host depends on the
  network's name and password: a new password or a new router means going
  back to it with a monitor and a keyboard, unless its wired port is ready as
  well (step 12f).
- A computer to work from, Windows or Linux, with an SSH key whose public half
  is in your GitHub account: appendix A, steps A.1 and A.2. The installer
  imports it, so the first login is key-only.

**Check:** `https://github.com/<github-user>.keys` shows your public key,
and `ssh-keygen -lf $HOME/.ssh/id_ed25519.pub` on that computer gives you the
fingerprint you will compare in step 6.

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
   (you need it for `sudo`, and to log in at the server's own screen).
7. **Ubuntu Pro:** skip for now.
8. **SSH:** check *Install OpenSSH server*. Choose *Import SSH key → from
   GitHub* and enter `<github-user>`; confirm the fingerprint shown matches
   the one from step 1. If the screen offers to allow password
   authentication over SSH, leave it off. Every key in that GitHub account
   opens the server: keep there only the keys of computers you use
   (appendix A).
9. **Featured snaps:** select nothing. Services are installed later by
   their own guides.
10. Wait for *Install complete*, choose *Reboot now* and remove the stick
    when prompted.

**Check:** the machine boots into Ubuntu without the stick.

## 7. First login over SSH

From now on the server is used from your computer. You type in a terminal on
your computer, and SSH runs each command on the server and shows its output.
Two keys protect the connection: the server proves which machine it is with
its *host key*, and you prove who you are with your own key, imported in
step 6. No password travels.

### 7a. At the server's screen: its address and its fingerprints

Log in at the server's own screen as `<user>`, with the password from step 6,
and read its address and its host key fingerprints:

```bash
ip -br addr show scope global                                       # the wired interface, UP, and <lan-ip>/24
for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done  # one line per key type: ECDSA, ED25519, RSA
```

`<lan-ip>` is the address before the slash. Each fingerprint is the text that
starts with `SHA256:`, and the type is at the end of its line. Write the
address and the three fingerprints, with their types, in your private note:
they are how a computer connecting for the first time knows that it reached
this server and not another machine at the same address. Then log out with
`exit`.

In your router, reserve that address for the server (the option is usually
called *DHCP reservation*, *address reservation* or *static lease*), so that
it does not change when the router restarts. The router asks for the MAC
address of the wired interface: `ip -br link` prints it next to the
interface's name.

**Check:** your note has `<lan-ip>` and the fingerprints, and the router lists
the reservation.

### 7b. From your computer: the first connection

Open a terminal on your computer: *Terminal* on Ubuntu; *Terminal* or
PowerShell on Windows, whose SSH client is part of Windows 10 and 11
(`ssh -V` prints its version).

If you connected to this address before a reinstall, your computer remembers
the old host key and SSH will refuse the new one. Read-only check:

```bash
ssh-keygen -F <lan-ip>     # shows an old entry, if any
```

Only if it shows one, remove that entry from your own `known_hosts`:

```bash
ssh-keygen -R <lan-ip>
```

Connect:

```bash
ssh <user>@<lan-ip>
```

The first time, SSH shows the fingerprint that the server presents and asks
whether to trust it:

```text
The authenticity of host '<lan-ip> (<lan-ip>)' can't be established.
ED25519 key fingerprint is SHA256:….
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

The line before the question names the key type: `ED25519` on current clients,
`ECDSA` on older ones such as Windows 10's. Paste the fingerprint of that type
from your note as the answer, and SSH compares the two for you. If they match,
it records the server in `~/.ssh/known_hosts` and goes on; from then on it
checks the server by itself at every connection. If SSH answers
`Please type 'yes', 'no' or the fingerprint:`, they do not match: check that you
pasted the fingerprint of the type it named; if it still does not match, answer
`no`, and find out why before going on. If the question offers only
`(yes/no)`, the client is too old to compare for you: compare the two by eye,
and type `yes` only if they are identical.

If your key has a passphrase, SSH asks for it next: that is your key's
passphrase (appendix A.1), not the server's password. Then the prompt
changes to the server's:

```text
<user>@<hostname>:~$
```

What to know from here:

- **The prompt tells you where you are.** While it shows `<user>@<hostname>`,
  every command runs on the server. On your own computer the prompt is
  different (PowerShell's starts with `PS C:\`).
- **`exit`** (or Ctrl+D) closes the session and takes you back to your
  computer. A restart of the server closes it too: connect again a minute or
  two later.
- **`sudo` asks for your password and shows nothing while you type it,** not
  even asterisks. Type it and press Enter.
- **Pasting:** Ctrl+Shift+V in Ubuntu's terminal; Ctrl+V or a right click on
  Windows. A pasted block may appear highlighted and wait: press Enter to run
  it. Some terminals instead run each line as it arrives, and then a question
  in the middle of the block (`sudo`'s password, apt's `[Y/n]`) takes the lines
  that follow it as its answer. So run `sudo -v` alone, and type the password,
  before pasting a block that has `sudo` after its first line; and run a
  command that asks a question in a block of its own.
- **If the connection drops,** the command running in it stops. Long commands
  go inside tmux (step 12c).

**Check:** SSH accepted the fingerprint from your note, and the prompt is the
server's.

### 7c. Password login is refused

From your computer (a second terminal, or after `exit`), try to log in with a
password instead of the key:

```bash
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password <user>@<lan-ip>
# expected: Permission denied (publickey)
```

If password login is accepted, find out why before changing anything. For
each setting, `sshd` keeps the first value it reads, and another file in
`/etc/ssh/sshd_config.d/` (for example one written by the installer) may
already set it. Read-only first, on the server:

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

Repeat the password test from your computer before you close your working
session.

**Check:** the password attempt ends in `Permission denied (publickey)`.

### 7d. The host as decided

On the server, read-only checks:

```bash
cat /etc/os-release                                   # the release you chose
[ -d /sys/firmware/efi ] && echo UEFI || echo Legacy  # expected: UEFI
mokutil --sb-state                                    # expected: SecureBoot enabled; "Setup Mode": step 8
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

`timedatectl` shows `Etc/UTC` unless the installer set another zone. Set
yours, because the reboot hour of step 10 is read in it (example value):

```bash
sudo timedatectl set-timezone America/Mexico_City
timedatectl | grep 'Time zone'      # America/Mexico_City (CST, -0600)
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
dpkg-query -W fwupd                           # fwupd 2.0.8 or later
mokutil --sb-state                            # SecureBoot enabled
mokutil --db  | grep -E 'Subject:|is empty'
mokutil --kek | grep -E 'Subject:|is empty'
```

If `--sb-state` adds `Platform is in Setup Mode` and the lists say `is empty`,
the firmware holds no Secure Boot keys at all: it checks nothing, and fwupd
has nothing to update. Go to *A firmware without keys*, below.

fwupd updates db and KEK from version 2.0.8, the first with the plugins that
write them; Ubuntu 24.04's updates carry a 2.0 release (2.0.20 in October
2026). If the version is older, update fwupd alone:

```bash
sudo apt update && sudo apt install fwupd
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

Follow the prompts, and restart when fwupd asks: changes to db and KEK take
effect at the next start.

**Check:** after that restart, the subjects above are listed.

### A firmware without keys

Without keys, the firmware's setup screen may still show Secure Boot as
enabled. The firmware keeps factory keys that its setup can install, with an
option such as *Restore Factory Keys* (under Security, Secure Boot or Key
Management). Read them first, read-only:

```bash
ls /sys/firmware/efi/efivars/ | grep -E '^(PK|KEK|db|dbx)(Default)?-'   # PK, KEK, db, dbx: keys in use; …Default: factory keys
for v in PKDefault KEKDefault dbDefault; do echo "== $v"; sudo grep -a -oE '[[:print:]]{8,}' "/sys/firmware/efi/efivars/$v-8be4df61-93ca-11d2-aa0d-00e098032b8c" 2>/dev/null | grep -E 'Microsoft|CA 20|DO NOT|Test|American' | sort -u; done
```

The loop prints the names of the certificates inside each factory key. With
`Microsoft Corporation UEFI CA 2011` in `dbDefault`, Ubuntu still starts once
the factory keys are installed: its loader is signed with that certificate. A
`PKDefault` whose name begins with `DO NOT TRUST` is a test key (the last
point of the next part).

What to do is a decision for its own record: install the factory keys, turn
Secure Boot on and run this step again, or run without Secure Boot, as the
current service host does
([ADR-011](../adr/ADR-011-the-service-host-runs-without-secure-boot.md)).

### If they are still missing

Read-only, and keep the output of each command. What fwupd offers for this
machine, and what it already tried:

```bash
fwupdmgr get-updates --no-unreported-check --no-metadata-check   # the options keep fwupdmgr from asking questions
fwupdmgr get-history
fwupdmgr get-devices --no-unreported-check | grep -vi serial     # one entry per certificate, named after it
```

Which firmware this is, and whose platform key (PK) it holds. The KEK can
only be replaced with a payload signed by that key's owner, the vendor:

```bash
mokutil --pk | grep -E 'Subject:|Issuer:|is empty'
sudo dmidecode -s system-manufacturer
sudo dmidecode -s system-product-name
sudo dmidecode -s bios-version
sudo dmidecode -s bios-release-date
```

How to read them:

- **`get-updates` lists certificate updates:** apply them with
  `sudo fwupdmgr update` and restart. If the subjects are still missing after
  the restart, `get-history` shows the result that fwupd recorded.
- **`get-devices` shows a certificate entry with an update error or a
  problem:** that line says why fwupd will not write it (a firmware setting,
  for example).
- **Nothing is offered:** LVFS, where fwupd gets its updates, has none that
  matches this firmware. The db updates are signed with Microsoft's 2011 KEK,
  which the firmware already holds; the KEK update has to be signed with the
  vendor's platform key. The vendor's support page may instead offer a
  firmware (BIOS) update that brings the 2023 certificates. When the
  manufacturer and product read `Default string`, the firmware does not even
  say who the vendor is.
- **The PK's subject contains `DO NOT TRUST` or `DO NOT SHIP`:** the firmware
  shipped with a test platform key (PKfail, CVE-2024-8105), whose private half
  may be known: at least one such key leaked. Secure Boot on that firmware
  protects less than it claims; note it.

Whatever the cause, record what you found in a new decision record, and
decide there among keeping Secure Boot on with the 2011 certificates only,
enrolling the 2023 certificates by hand from the firmware setup, and turning
Secure Boot off. The record supersedes that part of
[ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md). Meanwhile
the host keeps starting: Canonical states that systems with only the 2011
certificate keep working for the time being, without further shim security
updates.

## 9. Fix the LVM allocation (only if step 6 left space unallocated)

Read-only first:

```bash
sudo vgs
sudo lvs
```

On the first run, the guided layout gave the root volume 100 GB and left 374
of the 474 GB unallocated. If `VFree` is larger than you decided to keep,
extend the root volume and its filesystem, online and without losing data:

```bash
sudo lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
```

**Check:** `df -h /` shows the new size and `sudo vgs` shows the free space
you intended.

## 10. Updates and the automatic reboot policy

Bring the system up to date and reboot once. The upgrade can take several
minutes, so run it inside tmux (step 12c), where a dropped connection does not
cut it. First:

```bash
tmux new -A -s admin
```

Then, inside tmux, the upgrade, which asks before installing (answer `Y`):

```bash
sudo apt update && sudo apt full-upgrade
```

When it has finished:

```bash
sudo reboot
```

The reboot closes your session; connect again a minute or two later.

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

Check that apt reads it:

```bash
apt-config dump | grep -i automatic-reboot     # the same two lines
```

apt reads every file in `/etc/apt/apt.conf.d/`, and a typo in any of them,
even a space between the two colons, stops every apt command, automatic
updates included, with `E: Syntax error … Extra junk after value`. On the first
run, one went unnoticed until a later check.

The hour is in the server's time zone (step 7d). The workstation does not get
this file: a training run must never be cut by an automatic reboot. Its
reboots are manual, between runs.

By default, `unattended-upgrades` installs only security updates. The others,
from `noble-updates`, wait for a `sudo apt full-upgrade` by hand, now and
then; `apt list --upgradable`, after `sudo apt update`, shows them.

**Check:** `apt-config dump` prints both lines; `sudo unattended-upgrades
--dry-run --debug` runs without errors; and the log under
`/var/log/unattended-upgrades/` shows activity after a day.

## 11. The power-cut test

This is the test that proves the host is ready to be left alone. Do it now,
before any service holds data.

1. With the host running, cut the power at the wall (not the power button).
2. Restore power and do not touch the machine.
3. From your computer, wait for SSH to answer again.

**Check:** the host powers on by itself, boots without a keyboard and
answers SSH within a few minutes. If it does not power on, revisit the
"Restore on AC power loss" setting; if it stops at the GRUB menu, revisit
the `RECORDFAIL` check in step 7d. Once it passes, the monitor and keyboard
can go.

## 12. Working on the server from now on

### 12a. Where the work happens

On your computer. The server has no desktop and needs none: on it you install,
configure and read logs, over SSH, one change at a time:

1. Read the current state, with read-only commands.
2. Keep a copy of any file you are about to change:
   `sudo cp <file> <file>.bak`.
3. Make the change.
4. Test it with the program's own check, if it has one (for SSH,
   `sudo sshd -t`), and apply it.
5. Verify the result before closing the session; when the change touches SSH
   or the network, from a second connection.

Write in your private note what you changed and when. It is to the server what
the git history is to this repository.

### 12b. A short name for the server

A file named `config` in the `.ssh` folder of your home folder lets you type
`ssh server` instead of the user and the address. It belongs to the computer
you connect from, not to the server, so every computer you connect from needs
its own. These are its lines, with your values in place of `<lan-ip>` and
`<user>`:

```text
Host server
    HostName <lan-ip>
    User <user>
```

If the file already exists, add the lines at its end and keep what it has.

- **Ubuntu,** in the terminal:

  ```bash
  ls -la ~/.ssh          # read-only: whether a config is already there
  nano ~/.ssh/config     # opens it, or creates it when you save
  ```

  Paste the lines with Ctrl+Shift+V, save with Ctrl+O and Enter, and leave
  with Ctrl+X.
- **Windows,** in PowerShell, with Notepad, which saves the file as UTF-8:
  Windows PowerShell's `>` would write UTF-16, which SSH cannot read. The
  second line creates an empty file only if there is none, so that Notepad
  does not name it `config.txt`:

  ```powershell
  Get-ChildItem $HOME\.ssh      # read-only: whether a config is already there
  if (-not (Test-Path $HOME\.ssh\config)) { New-Item -ItemType File $HOME\.ssh\config }
  notepad $HOME\.ssh\config
  ```

  Paste the lines with Ctrl+V, save them with *File → Save*, and close
  Notepad.

The same command opens the file whenever it has to change, as it does in the
Tailscale guide, so that `server` also works from outside the house.

**Check:** on each computer, `ssh server` opens a session without asking for
the user or the address.

### 12c. Long commands: tmux

tmux keeps a session open on the server whether or not you are connected:

```bash
tmux new -A -s admin     # enters the session named admin, and creates it if it does not exist
```

Run the long command inside it. Ctrl+b then d leaves it running; after
connecting again, the same command, or `tmux attach -t admin`, takes you back
to it, and `exit` inside it ends it. If `tmux` answers *command not found*:
`sudo apt install tmux`.

### 12d. Copying files

From your computer, not from the server:

```bash
scp server:~/file.txt .     # from your home folder on the server to the folder you are in
scp file.txt server:~/      # from the folder you are in to your home folder on the server
```

### 12e. VS Code (optional)

VS Code's *Remote - SSH* extension opens folders and terminals on the server
from your computer, with the same `config` file and keys: run *Remote-SSH:
Connect to Host…* and choose `server`. The first time, it installs its server
component in `~/.vscode-server` on the server.

### 12f. A wired port in reserve (hosts on Wi-Fi)

A host on Wi-Fi loses its network when the Wi-Fi's password or router
changes. If its wired port is configured, a cable brings it back without a
monitor and a keyboard. Read-only first:

```bash
ip -br link                    # the wired interface's name (en…), DOWN without a cable
sudo netplan get ethernets     # null: no wired interface is configured
```

Then a file that asks for an address on that port whenever a cable is plugged
in. `<wired-if>` is the name `ip -br link` printed; `optional: true` keeps the
start from waiting for a cable that is not there:

```bash
sudo tee /etc/netplan/60-wired.yaml >/dev/null <<'EOF'
network:
  version: 2
  ethernets:
    <wired-if>:
      dhcp4: true
      optional: true
EOF
sudo chmod 600 /etc/netplan/60-wired.yaml
sudo netplan generate          # checks every netplan file: an error names the file and the line
sudo netplan get ethernets     # the port, with dhcp4: true
```

It takes effect at the next start. Applying it now (`netplan apply`) would
restart the network under the Wi-Fi session you are using. With a cable
plugged in, the host gets a second address, and the cable becomes the
preferred route.

**Check:** you can open a session by name, leave a command running in tmux
across a disconnection, and copy a file in each direction; on a host on Wi-Fi,
`netplan get ethernets` shows its wired port.

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Step | What you see | What to do |
|---|---|---|
| 7, A | `Permission denied (publickey)` | This computer's key is not on the server, or the user name is wrong. Import the key (appendix A.3); `ssh -v <user>@<lan-ip>` shows which keys SSH offered. |
| 7, A | `Please type 'yes', 'no' or the fingerprint:` after pasting a fingerprint | The pasted fingerprint is not the one the server presented. Paste the one of the type that SSH named (step 7b); if none matches, answer `no` and compare them at the server's screen (step 7a). |
| 7, A | `Host key verification failed.` | The first-connection question was answered `no`, or left empty. Connect again and answer it (step 7b). |
| 7 | `Connection timed out` or `No route to host` | The address is wrong, the server is off, or your computer is on another network. Read the address again at the server's screen (step 7a). |
| 7 | `Connection refused` | The server answers but SSH is not listening. At its screen: `systemctl status ssh.socket ssh --no-pager`. |
| 7 | `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!` | The server was reinstalled, or another machine answers at that address. Compare its fingerprints at the server's screen (step 7a); only if they are the server's new ones, `ssh-keygen -R <lan-ip>` and connect again. |
| 7 | `Enter passphrase for key` | Your key's passphrase (appendix A.1), not the server's password. |
| Any | A pasted block stops after a line with `sudo` | The password prompt took the lines that followed. Run `sudo -v` alone, then paste again. |
| Any | The terminal stops responding | The connection dropped. Close the window, or press Enter, then `~` and `.`, and connect again. Commands that must survive this go in tmux (step 12c). |
| 7, 8 | `Platform is in Setup Mode`, or `db is empty` | The firmware holds no Secure Boot keys: step 8, *A firmware without keys*. |
| 8 | The 2023 certificates are still missing after `fwupdmgr update` and a restart | Step 8, *If they are still missing*. |
| 10, any | Every apt command ends with `E: Syntax error /etc/apt/apt.conf.d/52unattended-upgrades-local:1: Extra junk after value` | A typo in the reboot policy, such as a space between the two colons. Write the file again (step 10) and check it with `apt-config dump`. |
| 11 | The host stays off when power returns | The firmware's *Restore on AC power loss* (step 5). |
| 11 | It stops at the GRUB menu | The `RECORDFAIL` check (step 7d). |
| 12 | `Could not resolve hostname server` | The short name is not in `~/.ssh/config`, or Windows saved the file as `config.txt`: `Get-ChildItem $HOME\.ssh` shows its real name. |
| 12 | `Bad configuration option`, followed by odd characters | The `config` file is not UTF-8 (it was written with PowerShell's `>`): write it again with Notepad (step 12b). |

## Next

In order: Tailscale (remote access without open ports, and this host by name
from any computer that joins it), Docker, ntfy, healthchecks (the host
heartbeat), Forgejo and its runner, and the experiment tracker. Each has its
own guide.

## Appendix A. Connect from another computer

Every computer you connect from has its own key pair. The private half never
leaves that computer; the public half goes to your GitHub account, and from
there to each host. A Windows and an Ubuntu installation on the same PC are
two computers for this purpose, each with its own key.

### A.1 Create the key

On the new computer, in a terminal (the same command in Ubuntu's terminal and
in PowerShell):

```bash
ssh-keygen -t ed25519 -C "<label>"
```

`<label>` names the computer for you, for example `workstation-ubuntu`; it
ends up in GitHub and on the hosts, never in this repository. Press Enter to
accept the file it proposes, then type a passphrase twice.

- If it says that `id_ed25519` already exists, answer `n`: this computer
  already has a key, and you use that one.
- The passphrase protects the key if the computer is stolen or its disk is
  read: without one, the file alone opens your hosts. SSH asks for it at each
  connection, unless an agent holds the key unlocked:
  - **Ubuntu:** `ssh-add` keeps it unlocked until you log out, when the
    session runs an agent (`ssh-add -l` answers without *Could not open a
    connection*).
  - **Windows:** the agent is off by default. Once, in PowerShell as
    administrator: `Get-Service ssh-agent | Set-Service -StartupType Automatic`,
    then `Start-Service ssh-agent`. Then `ssh-add` as yourself: Windows keeps
    the key for your account, across restarts, until `ssh-add -D` removes it.

`ssh-keygen` writes two files in the `.ssh` folder of your home folder:
`id_ed25519`, the private half, which you never copy or send, and
`id_ed25519.pub`, the public half. Print the public half and its fingerprint
(both commands work in PowerShell as written; there, `~` would not work with
`ssh-keygen`, which is why they use `$HOME`):

```bash
cat $HOME/.ssh/id_ed25519.pub              # one line: ssh-ed25519 AAAA… <label>
ssh-keygen -lf $HOME/.ssh/id_ed25519.pub   # 256 SHA256:… <label> (ED25519)
```

### A.2 Register it in GitHub

In GitHub, *Settings → SSH and GPG keys → New SSH key*. Title: the computer.
Key type: *Authentication Key*. Key: the whole line that `cat` printed.

**Check:** `https://github.com/<github-user>.keys` lists the new key, and
GitHub's page shows the same `SHA256:` fingerprint that `ssh-keygen -lf`
printed.

### A.3 Import it on the server

From a computer that already connects, or at the server's screen:

```bash
ssh-import-id gh:<github-user>                     # adds the keys GitHub has and the server does not
ssh-keygen -lf ~/.ssh/authorized_keys | cat -n     # read-only: every key the server accepts, numbered
```

When the workstation runs its SSH server
([its guide, section 22](install-ubuntu-gpu-workstation.md)), import the key
there too.

**Check:** the new key's fingerprint is in the list.

### A.4 Connect from the new computer

As in step 7b: `ssh <user>@<lan-ip>`, pasting from your note the server's
fingerprint of the type that SSH names. Then give the server its short name on
this computer (step 12b).

**Check:** `ssh server` opens a session from the new computer.

### A.5 Remove a computer

When a computer is retired, lost or reinstalled, remove its key everywhere:

1. In GitHub, delete it (*Settings → SSH and GPG keys*; each key shows its
   fingerprint).
2. On each host, read-only first:

   ```bash
   ssh-keygen -lf ~/.ssh/authorized_keys | cat -n     # the keys, numbered, with their fingerprints
   grep -c '' ~/.ssh/authorized_keys                  # lines in the file
   ```

   The numbers are the file's line numbers only when every line holds a key,
   which is how the installer and `ssh-import-id` write it: the second command
   must print the same count as the first lists. Then delete the line whose
   fingerprint is the retired computer's, with its number in place of `<n>`;
   `-i.bak` keeps the previous file as `authorized_keys.bak`:

   ```bash
   sed -i.bak '<n>d' ~/.ssh/authorized_keys
   ssh-keygen -lf ~/.ssh/authorized_keys | cat -n     # that fingerprint is gone; the others remain
   ```

3. Before closing that session, open a new one from a computer you keep. If
   it is refused, put the previous file back from the session that is still
   open, and look again at which line you deleted:

   ```bash
   cp ~/.ssh/authorized_keys.bak ~/.ssh/authorized_keys
   ```

   Remove one computer at a time: a second `sed -i.bak` replaces the backup of
   the first.

**Check:** your other computers still connect, and the removed computer, if
you still have it, gets `Permission denied (publickey)`.

## Appendix B. Commands you will use

Read-only commands only show something. The others change something, which is
why each comes after a read-only check.

### Keyboard

| Keys | What they do |
|---|---|
| Tab | Completes a command, file or folder name |
| ↑ and ↓ | Previous commands; `history` lists them |
| Ctrl+R | Searches the previous commands as you type |
| Ctrl+C | Stops the command that is running |
| Ctrl+D | Closes the session, like `exit` |
| q | Leaves `less`, `htop` and `man` |

### Where you are and what is there (read-only)

| Command | What it does |
|---|---|
| `pwd` | The folder you are in |
| `ls -la` | What it contains, hidden files included |
| `cd <folder>`, `cd ..`, `cd` | Enters a folder, goes up one, goes home |
| `cat <file>` | Prints a file |
| `less <file>` | Reads a long file; `/text` searches |
| `tail -n 50 <file>` | Its last 50 lines; `tail -f` keeps following it until Ctrl+C |
| `grep -i <text> <file>` | The lines that contain the text, ignoring case |
| `man <command>`, `<command> --help` | A command's manual |

### The system (read-only)

| Command | What it does |
|---|---|
| `uptime` | Time since the last start, and the load |
| `df -h` | Free space on each filesystem |
| `free -h` | Memory in use |
| `htop` | Processes, CPU and memory, live |
| `ip -br addr` | Network interfaces and their addresses |
| `systemctl status <service>` | Whether a service runs, and its last log lines |
| `systemctl --failed` | Services that failed |
| `journalctl -u <service> -n 50 --no-pager` | A service's last 50 log lines |
| `journalctl -b -p err --no-pager` | Errors since the last start |
| `apt list --upgradable` | What an upgrade would change |
| `last -n 10` | The last logins |

### Changes (most need `sudo`)

| Command | What it does |
|---|---|
| `sudo -v` | Asks for your password now, so that a pasted block is not interrupted |
| `sudo apt update` | Refreshes the list of available packages; installs nothing |
| `sudo apt full-upgrade` | Installs the updates |
| `sudo apt install <package>` | Installs a package |
| `sudo systemctl restart <service>` | Restarts a service |
| `nano <file>`, `sudo nano <file>` | Edits a file: Ctrl+O and Enter save, Ctrl+X leaves |
| `cp <file> <file>.bak` | Copies a file; `sudo cp` for system files |
| `mkdir -p <folder>` | Creates a folder |
| `mv <from> <to>` | Moves or renames; replaces `<to>` without asking |
| `rm <file>` | Deletes; there is no recycle bin |
| `sudo reboot` | Restarts; your session closes |
| `sudo poweroff` | Shuts down; the server stays off until its button is pressed, or power is cut and restored |

### On your computer: SSH

| Command | What it does |
|---|---|
| `ssh server` | Opens a session (step 12b) |
| `exit` | Closes it |
| `scp server:~/<file> .` | Copies a file from the server; the other way round, to it |
| `ssh -v server` | Connects showing each step: which keys it offers, and why it fails |
| `ssh-keygen -lf $HOME/.ssh/id_ed25519.pub` | Your key's fingerprint |
| `ssh-keygen -R <lan-ip>` | Forgets a server's host key, after a reinstall |
| `nano ~/.ssh/config`; on Windows, `notepad $HOME\.ssh\config` | Opens the file where the short names are (step 12b) |

### tmux

| Keys or command | What it does |
|---|---|
| `tmux new -A -s admin` | Enters the session named admin, creating it if needed |
| Ctrl+b then d | Leaves it running |
| `tmux ls` | Lists the sessions |
| `tmux attach -t admin` | Returns to it |
| Ctrl+b then c, Ctrl+b then n | Opens a new window; moves to the next one |
| Ctrl+b then [ | Scrolls back through the output; q leaves |

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
- fwupd, the plugins that update KEK and db (available since 2.0.8):
  https://github.com/fwupd/fwupd/blob/main/plugins/uefi-kek/README.md and
  https://github.com/fwupd/fwupd/blob/main/plugins/uefi-db/README.md
- fwupd in Ubuntu 24.04's updates: https://packages.ubuntu.com/noble-updates/fwupd
- Binarly, PKfail advisory (BRLY-2024-005, CVE-2024-8105):
  https://binarly.io/advisories/brly-2024-005
- GRUB recordfail default changed to 30 seconds (Launchpad bug 1443735):
  https://lists.snapcraft.io/archives/foundations-bugs/2015-June/243953.html
- Ubuntu community wiki, *AutomaticSecurityUpdates*:
  https://help.ubuntu.com/community/AutomaticSecurityUpdates
- OpenSSH manuals: https://man.openbsd.org/ssh,
  https://man.openbsd.org/ssh_config and https://man.openbsd.org/ssh-keygen
- OpenSSH 8.0 release notes (a pasted fingerprint is accepted as the answer
  to the first-connection question): https://www.openssh.org/txt/release-8.0
- Microsoft, *Key-based authentication in OpenSSH for Windows* (the agent
  service): https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement
- GitHub, *Adding a new SSH key to your GitHub account*:
  https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account
- `ssh-import-id`: https://manpages.ubuntu.com/manpages/noble/man1/ssh-import-id.1.html
- tmux manual: https://man.openbsd.org/tmux.1
- VS Code, *Remote development using SSH*: https://code.visualstudio.com/docs/remote/ssh
