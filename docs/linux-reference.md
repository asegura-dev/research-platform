# Linux reference

> **Scope:** the commands and ideas that the guides use on Ubuntu 24.04, each
> with an example from a guide and what its output means. It is a reference to
> come back to, not a guide to run: the guides are where each command runs in
> its order, with its checks.

> **Status:** written on 2026-11-04, from the guides at commit `67beafb`.
> Revised on 2026-11-24 with the user services of the long runs guide.

The examples use the names of the platform's design, such as `server` for the
service host's SSH alias and `/srv/ntfy` for ntfy's folder, never an
instance's names or addresses. A line that changes the machine says so in its
comment, or in a **Careful** note after it.

## Contents

1. [The terminal](#1-the-terminal)
2. [Files and permissions](#2-files-and-permissions)
3. [Text](#3-text)
4. [Packages](#4-packages)
5. [Services](#5-services)
6. [Network](#6-network)
7. [SSH](#7-ssh)
8. [Docker and Compose](#8-docker-and-compose)
9. [Git](#9-git)
10. [Disks, memory and GPUs](#10-disks-memory-and-gpus)
11. [Habits](#11-habits)

## 1. The terminal

The terminal runs a *shell*, bash on Ubuntu: it reads a line, runs it, and
waits for the next one. Ctrl+Alt+T opens a terminal on Ubuntu Desktop.

**Paths.** `/` is the root of the file system, `~` your home folder, `.` the
folder you are in, and `..` the one above it. A path that starts with `/` or
`~` is absolute; any other one starts from where you are.

```bash
cd ~/src/research-platform     # go into your clone of this repository
pwd                            # print where you are
```

**Variables and `$( )`.** `NAME=value`, with no spaces around `=`, stores a
value, and `"$NAME"` uses it. `$( )` stores what a command prints:

```bash
S=$(ssh -G server | awk '/^hostname /{print $2}')   # the server's name or address, from ~/.ssh/config
curl -s "http://$S:2586/v1/health"                   # {"healthy":true}
```

A variable lives in the terminal that set it: a new terminal, or an SSH
session, starts without it. Quote it, as in `"$S"`, so that a space in its
value does not split it in two.

**Pipes.** `|` hands what one command prints to the next one:

```bash
sudo ss -ltnp | grep 2586      # only the lines about port 2586
```

**`&&`, `||` and the exit status.** Every command ends with a status: 0 when it
worked, any other number when it did not, and `$?` holds the last one. `&&`
runs the next command only after a success, and `||` only after a failure:

```bash
cd ~/src/research-platform && git pull     # pulls only if the cd worked
command -v curl || echo "curl missing"     # the message only if curl is not installed
notify -- false; echo "exit $?"            # exit 1: false always fails
```

**Redirection.** `>` writes what a command prints into a file, replacing it,
and `>>` adds to its end. `2>` does the same with error messages:
`2>/dev/null` throws them away, and `2>&1` sends them where the output goes:

```bash
sudo unattended-upgrades --dry-run --debug 2>&1 | tail -n 20   # its last 20 lines, errors included
```

**Heredocs.** `<<'EOF'` hands the lines that follow, up to a line that says
only `EOF`, to a command as its input. With the quotes, `$` and backquotes stay
as they are; without them, the shell first replaces variables and `$( )`, as
the Docker guide's repository file does with `$(dpkg --print-architecture)`.
A commit message can go in this way:

```bash
git commit -F - <<'EOF'
docs: record the ntfy guide's first run
EOF
```

**`sudo tee`.** `sudo echo text > /etc/file` fails, because the `>` is done by
your own shell, without root. `sudo tee` writes as root, which is why the
guides write system files with `sudo tee FILE >/dev/null`, followed by a
heredoc.

**Parentheses** run their commands in a copy of the shell: a setting made
inside, such as `umask` (section 2), ends with them.

**Loops.**

```bash
for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done   # one fingerprint per host key
```

**Finding a program.** `command -v` prints where a program is, or nothing when
it is not installed:

```bash
command -v notify              # …/.local/bin/notify
```

**tmux: work that outlives the terminal.** A command dies with the terminal, or
the SSH session, that started it. Inside tmux it keeps running:

```bash
tmux new -A -s admin           # enters the session named admin, and creates it if it does not exist
```

Ctrl+b then d leaves the session running, and `tmux attach -t admin` comes back
to it, at the same machine or over SSH. A reboot ends it.

## 2. Files and permissions

**Where things live.**

| Folder | What it holds | Here |
|---|---|---|
| `/etc` | Configuration | `/etc/docker/daemon.json`, `/etc/research-platform/heartbeat.env` |
| `/srv` | The data of services | `/srv/ntfy` |
| `/var/lib` | Programs' state | `/var/lib/apt/periodic/upgrade-stamp` |
| `/usr/local` | Programs installed by hand | `/usr/local/sbin/service-host-heartbeat` |
| `~/.config` | Your programs' configuration | `~/.config/research-platform/ntfy.env` |
| `~/.local/bin` | Your own commands | `notify` |

**Reading `ls -l`.**

```bash
sudo ls -l /srv/ntfy
# -rw-r--r-- 1 root root  604 Nov  4 09:46 compose.yaml
# drwx------ 2 root root 4096 Nov  4 09:46 data
```

The first character is `-` for a file and `d` for a folder. The next nine are
three groups of `rwx`: the owner's, the group's and everyone else's. `r` reads,
`w` writes, and `x` runs a file or enters a folder. Then come the owner, the
group, the size in bytes, and the date of the last change.

**Permissions as numbers.** r is 4, w is 2 and x is 1, added up for each of the
three groups:

| Number | Means | Used for |
|---|---|---|
| 600 | The owner reads and writes; nobody else can do anything | Files with secrets: `ntfy.env`, `heartbeat.env` |
| 644 | The owner writes; everyone reads | Configuration: `compose.yaml`, `server.yml` |
| 700 | Only the owner enters | Folders with secrets: `/srv/ntfy/data` |
| 755 | The owner writes; everyone reads, and runs or enters | Programs and ordinary folders: `notify`, `/srv/ntfy` |

```bash
stat -c '%a' ~/.config/research-platform/ntfy.env   # 600
```

**Creating with the right permissions.** `install` copies files, or creates a
folder, with its permissions in one step, so there is no moment when they are
looser:

```bash
sudo install -d -m 700 /srv/ntfy/data                                           # a folder that only root enters
sudo install -m 644 config/ntfy/compose.yaml config/ntfy/server.yml /srv/ntfy/  # two files that everyone reads
install -m 755 ~/src/research-platform/scripts/notify.sh ~/.local/bin/notify    # a program, for you
```

**Careful:** these commands change the machine, and `install` replaces a file
that is already there.

`umask` sets the permissions that new files get: `077` leaves everything to
their owner. Inside parentheses, it lasts only for that line. The ntfy guide
creates `ntfy.env` this way; this example uses a file of its own, in `/tmp`,
which empties at every boot:

```bash
( umask 077; touch /tmp/umask-test ); stat -c '%a' /tmp/umask-test   # 600
```

**sudo** runs one command as root, the owner of `/etc`, `/srv` and `/usr`. It
asks for your password, then remembers it for 15 minutes in that terminal.

**Fingerprints of files.** `sha256sum` prints a 64-character fingerprint of a
file's content: a single changed byte changes all of it. `sha256sum -c` checks
a list of them and prints `OK` for each file, which is how every delivery to
this repository is checked:

```bash
sha256sum config/ntfy/server.yml /srv/ntfy/server.yml   # the same fingerprint twice: the installed file is the repository's
```

**Finding and counting files.**

```bash
find . -type f -name '*.dcm' | wc -l    # how many DICOM files there are below this folder
```

**Careful:** `cp` and `mv` replace a file of the same name without asking, and
`rm` deletes without a trash bin. Before any of them, look with `ls`, and keep
a copy of what cannot be made again.

## 3. Text

Most commands print text, and these tools cut it down to what matters:

| Tool | What it does | Example |
|---|---|---|
| `grep` | Keeps the lines that match | `sudo ss -ltnp \| grep 2586` |
| `grep -E` | Matches extended patterns: `a\|b`, `[123]`, `+` | `grep -E ':808[123]'` |
| `grep -v`, `-i`, `-c`, `-o` | The lines that do not match; ignoring case; how many; only the match | `grep -c OK` |
| `sed -n 's/^NAME=//p'` | Prints the value after `NAME=` | How the scripts read their files |
| `sed -E 's/old/new/'` | Replaces text | `sed -E 's/tk_[a-z0-9]+/tk_…/'` hides a token |
| `awk '{print $2}'` | Prints a column; spaces separate them | `ssh -G server \| awk '/^hostname /{print $2}'` |
| `awk -F=` | Separates the columns by `=` instead | `awk -F= '{print $1, length($2)}' ntfy.env` prints each name and the length of its value, never the value |
| `head -n 1`, `tail -n 20`, `tail -n +2` | The first line; the last 20; from the second one on | `tail -n +2` skips a header |
| `cut -f1` | The first column of a tab-separated file | |
| `sort -u` | Sorts, without repeats | |
| `wc -l` | Counts lines | |
| `tr -d '[:space:]'` | Deletes characters | Removes stray spaces from a value |

Together they answer a question in one line:

```bash
tail -n +2 "$F" | cut -f1 | sort -u | wc -l   # distinct values of the first column, without the header: 378 patients
```

**Careful:** `sed -i` edits a file in place, with no copy. Run the same command
without `-i` first: it only prints.

## 4. Packages

Ubuntu installs software with *apt*, from repositories that sign their
packages:

```bash
sudo apt update                        # refreshes the lists of what can be installed; installs nothing
sudo apt install lm-sensors            # installs a package, and what it needs
sudo apt full-upgrade                  # installs every update, removing packages when an update needs it
dpkg -l | grep -E '^ii +docker'        # the installed packages whose names start with docker
```

**Careful:** `apt install`, `full-upgrade` and `remove` list what they will
change and ask before doing it. Read the list, above all what it says it will
remove.

**Other repositories.** Docker and Tailscale come from their own repositories,
each with its key in `/etc/apt/keyrings` or `/usr/share/keyrings`, and a file
in `/etc/apt/sources.list.d`. Their guides add both, and from then on `apt`
updates them like any other package.

**Updates by themselves.** unattended-upgrades installs the security updates
every day:

```bash
cat /etc/apt/apt.conf.d/20auto-upgrades                         # both values "1": daily lists and upgrades
sudo unattended-upgrades --dry-run --debug 2>&1 | tail -n 20    # what it would do now, without doing it
ls /var/run/reboot-required 2>/dev/null || echo "no reboot pending"
```

The service host reboots by itself at 04:00 when an update asks for it
([ADR-008](adr/ADR-008-a-service-host-comes-back-on-its-own.md)); the
workstation does not.

## 5. Services

*systemd* starts the machine's services and keeps them running. Each thing it
manages is a *unit*: a `.service` is a program, a `.timer` runs a service on a
schedule, and a `.socket` starts a service at its first connection.

```bash
systemctl status ssh.socket --no-pager   # its state, and its last log lines
systemctl is-enabled docker              # enabled: it starts with the machine
systemctl is-active docker               # active: it is running now
sudo systemctl restart docker            # stops it and starts it again
```

**Timers.**

```bash
systemctl list-timers service-host-heartbeat.timer --no-pager   # when it ran last, and when it runs next
sudo systemctl enable --now service-host-heartbeat.timer        # starts it now, and at every boot
```

After a unit file under `/etc/systemd/system` is added or changed,
`sudo systemctl daemon-reload` makes systemd read it again.

**Never starting something.**

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target   # the workstation never suspends
```

A masked unit cannot start, not even by hand, until `sudo systemctl unmask`.

**The journal.** Everything that a service prints goes to the journal:

```bash
journalctl -u service-host-heartbeat -n 5 --no-pager -o cat   # its last 5 messages, whole
journalctl -k -b | grep -iE 'machine check|hardware error'     # the kernel's messages since this boot, filtered
journalctl -u systemd-oomd --since today                       # what the out-of-memory killer stopped today
```

`-u` names the unit, `-b` means this boot, `-k` the kernel, `--since` a time,
`-n` how many of the last lines, and `-o cat` the messages alone, without their
dates. On Ubuntu 24.04, a one-shot service that worked says
`Deactivated successfully` and `Finished`.

**Your own services.** systemd also runs a manager for each user, with its
units in `~/.config/systemd/user/`. The same commands take `--user`, and need
no `sudo`:

```bash
systemctl --user status run-queue@5080 --no-pager             # one of the queues of the long runs
systemctl --user daemon-reload                                # after a unit in ~/.config/systemd/user changed
journalctl --user -u run-queue@5080 -n 20 --no-pager -o cat   # its last 20 messages, whole
sudo loginctl enable-linger "$USER"                           # changes: your manager starts at boot, and stays after you log out
```

A name with `@`, such as `run-queue@5080`, is an instance of a template unit,
`run-queue@.service`, which takes the part after `@` as `%i`
([long runs guide](guides/operate-long-runs.md)).

## 6. Network

**What listens.**

```bash
sudo ss -ltnp       # every port that waits for connections, its address and its program
```

In its output, `127.0.0.1:2586` listens only for this machine, and
`0.0.0.0:2586` or `[::]:2586` for every network the machine is on. Every
service of the platform listens on `127.0.0.1`, and reaches the tailnet only
through Tailscale Serve
([ADR-004](adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md)).

**Interfaces.**

```bash
ip -br addr         # each network interface, UP or DOWN, with its addresses
```

**curl: HTTP from the terminal.**

```bash
curl -s http://127.0.0.1:2586/v1/health                                       # the answer's body: {"healthy":true}
curl -s -o /dev/null -w '%{http_code}\n' -d test http://127.0.0.1:2586/runs   # only its status code: 403
```

| Option | Does |
|---|---|
| `-s` | Prints no progress |
| `-o /dev/null` | Throws the answer's body away |
| `-w '%{http_code}\n'` | Prints the status code |
| `-d text` | Sends the text, as a POST |
| `-m 5` | Gives up after 5 seconds |
| `-f` | Fails when the server answers with an error |
| `-L` and `-O` | Follows redirections, and saves the file with its own name |

The status codes that the guides meet: 200, it worked; 400, a malformed
request; 401, wrong credentials; 403, refused; 404, nothing at that address;
429, too many requests in a short time.

**Tailscale.**

```bash
tailscale status                                          # the devices in the tailnet, with their names and 100. addresses
tailscale ip -4                                           # this machine's address in the tailnet
tailscale serve status                                    # what this machine publishes to the tailnet
sudo tailscale serve --bg --tcp=2586 tcp://127.0.0.1:2586 # publishes a local port to the tailnet, across reboots
```

**Careful:** `tailscale status` prints your devices' names and addresses:
instance data, never for this repository.

## 7. SSH

SSH opens a terminal on another machine. Each computer has its own key pair:
the private key never leaves it, and the public key, the `.pub` file, goes to
the machines it connects to
([ADR-012](adr/ADR-012-ssh-over-tailscale-with-a-key-per-computer.md)).

```bash
ssh-keygen -t ed25519 -C "laptop"               # a new key pair in ~/.ssh, under that label; give it a passphrase
ssh server                                      # a session on the service host, by its alias
ssh -G server | awk '/^hostname /{print $2}'    # where the alias leads, without connecting
```

**Aliases.** `~/.ssh/config` holds one `Host` block per alias: its `HostName`
line says where the alias leads, and its `User` line as whom
([Tailscale guide](guides/install-tailscale.md), section 6).

**Host fingerprints.** The first connection to a machine shows its key's
fingerprint. Before answering `yes`, compare it with the one that the machine
itself prints:

```bash
for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done   # on that machine: one line per key type
```

Your computer remembers the answer in `~/.ssh/known_hosts`. When a machine is
installed again and its key changes, `ssh-keygen -R` followed by its name or
address forgets the old entry.

**Public keys from GitHub.** `ssh-import-id gh:` followed by your GitHub user
adds the public keys registered there to `~/.ssh/authorized_keys` on the
machine where it runs.

**Careful:** a private key, the file without `.pub`, is a password. It never
goes to a chat, a repository or another computer.

## 8. Docker and Compose

Docker runs programs in *containers*. Each one comes from an *image*, which
carries the program and everything it needs, apart from the rest of the
machine. Compose starts them from a file, `compose.yaml`, kept in the
service's folder:

```bash
cd /srv/ntfy
sudo docker compose ps                       # its state: Up … (healthy)
sudo docker compose logs --tail 50           # its last 50 log lines
sudo docker compose exec ntfy ntfy access    # runs a command inside the running container
```

These change what runs:

```bash
sudo docker compose up -d                    # starts what compose.yaml describes, in the background
sudo docker compose up -d --force-recreate   # creates the container again, so that it reads a changed configuration file
sudo docker compose down                     # stops it and removes the container; the data folder stays
```

In `compose.yaml`:

- `"127.0.0.1:2586:80"` under `ports` publishes the container's port 80 on the
  machine's 127.0.0.1:2586, and nowhere else;
- `./data:/var/lib/ntfy` under `volumes` keeps the container's data in a folder
  of the machine, so that it outlives the container;
- `image: binwiederhier/ntfy:v2.28.0` fixes the version, so an update is a line
  that changes.

```bash
sudo docker run --rm hello-world   # Hello from Docker!: Docker works
sudo docker system df              # the space that images, containers and volumes take
```

**Careful:** Docker sends the traffic of its published ports past the firewall
(ufw). What keeps a port off the network is its address, `127.0.0.1`, which
this platform makes Docker's default ([Docker guide](guides/install-docker.md)).

## 9. Git

Read-only:

```bash
git log --oneline -3                          # the last three commits
git log -1 --format='%h %ad %s' --date=short  # the last one: its short hash, date and subject
git status --short                            # what changed in your copy: M for modified, ?? for new
git diff --stat                               # how many lines changed, per file
```

These change your copy, or GitHub:

```bash
git clone https://github.com/asegura-dev/research-platform.git ~/src/research-platform   # a copy of the repository
git pull                                      # brings what changed on GitHub
git add -u                                    # takes every change to a file git already knows into the next commit
git push                                      # sends your commits to GitHub
```

`git commit -F -` with a heredoc makes the commit (section 1).

**Hooks.** `git config core.hooksPath .githooks` makes a clone run the
instance-data guard before each commit
([guard guide](guides/set-up-the-instance-data-guard.md)).

**Careful:** what is pushed stays in the history for good, even after a later
commit deletes it. That is why the guard checks before the commit, not after.

## 10. Disks, memory and GPUs

```bash
lsblk -o NAME,SIZE,MODEL,TRAN,FSTYPE,MOUNTPOINTS   # disks, their partitions, and where those are mounted
findmnt -n -o SOURCE /                             # the partition the system runs from
df -h /                                            # how full that partition is
free -h                                            # memory in use, and available
lscpu | grep 'Model name'                          # the processor
uname -r                                           # the version of the running kernel
sensors                                            # temperatures, and fans when the board's driver loads
```

An NVMe SSD's health, for the first one (`lsblk` says which disk is which):

```bash
sudo smartctl -a /dev/nvme0n1 | grep -E 'Critical Warning|Percentage Used|Media and Data Integrity Errors|Temperature:'
```

A healthy SSD shows `0x00` as its critical warning, a low percentage used, and
0 integrity errors.

**GPUs.**

```bash
nvidia-smi                       # every GPU: model, temperature, power, memory and processes; the driver and CUDA versions
nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv   # the same, as a table
watch -n 5 nvidia-smi            # again every 5 seconds, until Ctrl+C
```

**Careful:** `nvidia-smi -L` prints each GPU's UUID, which is instance data.

**Boot.**

```bash
mokutil --sb-state               # SecureBoot enabled, or disabled
sudo efibootmgr                  # the firmware's boot entries, and their order
```

**Careful:** `efibootmgr -o` changes the boot order, and a wrong order can boot
Windows, or nothing
([workstation guide](guides/install-ubuntu-gpu-workstation.md)).

## 11. Habits

- **`sudo -v` before a pasted block.** sudo asks for your password the first
  time in a terminal, and again 15 minutes after its last use. If it asks in
  the middle of a pasted block, the lines pasted after the prompt are taken as
  the password. `sudo -v`, alone, asks first.
- **Read-only first.** Every guide looks before it changes anything (`ls`,
  `status`, `ss`, `--dry-run`), and changes nothing until what it sees matches
  what it expects.
- **Secrets stay out of command lines and chats.** A command line can be read
  by any process on the machine, and stays in the history. The scripts read
  their secrets from files that only you can read: `notify` takes its token
  from `ntfy.env`. To check a secret without showing it, print its length with
  `awk`, or hide it with `sed` (section 3).
- **Keys.** Ctrl+Shift+C and Ctrl+Shift+V copy and paste in the terminal;
  Ctrl+C stops the command that is running; Ctrl+click opens a link; the up
  arrow brings back the last commands, and Ctrl+R searches them.
- **nano.** `nano` followed by a file opens it; Ctrl+O and Enter save it;
  Ctrl+X leaves.
- **Termux, on the phone.** The Volume Down button works as Ctrl.
- **Manuals.** `man` followed by a command's name, such as `man ss`, shows its
  manual; q leaves it.

## References

- Ubuntu Server documentation: https://documentation.ubuntu.com/server/
- The GNU Bash manual: https://www.gnu.org/software/bash/manual/
