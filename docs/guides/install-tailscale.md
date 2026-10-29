# Join the hosts and your computers with Tailscale

> **Scope:** the service host, the GPU workstation's Ubuntu, the computers you
> work from (Windows or Ubuntu) and an Android phone. At the end, `ssh server`
> works from anywhere, and nothing is opened to the internet. Services
> published with Tailscale Serve come in their own guides. Switching the
> workstation to Windows remotely is not covered yet.

> **Status:** written on 2026-10-25, from the documentation and the source
> code of Tailscale 1.104.2. First run on 2026-10-28, sections 1 to 7, with the
> workstation, the service host and a Windows laptop; the phone (section 8) is
> still to run. Revised from that run on 2026-10-29.

Tailscale joins your devices in a private network of their own, a *tailnet*.
Each device gets an address that starts with `100.` and a name, and reaches
the others by that name from any network: at home, on a phone's hotspot, at
the university. The traffic between two devices is encrypted end to end, and
no port is opened in the router.

SSH does not change. It keeps OpenSSH and each computer's own key; Tailscale
only carries the connection
([ADR-012](../adr/ADR-012-ssh-over-tailscale-with-a-key-per-computer.md)).
Read the [server guide](install-ubuntu-server.md) first, at least its step 7
and its appendix A: this guide builds on them.

Every step ends with a check. Read-only commands come first, and nothing that
changes the machine runs until they match what you expect.

Placeholders used throughout; replace each one, angle brackets included:

- `<server-name>` and `<workstation-name>`: each host's name in the tailnet,
  as `tailscale status` prints it (section 5).
- `<server-address>` and `<workstation-address>`: each host's address in the
  tailnet, the one that starts with `100.` (`tailscale ip -4` on it).
- `<user>`, `<github-user>`, `<lan-ip>`: as in the server guide.

Never commit tailnet names, `100.` addresses or machine names to this
repository. They go in your private note.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| SSH | OpenSSH with each computer's own key, over the LAN or the tailnet; Tailscale SSH stays off | A login needs the tailnet and a key | [ADR-012](../adr/ADR-012-ssh-over-tailscale-with-a-key-per-computer.md) |
| Services | They listen on 127.0.0.1 and are published only with Tailscale Serve, in their own guides | Nothing is reachable from the internet or the LAN | [ADR-004](../adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md) |
| Key expiry | Off on the two hosts; on, after 180 days, on the computers you carry | A host must not drop off the tailnet while nobody is around; a lost laptop expires by itself | This guide |
| Tailscale updates | Automatic, Tailscale's default | Fixes for the program that holds the network arrive without waiting; each one restarts it for a few seconds | This guide |
| Access policy | Tailscale's default: every device of yours reaches every other | One person, a few devices | This guide |

## 1. What you need

- The service host installed (server guide, through step 11) and the
  workstation installed (its guide, through section 20).
- SSH from the workstation to the server over the LAN, with the short name
  `server` (server guide, step 12b).
- An account to sign in to Tailscale with: Google, Microsoft, GitHub or Apple.
  Turn on its two-factor authentication first: the tailnet is one of the two
  locks of ADR-012.
- The Personal plan is free: up to 6 users and as many personal devices as you
  want (as of April 2026).

**Check:** `ssh server` from the workstation opens a session.

## 2. Install Tailscale on the workstation

In the workstation's terminal. Read-only first:

```bash
command -v tailscale || echo "not installed"      # not installed
lsb_release -cs                                    # noble
command -v curl || echo "curl missing"             # if missing: sudo apt install curl
```

Tailscale publishes its own package repository. Its signing key goes into
`/usr/share/keyrings` and the repository's line into `/etc/apt/sources.list.d`,
so that apt installs and updates it like any other package. Run `sudo -v`
alone first, then:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
```

The last command prints the repository's line. Then the package, which asks
before installing (answer `Y`):

```bash
sudo apt update && sudo apt install tailscale
```

**Check:**

```bash
gpg --show-keys /usr/share/keyrings/tailscale-archive-keyring.gpg   # a key whose owner line names Tailscale
tailscale version                                                   # 1.104 or later
systemctl is-enabled tailscaled                                     # enabled: it starts with the machine
```

## 3. Sign in: this creates the tailnet

Still on the workstation:

```bash
sudo tailscale up
```

It prints `To authenticate, visit:` and a link. Open it with Ctrl+click, sign
in with your account and accept the device. The terminal then prints
`Success.`. The first sign-in creates your tailnet; every other device joins it
by signing in with the same account.

**Check:**

```bash
tailscale status       # one line: this machine's 100. address, its name, your account, linux
tailscale ip -4        # its address in the tailnet
```

## 4. Install Tailscale on the server and sign it in

From the workstation, `ssh server`, and in that session the commands of
section 2: the read-only ones, `sudo -v`, the repository and the package,
and the checks. Then:

```bash
sudo tailscale up
```

The server has no browser: the link appears in your session on the
workstation. Open it there with Ctrl+click (or copy it with Ctrl+Shift+C),
sign in with the same account and accept the device. The server's terminal
prints `Success.`.

**Check:** on the server, `tailscale status` lists both machines. From the
workstation, the server answers through the tailnet:

```bash
tailscale ping <server-name>     # pong from <server-name> (100.…) …
```

The first answers may say `via DERP`, Tailscale's relays, until the two
machines find a direct path; both work.

## 5. Names, and the settings of the admin console

In `tailscale status`, the second column is each machine's name in the
tailnet; Tailscale makes it from the machine's hostname. Write both names and
both `100.` addresses in your private note.

In the admin console, https://console.tailscale.com/admin/machines:

1. **Key expiry, off for the hosts.** Every device signs in for 180 days by
   default; when that ends it drops off the tailnet until someone signs it in
   again. For each host, open the menu at the end of its row (`…`) and choose
   *Disable key expiry*. Leave it on for laptops: a lost one drops off by
   itself.
2. **Names.** To change one, *Edit machine name* in the same menu, unchecking
   the option that takes it from the hostname. A name ends up in public
   certificate logs if HTTPS certificates are turned on later, for Serve:
   nothing private in it.
3. **MagicDNS,** on the DNS page: it must be on. It is what makes the names
   work, and it is on by default for tailnets created since 2022.

On each host, read-only:

```bash
tailscale get auto-update        # true: Tailscale updates itself
```

**Check:** both hosts show *Expiry disabled* in the Machines page, and
`tailscale status` on each lists the other by its name.

## 6. SSH by name, from anywhere

Each computer you connect from has its own `config`; the server guide's step
12b says how to open it on Ubuntu and on Windows. By the end of this guide,
they hold these names:

| Computer | Names in its `config` |
|---|---|
| The workstation | `server` and `server-lan` |
| Any other computer you work from, Windows or Ubuntu | `server` and `server-lan`; `workstation`, once the workstation runs its SSH server |
| The phone | `server` and `workstation`, by their `100.` addresses (section 8) |

On the workstation, open it with `nano ~/.ssh/config`. `server` now names the
host in the tailnet, and `server-lan` keeps the LAN address, the way in at
home when Tailscale is out of reach:

```text
Host server
    HostName <server-name>
    User <user>

Host server-lan
    HostName <lan-ip>
    User <user>
```

The first `ssh server` asks for the server's fingerprint again, because SSH
remembers hosts by the name it reaches them by, and this one is new. Answer as
in the server guide's step 7b, with the server's fingerprint from your note.
On current clients (OpenSSH 8.5 or later, which leaves out Windows 10's), the
question also says `This host key is known by the following other
names/addresses:` and lists the LAN address (`[hashed name]` on Ubuntu): it is
the key you accepted there. `server-lan` uses the address SSH already knows.

`HostName` can also be the server's `100.` address instead of its name: it
does not change while the server stays in the tailnet.

**Check:** `ssh server` and `ssh server-lan` both open a session on the server.

Once the workstation runs its SSH server (its guide, section 22), the
computers you work from reach it by name too, with these lines added to their
`config`:

```text
Host workstation
    HostName <workstation-name>
    User <user>
```

The first `ssh workstation` asks for the workstation's fingerprint: compare it
with the ones you wrote down in its guide's section 22.

## 7. A computer outside the house (Windows)

In PowerShell:

```powershell
winget install -e --id Tailscale.Tailscale
```

The installer from https://tailscale.com/download/windows does the same.
Tailscale's icon appears next to the clock: right click, *Log in*, and sign in
with the same account in the browser that opens.

Then the computer's SSH key, if it does not have one yet, as for any new
computer (section 9): server guide, appendix A, steps A.1 to A.3. Then its
`config`, with the lines of section 6: `notepad $HOME\.ssh\config` opens it,
once the file exists (server guide, step 12b).

**Check:** `Resolve-DnsName <server-name>` returns a `100.` address (on
Windows, test names this way, not with `nslookup`); then, from another
network, such as a phone's hotspot, `ssh server` opens a session.

## 8. A phone (Android)

For ADR-012 a phone is one more computer: it joins the tailnet and gets its
own key. Termux gives it a terminal with OpenSSH.

1. Install **Tailscale** from Google Play and sign in with the same account.
   Leave its key expiry on: a lost phone drops off the tailnet by itself.
2. Install **Termux** from F-Droid or from its GitHub releases, not from
   Google Play, whose build is experimental and missing features. Take every
   Termux app from one source: a mix fails to update.
3. In Termux, the SSH client, an editor, and the phone's key:

   ```bash
   pkg update && pkg install openssh nano
   ssh-keygen -t ed25519 -C "<label>"
   cat ~/.ssh/id_ed25519.pub
   ```

   Give the key a passphrase: a phone stolen unlocked already holds the
   tailnet and the key, and the passphrase is what is left. Select the line
   that `cat` printed (a long press) and copy it.
4. Register the key in GitHub from the phone's browser, and import it on each
   host from a computer that already connects: server guide, appendix A,
   steps A.2 and A.3.
5. In Termux, `nano ~/.ssh/config`, with each host's `100.` address rather
   than its name: on Android a name can fail to resolve, for example with
   Private DNS turned on, and a device's tailnet address does not change while
   it stays in the tailnet.

   ```text
   Host server
       HostName <server-address>
       User <user>

   Host workstation
       HostName <workstation-address>
       User <user>
   ```

6. `ssh server`, pasting the server's fingerprint from your note when asked
   (server guide, step 7b).

In Termux, the Volume Down button works as Ctrl (Volume Down and c is Ctrl+C),
and the row of extra keys above the keyboard has Esc, Tab and the arrows. To
look at a training: `ssh workstation`, then `tmux attach -t bench`; Ctrl+b then
d leaves it running.

**Check:** with Wi-Fi off, on mobile data, `ssh server` opens a session from
the phone.

A lost phone is a retired computer (section 9).

## 9. A new computer, and one you retire

A new computer, in this order:

1. Tailscale, signed in with your account: sections 2 and 3 on Ubuntu,
   section 7 on Windows, section 8 on an Android phone.
2. Its SSH key, and that key in GitHub: server guide, appendix A, steps A.1
   and A.2.
3. From a computer that already connects, the key onto each host:
   `ssh server`, then `ssh-import-id gh:<github-user>`, and the list of
   fingerprints (appendix A.3); the same on the workstation once it runs an
   SSH server.
4. Its `config` (section 6; section 8 on a phone), and the first connection,
   comparing the fingerprint.

A computer you retire, lose or reinstall:

1. In the Machines page, its menu, *Remove*: it leaves the tailnet.
2. Its key out of GitHub and out of each host: server guide, appendix A.5.

**Check:** the new computer opens `ssh server` from outside the house, and the
retired one no longer appears in `tailscale status`.

## 10. Living with Tailscale

- **Updates restart Tailscale.** For a few seconds, the sessions that go over
  the tailnet can freeze or drop. Anything long runs in tmux (server guide,
  step 12c). A training on the workstation runs on the machine itself and is
  not affected.
- **Laptops and phones sign in again every 180 days:** the icon's *Log in* on
  Windows, `sudo tailscale up --force-reauth` on Ubuntu, the app on the phone.
- **When Tailscale is out of reach** (an outage, an account problem), at home
  `ssh server-lan` still works: that is why it stays.
- **Firewall.** ufw is off on both hosts. If it is turned on one day, it will
  not filter what arrives over Tailscale: Tailscale puts its own rule first,
  and its access policy decides there.
- **Docker,** when it comes: every port published on 127.0.0.1 only. Docker
  sends published ports past the firewall
  ([ADR-004](../adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md)).

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 2 | `apt update` reports the Tailscale repository's key as missing (`NO_PUBKEY`) | The key did not download: repeat the first `curl` command of section 2. |
| 3, 4 | `tailscale up` waits and no link appears | The machine has no internet access: `tailscale netcheck` shows whether it reaches Tailscale. |
| 4, 5 | `tailscale status` says `Logged out.` and `Log in at:` with a link | That machine is not signed in: open the link, or run `sudo tailscale up` again. |
| 5, 10 | A device shows `offline` in `tailscale status` | It is off, without network, or its key expired: `sudo tailscale up --force-reauth` on it. |
| 6 | `ssh: Could not resolve hostname <server-name>` | MagicDNS is off, or the name is different: compare with `tailscale status`; meanwhile, `ssh <user>@$(tailscale ip -4 <server-name>)` works on Ubuntu. |
| 6, 7 | `ssh server` asks for the fingerprint | Expected the first time by a new name: compare it with your note (server guide, step 7b). |
| 6 | `tailscale ping <server-name>` answers, but `ssh server` does not | Something on the server blocks port 22: on it, `systemctl status ssh.socket ssh --no-pager`. |
| 7 | `Resolve-DnsName` finds nothing on Windows | Tailscale is not signed in on that computer: its icon, *Log in*. |
| 8 | On the phone, `ssh` cannot resolve a host's name, or times out | Use the host's `100.` address in Termux's `config` (section 8), and check that the Tailscale app shows *Connected*. |

## Next

The services, each with its own guide: Docker, ntfy, healthchecks (the host
heartbeat), Forgejo and its runner, and the experiment tracker. Each one is
published with Tailscale Serve.

## References

- Tailscale, package repository and its Ubuntu 24.04 instructions:
  https://pkgs.tailscale.com/stable/
- Tailscale, *Install Tailscale on Linux*:
  https://tailscale.com/docs/install/linux.md
- Tailscale, *Install Tailscale on Windows*:
  https://tailscale.com/docs/install/windows.md
- Tailscale, `tailscale up`: https://tailscale.com/docs/reference/tailscale-cli/up
- Tailscale, *Key expiry*:
  https://tailscale.com/docs/features/access-control/key-expiry.md
- Tailscale, *MagicDNS*: https://tailscale.com/docs/features/magicdns.md
- Tailscale, *Machine names*: https://tailscale.com/docs/concepts/machine-names.md
- Tailscale, *Tailscale SSH* (what ADR-012 refuses):
  https://tailscale.com/docs/features/tailscale-ssh.md
- Tailscale, *Auto-updates*: https://tailscale.com/docs/features/client/update.md
- Tailscale, *Netfilter modes* (its firewall rules on Linux):
  https://tailscale.com/docs/reference/netfilter-modes.md
- Tailscale, *Tailscale Serve*: https://tailscale.com/docs/features/tailscale-serve.md
- Tailscale, Personal plan as of April 2026: https://tailscale.com/blog/pricing-v4
- Tailscale source code, version 1.104.2:
  https://github.com/tailscale/tailscale/tree/v1.104.2
- Microsoft, winget package `Tailscale.Tailscale`:
  https://github.com/microsoft/winget-pkgs/tree/master/manifests/t/Tailscale/Tailscale
- Docker, published ports and the firewall:
  https://docs.docker.com/engine/network/packet-filtering-firewalls/
- Termux, where to install it from (F-Droid, GitHub; the Google Play build is
  experimental): https://github.com/termux/termux-app
