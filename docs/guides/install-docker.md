# Install Docker on the service host

> **Scope:** the service host only. At the end, Docker runs containers that
> come back after a reboot, and every port they publish stays on the server,
> at 127.0.0.1, where only Tailscale Serve reaches it. The services come in
> their own guides. The workstation is not covered.

> **Status:** written on 2026-10-30 from Docker's documentation, for Docker
> Engine 29.9 (29.9.2, released on 2026-10-20). Not run yet.

Docker runs each service in a *container*: the service's program, isolated
from the rest of the server, started from an *image* that the service's
project publishes with everything the program needs. Compose describes a
service in one file, `compose.yaml`: its image and version, its ports, its
folders, and whether it comes back after a reboot. Each service guide brings
its own.

By default, Docker opens a published port on every interface of the server,
and it routes the traffic to it before any rule of ufw's applies
([ADR-004](../adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md)).
This guide installs Docker, makes 127.0.0.1 its default address, and tests two
things before any service depends on them: that another computer cannot reach
a published port, and that a container comes back after a reboot.

Read the [server guide](install-ubuntu-server.md), at least its step 12a, and
the [Tailscale guide](install-tailscale.md) first: this guide builds on them.
Every command runs on the server, over SSH (`ssh server`), except the test
from the workstation in section 4.

Every step ends with a check. Read-only commands come first, and nothing that
changes the machine runs until they match what you expect.

Before pasting a block that has `sudo` after its first line, run `sudo -v`
alone and type your password. In a new session, or 15 minutes after the last
`sudo`, a password prompt would take the lines pasted after it.

Placeholders used throughout; replace each one, angle brackets included:

- `<lan-ip>`: the server's address in the house's network, as in the server
  guide.
- `<server-name>`: the server's name in the tailnet, as in the Tailscale
  guide.
- `<service>`: a service's short name, such as `ntfy` (section 7).

Never commit addresses, names, tokens or topics to this repository. They go in
your private note, or in the server's own files.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| Services | They listen on 127.0.0.1 and are published only with Tailscale Serve | Docker sends published ports past the firewall: the address is what keeps them off the network | [ADR-004](../adr/ADR-004-compute-and-always-on-services-on-separate-hosts.md) |
| Where Docker comes from | Docker's own apt repository, with the Compose plugin; not Ubuntu's `docker.io` or its snap | It is the method Docker documents for Ubuntu, and it brings Docker's current releases | This guide |
| The daemon | Runs as root, Docker's default; rootless mode refused | Rootless mode limits what an escaped container can do, but complicates networking and storage; a few trusted services behind Tailscale do not need it | This guide |
| Default address of published ports | 127.0.0.1, in `/etc/docker/daemon.json`, on Docker's default network and on every network created later | A port published without an address stays on the server instead of opening on every interface | This guide |
| Who runs Docker | `sudo docker`; nobody joins the `docker` group | That group is root on the server, without a password | This guide |
| Container logs | Docker's `local` driver: at most 100 MB per container, compressed | The default driver, `json-file`, never deletes a line and can fill the SSD | This guide |
| Live restore | Off, Docker's default | Live restore keeps services running while Docker restarts, but an update to a new minor version, or one that skips releases, can leave them running out of Docker's control, and updates by hand do both. Off, every restart takes the same path as a reboot | This guide |
| Docker updates | By hand, with the server's `apt full-upgrade`; `unattended-upgrades` leaves them alone | Each one restarts Docker and every service with it: you choose when | This guide |
| Service data | `/srv/<service>`: its `compose.yaml`, its data folders and its `.env` | Everything that cannot be downloaded again is in one place, for the backups | This guide |

## 1. What you need

- The service host installed (server guide, through step 11) and in the
  tailnet (Tailscale guide, through section 6).
- The workstation at home, on the same network as the server and in the
  tailnet: it is the other computer of section 4's test.

**Check:** from the workstation, `ssh server` opens a session, and
`tailscale status` lists the server.

## 2. Install Docker from its repository

On the server. Read-only first:

```bash
lsb_release -cs                                   # noble
dpkg --print-architecture                         # amd64
command -v curl || echo "curl missing"            # if missing: sudo apt install curl
snap list docker 2>/dev/null || echo "no snap"    # no snap
ls /etc/apt/sources.list.d/                       # no docker.sources yet
sudo ss -ltnp                                     # what listens today; the check below compares with it
```

And the packages that Docker's install page names as conflicting, from Ubuntu
or from another source. The command must print nothing:

```bash
dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc 2>/dev/null
```

If it prints a package, or the `snap` line lists Docker, stop there: another
Docker is installed (*If something goes wrong*).

Docker publishes its own package repository, as Tailscale does: its signing
key goes into `/etc/apt/keyrings` and the repository's file into
`/etc/apt/sources.list.d`, so that apt installs and updates Docker like any
other package. These are the commands of Docker's install page. Run `sudo -v`
alone first, then the key:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Then the repository. The command prints the file it writes, which must say
`Suites: noble` and `Architectures: amd64`:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

The packages install inside tmux (server guide, step 12c), where a dropped
connection does not cut the install halfway. First:

```bash
tmux new -A -s admin
```

Then, inside tmux, the install, which asks before installing (answer `Y`):

```bash
sudo apt update && sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Docker starts as soon as it is installed, with its defaults. Section 3 changes
them before anything publishes a port.

**Check:**

```bash
gpg --show-keys /etc/apt/keyrings/docker.asc        # 9DC858229FC7DD38854AE2D88D81803C0EBFCD88, Docker Release (CE deb) <docker@docker.com>
sudo docker version --format '{{.Server.Version}}'  # 29.9.2 or later; never older than 28
sudo docker compose version                         # Docker Compose version v…
systemctl is-enabled docker                         # enabled: Docker starts with the machine
sudo docker run --rm hello-world                    # Hello from Docker!, and what it just did
sudo ss -ltnp                                       # the same list as before: Docker listens on no port of its own
```

The version matters: before 28.0, machines on the same local network could
reach ports published on 127.0.0.1
([moby/moby#45610](https://github.com/moby/moby/issues/45610)).

## 3. Published ports on 127.0.0.1, and logs that rotate

Docker reads its settings from `/etc/docker/daemon.json`, which does not
exist yet. Read-only first:

```bash
ls /etc/docker 2>/dev/null || echo "no folder"    # nothing, or no folder: there is no daemon.json
sudo docker info --format '{{.LoggingDriver}}'    # json-file, Docker's default
sudo docker network inspect bridge --format '{{index .Options "com.docker.network.bridge.host_binding_ipv4"}}'   # 0.0.0.0: every interface
```

Three settings:

- `ip`: the address a port gets when it is published without one, on Docker's
  default network, the one `docker run` uses when no network is named.
- `default-network-opts`: the same for every network created from now on.
  Compose creates one for each `compose.yaml`, which here means one for each
  service.
- `log-driver`: `local` keeps at most five files of 20 MB per container, and
  compresses the older ones. The default, `json-file`, never deletes a line.

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "ip": "127.0.0.1",
  "default-network-opts": {
    "bridge": {
      "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1"
    }
  },
  "log-driver": "local"
}
EOF
sudo dockerd --validate --config-file=/etc/docker/daemon.json    # configuration OK
```

`configuration OK` means Docker accepts the file. It does not check the
option's name inside `default-network-opts`: section 4's test does. Then apply
the file:

```bash
sudo systemctl restart docker
```

`default-network-opts` and `log-driver` apply only to what is created after
the restart: a network keeps its default address, and a container its log
settings, until they are created again. Nothing has been created yet, which is
why they go in now. `ip` also reaches the containers that already exist,
because Docker creates its default network anew at every start. For the same
reason, if `ip` ever leaves the file, the ports published on that network
without an address open on every interface at the next start. To change the
file later, keep a copy first (server guide, step 12a), validate it, and
restart Docker, which restarts every service with it.

**Check:**

```bash
systemctl is-active docker                        # active
sudo docker info --format '{{.LoggingDriver}}'    # local
sudo docker network inspect bridge --format '{{index .Options "com.docker.network.bridge.host_binding_ipv4"}}'   # 127.0.0.1
```

## 4. Test the ports from another computer

Three test containers, each a small web server (nginx) on its own port:

- `port-test-1`, on Docker's default network, published without an address:
  it tests `ip`.
- `port-test-2`, on a network created the way Compose creates one, published
  without an address: it tests `default-network-opts`.
- `port-test-3`, published with the address `0.0.0.0` written on purpose: open
  on every interface, as a service with a wrong line in its `compose.yaml`
  would be. It is the control, the proof that the test sees an open port when
  there is one, and it stays up only during the test.

On the server:

```bash
sudo docker run -d --rm --name port-test-1 -p 8081:80 nginx:alpine
sudo docker network create port-test
sudo docker run -d --rm --name port-test-2 --network port-test -p 8082:80 nginx:alpine
sudo docker run -d --rm --name port-test-3 -p 0.0.0.0:8083:80 nginx:alpine
```

The first one downloads the image. `--rm` removes each container when it
stops. If anything in this section goes wrong, stop the three first, with the
command at the end of the section, and then look for what you see in *If
something goes wrong*. Still on the server:

```bash
sudo ss -ltnp | grep -E ':808[123]'                            # 127.0.0.1:8081, 127.0.0.1:8082 and 0.0.0.0:8083, all docker-proxy
curl -s http://127.0.0.1:8081 | grep -o '<title>.*</title>'    # <title>Welcome to nginx!</title>
curl -s http://127.0.0.1:8082 | grep -o '<title>.*</title>'    # the same
sudo docker network inspect port-test --format '{{index .Options "com.docker.network.bridge.host_binding_ipv4"}}'   # 127.0.0.1
```

Then at the workstation, in a terminal of its own, not in the SSH session:

```bash
curl -s -m 5 http://<lan-ip>:8081 || echo unreachable                  # unreachable
curl -s -m 5 http://<lan-ip>:8082 || echo unreachable                  # unreachable
curl -s -m 5 http://<lan-ip>:8083 | grep -o '<title>.*</title>'        # <title>Welcome to nginx!</title>
curl -s -m 5 http://<server-name>:8081 || echo unreachable             # unreachable, through the tailnet too
curl -s -m 5 http://<server-name>:8082 || echo unreachable             # unreachable
curl -s -m 5 http://<server-name>:8083 | grep -o '<title>.*</title>'   # <title>Welcome to nginx!</title>
```

The control shows what ADR-004 prevents: a port open on every interface
answers in the tailnet without Serve, and in the house's network, to every
device on it.

Back on the server, stop the three:

```bash
sudo docker stop port-test-1 port-test-2 port-test-3
```

**Check:** on the server, ports 8081 and 8082 listened only on 127.0.0.1 and
answered there; from the workstation they were unreachable, through the
house's network and through the tailnet, while the control answered through
both.

## 5. Test a reboot

The server comes back on its own after a power cut and after its automatic
reboots at 04:00
([ADR-008](../adr/ADR-008-a-service-host-comes-back-on-its-own.md)), and its
services must come back with it. For a container, that takes Docker starting
with the machine (section 2's check) and a restart policy. One more test
container, with the policy every service will use:

```bash
sudo docker run -d --name reboot-test --restart unless-stopped -p 8081:80 nginx:alpine
sudo docker ps --format '{{.Names}}  {{.Status}}  {{.Ports}}'   # reboot-test  Up …  127.0.0.1:8081->80/tcp
```

Only if it is up, reboot:

```bash
sudo reboot
```

The reboot closes your session. Connect again a minute or two later, run
`sudo -v` alone, since it is a new session, and then:

```bash
sudo docker ps --format '{{.Names}}  {{.Status}}  {{.Ports}}'   # reboot-test  Up …  127.0.0.1:8081->80/tcp
curl -s http://127.0.0.1:8081 | grep -o '<title>.*</title>'     # <title>Welcome to nginx!</title>
sudo docker stop reboot-test
```

`unless-stopped` starts a container again after every reboot, unless you
stopped it yourself: then it stays stopped, reboots included, until you start
it.

**Check:** after the reboot, `reboot-test` was up by itself, on 127.0.0.1.

## 6. Clean up after the tests

Read-only first:

```bash
sudo docker ps -a         # reboot-test, Exited; no other container
sudo docker network ls    # bridge, host, none and port-test
sudo docker image ls      # hello-world and nginx:alpine
```

If they list that and nothing else, remove what the tests left:

```bash
sudo docker rm reboot-test
sudo docker network rm port-test
sudo docker image rm hello-world nginx:alpine
```

**Check:** `sudo docker ps -a` and `sudo docker image ls` list nothing under
their header line, and `sudo docker network ls` lists only Docker's own
networks: `bridge`, `host` and `none`.

## 7. Living with Docker

- **A service is a folder.** `/srv/<service>` holds its `compose.yaml`, the
  folders where it keeps its data, and its `.env`, with the values of this
  instance (tokens, topics), readable only by root (`sudo chmod 600 .env`).
  Nothing in an `.env` enters this repository. Docker's own folders,
  `/var/lib/docker` and `/var/lib/containerd`, hold the images and the
  containers, which `docker compose up` downloads and creates again: a backup
  needs `/srv`, not them. For the same reason, a service keeps its data in its
  folder, not in a Docker volume, which would live in `/var/lib/docker`.
- **Every port with its address.** A service's lines in its `compose.yaml`:

  ```yaml
  services:
    <service>:
      image: <image>:<version>
      restart: unless-stopped
      ports:
        - "127.0.0.1:<host-port>:<container-port>"
      volumes:
        - ./data:/data
  ```

  The daemon's default catches a forgotten address; writing it keeps the
  intent in the file, and holds on any Docker, configured or not.
- **Images by version, never `latest`.** An update is a line you change, and
  the version before it is the line you replaced.
- **`restart: unless-stopped` in every service,** so that it comes back after
  the 04:00 reboots and after a power cut (section 5).
- **No host, macvlan or ipvlan networks.** `network_mode: host` puts a
  container on the server's own interfaces, and a macvlan or ipvlan network
  puts it on the house's network with an address of its own. Docker's default
  address does not apply to them, and Docker writes no firewall rules for
  them: the program listens wherever it is configured to. A service guide that
  needs one says why, and how its program listens on 127.0.0.1 only.
- **The commands,** in the service's folder (`cd /srv/<service>`), always with
  `sudo`:

  ```bash
  sudo docker compose up -d             # starts the service, or applies a change to compose.yaml
  sudo docker compose ps                # its containers, their state and their ports
  sudo docker compose logs --tail 50    # its last lines of log; -f follows them
  sudo docker compose down              # stops it and removes its containers; its folders stay
  sudo docker system df                 # the space Docker takes, by images, containers and volumes
  ```

  Before changing a `compose.yaml`, keep a copy:
  `sudo cp compose.yaml compose.yaml.bak` (server guide, step 12a).
- **Updates.** Docker's packages come from Docker's repository, and
  `unattended-upgrades` installs only Ubuntu's security updates. Docker updates
  with the server's `sudo apt full-upgrade`, by hand (server guide, step 10).
  Each update restarts Docker, and every service with it, for a few seconds;
  they come back by their restart policy. Before a new minor or major version
  (29.10, 30), read its release notes.
- **Nobody joins the `docker` group.** Whoever can talk to Docker's socket is
  root on the server, without a password. `sudo` remembers your password for
  15 minutes in each terminal.
- **Firewall.** ufw stays off (Tailscale guide, section 10). Turned on, it
  would not filter published ports anyway: Docker routes them before ufw sees
  them, which is why the address 127.0.0.1 is what protects them. Docker
  writes its own iptables rules at every start: do not edit them, and do not
  write firewall rules with `nft`, which Docker does not support.

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 2 | The `dpkg --get-selections` command prints a package | Another Docker is installed, from Ubuntu or by hand. If `sudo docker ps -a` lists nothing you need, remove those packages with Docker's own command: `sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc \| cut -f1)`. Their data stays in `/var/lib/docker`. |
| 2 | `snap list docker` lists Docker | It was chosen among the snaps when the server was installed. If `sudo docker ps -a` lists nothing you need: `sudo snap remove docker`. |
| 2 | `apt update` says that Docker's repository is not signed, or `NO_PUBKEY` | The key did not download: repeat the key's three commands. |
| 2 | `Unable to locate package docker-ce` | The repository's file is wrong: `cat /etc/apt/sources.list.d/docker.sources` must say `Suites: noble` and `Architectures: amd64`. Write it again, then `sudo apt update`. |
| 2, any | `permission denied` and `docker.sock` | The command ran without `sudo`: by design, nobody is in the `docker` group. |
| 3 | `dockerd --validate` prints `unable to configure the Docker daemon with file` | A typo in `daemon.json`; the message names the key. Write the file again. |
| 3 | `Job for docker.service failed` after the restart | `sudo journalctl -u docker -n 30 --no-pager` says why, usually a typo in `daemon.json`: write the file again, validate it, and restart. |
| 4 | `port is already allocated`, or `address already in use` | Stop the test containers that started (`sudo docker stop port-test-1 port-test-2 port-test-3`). Something else uses that port: `sudo ss -ltnp \| grep 808` shows what. Use other ports for the test. |
| 4 | `ss` shows `0.0.0.0` or `[::]` for 8081 | Stop the three test containers at once. Docker is not using `daemon.json`: repeat section 3's check. |
| 4 | `ss` shows `0.0.0.0` or `[::]` for 8082 only | Stop the three test containers at once. The option name inside `default-network-opts` is wrong, or the `port-test` network was created before section 3's restart. Compare the file with section 3, restart Docker, remove the network with `sudo docker network rm port-test`, and create it again. |
| 4 | From the workstation, 8081 or 8082 shows nginx's title | The port is open on the network: stop the three test containers at once, and do not go on until section 3's check passes. |
| 4 | From the workstation, the control (8083) does not answer either | Stop the three test containers first. The test cannot see an open port, so the other results prove nothing. Check the address (`ssh server-lan` uses the same `<lan-ip>`) and the name (`tailscale status`), then start section 4 again; its `network create` line then says that `port-test` already exists, which is fine. |
| 5 | After the reboot, `reboot-test` is not listed | `systemctl is-enabled docker` must print `enabled`. `sudo docker ps -a` shows the container's state, and `sudo docker inspect reboot-test --format '{{.HostConfig.RestartPolicy.Name}}'` must print `unless-stopped`. |

## Next

ntfy, the first service, in its own guide: its folder in `/srv/ntfy`, its port
on 127.0.0.1, and Tailscale Serve to publish it in the tailnet. Then
healthchecks (the host heartbeat), Forgejo and its runner, and the experiment
tracker.

## References

- Docker, *Install Docker Engine on Ubuntu*:
  https://docs.docker.com/engine/install/ubuntu/
- Docker, *Linux post-installation steps* (the `docker` group, starting with
  the machine, the default log driver):
  https://docs.docker.com/engine/install/linux-postinstall/
- Docker, *Docker daemon attack surface* (why the `docker` group is root):
  https://docs.docker.com/engine/security/#docker-daemon-attack-surface
- Docker, *Rootless mode* (what this guide refuses):
  https://docs.docker.com/engine/security/rootless/
- Docker, *Port publishing and mapping* (the default address, and releases
  before 28.0): https://docs.docker.com/engine/network/port-publishing/
- Docker, *Bridge network driver* (the default host binding address):
  https://docs.docker.com/engine/network/drivers/bridge/
- Docker, *Packet filtering and firewalls* (ufw, iptables and nftables, and
  no rules for host, macvlan or ipvlan networks):
  https://docs.docker.com/engine/network/packet-filtering-firewalls/
- Docker, `dockerd` reference (`daemon.json`, `--validate`,
  `default-network-opts`): https://docs.docker.com/reference/cli/dockerd/
- Docker, *Local file logging driver*:
  https://docs.docker.com/engine/logging/drivers/local/
- Docker, *Live restore*: https://docs.docker.com/engine/daemon/live-restore/
- Docker, *Start containers automatically* (restart policies):
  https://docs.docker.com/engine/containers/start-containers-automatically/
- Docker, *containerd image store* (where images live):
  https://docs.docker.com/engine/storage/containerd/
- Docker, *Compose file reference*, services (`ports`, `restart`):
  https://docs.docker.com/reference/compose-file/services/
- Docker, *Networking in Compose* (one network for each `compose.yaml`):
  https://docs.docker.com/compose/how-tos/networking/
- Docker Engine 29 release notes:
  https://docs.docker.com/engine/release-notes/29/
- Moby issue 45610, ports published on localhost reachable from the local
  network: https://github.com/moby/moby/issues/45610
