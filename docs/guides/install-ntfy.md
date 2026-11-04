# Install ntfy on the service host

> **Scope:** the service host, the phone and the workstation. At the end,
> ntfy runs on the service host, reachable only inside the tailnet, and
> refuses whoever it does not know; the phone receives its notifications at
> any hour; and a command on the workstation tells the phone when it ends. How
> a training uses it comes with the long runs (roadmap).

> **Status:** written on 2026-11-03 from ntfy's documentation and source, for
> ntfy 2.28.0 (released on 2026-08-27), and from Tailscale's documentation of
> Serve. First run on 2026-11-04, sections 1 to 8: ntfy refused every request
> without a user, and the phone received the three notifications sent from the
> workstation. Serve first published ntfy over HTTP, and answered
> `404 page not found` to the workstation, whose SSH `config` names the server
> by its `100.` address: over HTTP, Serve answers only a request addressed to
> the server's name. Revised from that run: section 5 publishes over TCP,
> which the server's addresses reach as well as its name, section 4's check
> hides the token, section 9 recreates the container on an update, and
> `notify` sends no tags, which the phone showed as emojis.

ntfy delivers notifications by *topic*: whatever is published to a topic
reaches every phone subscribed to it. Here it runs in Docker on the service
host, one more service under `/srv`
([Docker guide](install-docker.md)), and it is the first one published to the
tailnet. Two locks keep it: only devices in the tailnet reach it, and ntfy
itself refuses every request that does not come from a user with access to
the topic. There are two users and one topic, `runs`:

- `phone` reads it, with a password typed once in the phone's app;
- `workstation` publishes to it, with a *token* kept in a file on the
  workstation that only you can read.

The names of the topic and of the users are part of the design, the same on
every instance, and they open nothing by themselves: on a public server a
topic's name is its only lock, but this one refuses whoever has no user. What
is secret is the token and the phone's password.

With a server of your own, the phone's app does not use Google's push service:
it keeps a connection open with the server. That is why Tailscale stays on in
the phone, with Android's always-on VPN; a phone out of the tailnet gets what
it missed when it is back, within 48 hours.

ntfy is published over plain HTTP inside the tailnet. Tailscale already
encrypts every connection between your devices, and an HTTPS certificate would
write the server's name, and the tailnet's, in public certificate logs.

A notification leaves the workstation and waits on the server for 48 hours:
it carries a status, a run name and numbers, never paths, study identifiers
or patient data
([ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md)).

Why it is built this way, and what was refused, is in
[ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md).

Read the [Docker guide](install-docker.md) and the
[Tailscale guide](install-tailscale.md) first: this guide builds on them.
Sections 1 to 5 run on the server, over SSH (`ssh server`); section 6 on the
phone; sections 7 and 8 on the workstation.

Every step ends with a check. Read-only commands come first, and nothing that
changes the machine runs until they match what you expect.

Before pasting a block that has `sudo` after its first line, run `sudo -v`
alone and type your password. In a new session, or 15 minutes after the last
`sudo`, a password prompt would take the lines pasted after it.

Never commit the token, the phone's password, the server's name or its
address to this repository.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| Where it runs | Docker on the service host, in `/srv/ntfy`, from the image `binwiederhier/ntfy:v2.28.0` | The service host is always on; an image by version makes an update a line you change | [ADR-004](../adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md), [ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md) |
| How it is reached | Port 2586 on 127.0.0.1, published to the tailnet by Tailscale Serve, which forwards each connection over TCP; ntfy speaks plain HTTP | Nothing outside the tailnet reaches it, and the server's `100.` address reaches it as well as its name; Tailscale encrypts the traffic, and no certificate puts the server's name in public logs | [ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md) |
| Who may use it | Nobody by default; `phone` reads the topic `runs`, and `workstation` publishes to it | The second lock: a device in the tailnet without a user gets nothing | [ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md) |
| How the phone receives | The ntfy app keeps a connection open with the server; Tailscale stays on in the phone | A server of your own gets no push from Google; a phone out of the tailnet hears nothing until it is back | [ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md) |
| How the workstation publishes | `notify`, a script in this repository, with the token in `~/.config/research-platform/ntfy.env`, readable only by you | The token never goes on a command line or into git; a project reads the same three values | [ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md) |
| What a message carries | A status, a program or run name, numbers | Messages leave the workstation and wait on the server | [ADR-007](../adr/ADR-007-liveness-is-watched-from-outside.md), [ADR-014](../adr/ADR-014-ntfy-stays-inside-the-tailnet-and-answers-only-its-users.md) |
| What ntfy keeps | Messages for 48 hours, and its users and token, in `/srv/ntfy/data`, readable only by root | A phone that was off gets what it missed; the token is a secret | This guide |

## 1. What you need

- The service host with Docker (Docker guide, sections 1 to 6), and in the
  tailnet with the workstation (Tailscale guide, through section 6).
- The phone in the tailnet: Tailscale from Google Play, signed in with the
  same account (Tailscale guide, section 8, step 1). In Android's settings,
  under *VPN*, turn on *Always-on VPN* for Tailscale; the names vary with the
  brand.
- The ntfy app on the phone, from Google Play or F-Droid.

On the server, read-only:

```bash
sudo docker compose version                              # Docker Compose version v5.6.1 or later
sudo ss -ltnp | grep 2586 || echo "nothing on 2586"      # nothing on 2586
tailscale serve status                                   # No serve config
ls -d /srv/ntfy 2>/dev/null || echo "not there yet"      # not there yet
```

**Check:** each command prints what its comment says, and the Tailscale app on
the phone says it is connected and lists the server.

## 2. Put ntfy's files in `/srv/ntfy`

On the server, bring its clone of this repository up to date, and see which
commit it is at:

```bash
cd ~/src/research-platform
git pull
git log -1 --format='%h %ad %s' --date=short
```

It must be the latest commit on the repository's page on GitHub. Then the
folder, a data folder that only root can read, and the two files:

```bash
sudo install -d -m 755 /srv/ntfy
sudo install -d -m 700 /srv/ntfy/data
sudo install -m 644 config/ntfy/compose.yaml config/ntfy/server.yml /srv/ntfy/
```

`server.yml` holds no instance values: the users, the token and the messages
go to the database in `data`.

**Check:**

```bash
sudo ls -l /srv/ntfy
```

It lists `compose.yaml` and `server.yml` as `-rw-r--r-- root root`, and `data`
as `drwx------ root root`.

## 3. Start ntfy

```bash
cd /srv/ntfy
sudo docker compose up -d
```

Docker downloads the image the first time. Then, read-only:

```bash
sudo docker compose ps                                                   # ntfy, Up … (healthy), 127.0.0.1:2586->80/tcp
sudo ss -ltnp | grep 2586                                                # 127.0.0.1:2586, and nothing else
curl -s http://127.0.0.1:2586/v1/health                                  # {"healthy":true}
curl -s -o /dev/null -w '%{http_code}\n' -d test http://127.0.0.1:2586/runs   # 403
```

The status says `(health: starting)` for its first 40 seconds. The last line
publishes without a user, and ntfy refuses it: that is the second lock.

**Check:** the four outputs match their comments.

## 4. Users, their access, and the token

Still in `/srv/ntfy`. The phone's user first; ntfy asks for its password
twice. The phone's app keeps it, so you need not: if it is ever lost, section
9 says how to change it.

```bash
sudo docker compose exec ntfy ntfy user add phone
```

Then the workstation's user, with a random password that nobody sees, because
the workstation uses a token instead; and what each one may do:

```bash
sudo docker compose exec -e NTFY_PASSWORD="$(head -c 24 /dev/urandom | base64)" ntfy ntfy user add workstation
sudo docker compose exec ntfy ntfy access phone runs ro
sudo docker compose exec ntfy ntfy access workstation runs wo
sudo docker compose exec ntfy ntfy access
```

The last command lists every user: `phone` with read-only access to `runs`,
`workstation` with write-only access to it, and everyone else with none.

Then the workstation's token:

```bash
sudo docker compose exec ntfy ntfy token add --label=workstation workstation
```

It prints `token tk_… created for user workstation, never expires`. Leave it
on the screen: section 7 copies it into a file on the workstation. Do not
paste it anywhere else, in a chat or in a screenshot: whoever holds it can
publish to the topic.

**Check:** the list shows the two users with those accesses, and this shows
one token, labeled `workstation`. `token list` prints the token in full, so
`sed` hides it:

```bash
sudo docker compose exec ntfy ntfy token list workstation | sed -E 's/tk_[a-z0-9]+/tk_…/'   # - tk_… (workstation), never expires, …
```

## 5. Publish it to the tailnet

```bash
sudo tailscale serve --bg --tcp=2586 tcp://127.0.0.1:2586
tailscale serve status
```

Serve forwards each connection to ntfy as it comes, without reading it, so
the server's `100.` address reaches ntfy as well as its name. Over HTTP
(`--http`), Serve would answer only a request addressed to the server's name:
one addressed to its address gets `404 page not found`. `--bg` keeps it
published across reboots. The status shows the server's name on port 2586,
marked as reachable from the tailnet only, then its two addresses on the same
port, all sent to `tcp://127.0.0.1:2586`.

From the workstation, read-only, with the server's name or address in the
tailnet taken from its SSH `config`:

```bash
S=$(ssh -G server | awk '/^hostname /{print $2}')
curl -s "http://$S:2586/v1/health"                                       # {"healthy":true}
curl -s -o /dev/null -w '%{http_code}\n' -d test "http://$S:2586/runs"   # 403
```

**Check:** the workstation reaches ntfy through the tailnet, and ntfy refuses
it without a user.

## 6. The phone

1. In the Tailscale app, find the server and copy its address, the one that
   starts with `100.`. Use the address, not the name: on Android a name can
   fail to resolve (Tailscale guide, section 8).
2. In the ntfy app, **+**, then in *Subscribe to topic*:
   - the topic: `runs`;
   - **Use another server**, and in it `http://`, the server's address and
     `:2586`, as in `http://<server-address>:2586`;
   - **Instant delivery in doze mode**, on (the F-Droid build has it always
     on).

   Then **Subscribe**. The app answers *Login required*: type `phone` and its
   password, then **Log in**.
3. If Android asks whether ntfy may run in the background, or ignore battery
   optimization, allow it: otherwise Android stops it from listening.

**Check:** the app lists `runs`, and a notification that stays says that ntfy
is subscribed to an instant delivery topic.

## 7. The workstation: its token and `notify`

On the workstation. Bring the clone up to date, then write the file with the
server's address and the topic, readable only by you:

```bash
cd ~/src/research-platform && git pull
mkdir -p ~/.config/research-platform ~/.local/bin
S=$(ssh -G server | awk '/^hostname /{print $2}')
( umask 077; printf 'NTFY_URL=http://%s:2586\nNTFY_TOPIC=runs\nNTFY_TOKEN=\n' "$S" > ~/.config/research-platform/ntfy.env )
nano ~/.config/research-platform/ntfy.env
```

In nano, right after `NTFY_TOKEN=`, paste the token that section 4 left on the
server's screen. Save with Ctrl+O and Enter, and leave with Ctrl+X. Then the
script, which reads that file:

```bash
install -m 755 ~/src/research-platform/scripts/notify.sh ~/.local/bin/notify
```

**Check**, without showing the token:

```bash
stat -c '%a' ~/.config/research-platform/ntfy.env                       # 600
awk -F= '{print $1, length($2)}' ~/.config/research-platform/ntfy.env   # NTFY_URL and a length, NTFY_TOPIC 4, NTFY_TOKEN 32
command -v notify                                                       # …/.local/bin/notify
```

## 8. Try it

```bash
notify "Hola desde la workstation"
notify -- sleep 5
notify -- false; echo "exit $?"                                         # exit 1
```

The phone shows three notifications:

- *Notice*, with the text;
- *sleep finished*, *It took 0h 00m 05s.*;
- *false failed*, *Exit status 1, after 0h 00m 00s.*, with a higher priority.

`notify -- command` runs any command, waits for it, and tells the phone how it
ended and how long it took. It names only the program, never its arguments,
which may hold paths, and it exits with the command's status.

**Check:** the three notifications arrived, and the terminal printed nothing
but `exit 1`.

## 9. Living with it

- **Long commands:** `notify -- ` in front of a conversion, a download or a
  copy. A training notifies through the long runs' guide, with the same three
  values.
- **What a message carries:** a status, a program or run name, and numbers;
  never paths, study identifiers or patient data. It waits on the server for
  48 hours.
- **Users and tokens,** from `/srv/ntfy` on the server:

  ```bash
  sudo docker compose exec ntfy ntfy access                       # every user and its access
  sudo docker compose exec ntfy ntfy token list workstation       # the workstation's tokens, in full
  sudo docker compose exec ntfy ntfy user change-pass phone       # a new password for the phone
  ```

  A lost phone: change the phone's password, and type the new one only on the
  new phone. A token that leaked: `ntfy token remove workstation`, followed by
  the token, then a new one (section 4) into the workstation's file
  (section 7).
- **Updates:** a new version is a new image line in this repository's
  `config/ntfy/compose.yaml`. On the server, `git pull`, section 2's `install`
  of the two files, then `sudo docker compose up -d --force-recreate` in
  `/srv/ntfy`: without `--force-recreate`, a change to `server.yml` alone
  would not restart ntfy. Read the release notes first.
- **The 04:00 reboot:** ntfy comes back by its restart policy, the
  publication by `--bg`, and the phone reconnects and fetches what it missed.
- **To stop publishing it:** `sudo tailscale serve --tcp=2586 off`.
- **Backups:** `/srv/ntfy/data` holds the users, the token and the messages;
  the backups (roadmap) copy `/srv`.

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 3 | `docker compose ps` shows `unhealthy` or `Restarting` | `sudo docker compose logs --tail 50` in `/srv/ntfy` says why, usually a typo in `server.yml`: install it again from the repository (section 2) and `sudo docker compose up -d`. |
| 3 | `ss` shows `0.0.0.0:2586` or `[::]:2586` | Stop it at once with `sudo docker compose down`. The `ports` line of `compose.yaml` lost its `127.0.0.1`: install it again from the repository (section 2). |
| 3, 5 | Publishing without a user answers `200` | Stop it with `sudo docker compose down`: `server.yml` lacks `auth-default-access: deny-all`. Install it again (section 2) and start it again. |
| 4 | `ntfy user add` says that the user already exists | It was created before: `ntfy access` shows it, and `ntfy user change-pass phone` changes its password. |
| 5 | `curl` from the workstation says `Could not resolve host` | `tailscale status` on the workstation must list the server; MagicDNS must be on (Tailscale guide, section 5). |
| 5 | `curl` from the workstation waits, or says `Connection refused` | `tailscale serve status` on the server: repeat the `tailscale serve` command of section 5. |
| 5 | `curl` from the workstation answers `404 page not found` | ntfy is published over HTTP, which answers only by the server's name: on the server, `sudo tailscale serve --http=2586 off`, then section 5's command. |
| 6 | The app says *Login failed. User phone not authorized* | The password, or the access line for `phone` (section 4). |
| 6, 8 | The topic is listed, but notifications do not arrive | Tailscale is off on the phone, or Android stopped ntfy: in the app's battery settings, let it run without restrictions. |
| 7, 8 | `notify: NTFY_URL, NTFY_TOPIC and NTFY_TOKEN must be set` | The file lacks a line or a value: section 7's `awk` check shows which. |
| 8 | `curl: (22) The requested URL returned error: 401` | The token is wrong or was removed: a new one (section 4) into the file (section 7). |
| 8 | `curl: (22) The requested URL returned error: 403` | `workstation` cannot publish to that topic: the file must say `NTFY_TOPIC=runs`, and section 4's `ntfy access workstation runs wo` must have run. |
| 8 | `curl: (6) Could not resolve host` | The workstation is out of the tailnet: `tailscale status`. |
| 8 | `curl: (22) The requested URL returned error: 429` | Too many messages in a short time: wait a minute. |

## Next

The long runs: a training that notifies when it starts, every few dozen
epochs, when it ends and when it fails, through the same three values. What
comes next is in the [roadmap](../roadmap.md).

## References

- ntfy, *Configuring the ntfy server* (access control, behind a proxy, the
  message cache): https://docs.ntfy.sh/config/
- ntfy, *Installation* (Docker): https://docs.ntfy.sh/install/
- ntfy, *Publishing* (title, priority and authentication):
  https://docs.ntfy.sh/publish/
- ntfy, *Subscribe from your phone* (instant delivery, self-hosted servers):
  https://docs.ntfy.sh/subscribe/phone/
- ntfy 2.28.0, its release on GitHub:
  https://github.com/binwiederhier/ntfy/releases/tag/v2.28.0
- Tailscale, *tailscale serve*: https://tailscale.com/kb/1242/tailscale-serve
- Tailscale's source, where Serve over HTTP picks what answers by the name in
  each request (`getServeHandler`):
  https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go
