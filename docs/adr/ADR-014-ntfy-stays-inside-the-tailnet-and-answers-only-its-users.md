# ADR-014 - ntfy stays inside the tailnet, and answers only its own users

## Status

Accepted on 2026-11-03, while writing the
[ntfy guide](../guides/install-ntfy.md). ntfy is the first service published
to the tailnet, and the first one that a project's code will call.

## Context

- The platform has to tell the phone how a long training goes, when it ends
  and when it fails (roadmap).
  [ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md) put
  ntfy on the service host without weighing other notifiers.
  [ADR-007](ADR-007-liveness-is-watched-from-outside.md) leaves liveness to
  healthchecks.io, because a notifier at home dies with the house.
- ntfy, as of November 2026 (2.28.0, released on 2026-08-27):
  - it is open source, and publishing to it is one HTTP request;
  - its Android app subscribes to topics on any server. With a server of
    one's own, the app does not use Google's push service: it keeps a
    connection open with the server. Only ntfy.sh, the project's public
    server, relays through Google;
  - on a public server, a topic's name is its only lock: whoever knows it
    reads and publishes;
  - it can refuse every request without a user, and give each user a
    password or tokens, and access to each topic.
- Tailscale Serve publishes a local port to the tailnet, as of November 2026:
  - over HTTPS, with a certificate whose name, the machine's and the
    tailnet's, goes to public certificate logs
    ([Tailscale guide](../guides/install-tailscale.md), section 5);
  - or over plain HTTP. Traffic between devices in the tailnet is encrypted by
    Tailscale either way;
  - it passes each device's tailnet address to the service, in
    `X-Forwarded-For`.
- The phone runs Android, where a name in the tailnet can fail to resolve
  (Tailscale guide, section 8).

## Decision

**ntfy runs in Docker on the service host, and is reached only inside the
tailnet, because a notification must reach the phone anywhere without
publishing anything to the internet.** It listens on 127.0.0.1
([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)), and
Tailscale Serve publishes it to the tailnet.

**Over plain HTTP, because Tailscale already encrypts every connection, and a
certificate would publish the names of the server and of the tailnet.**

**It refuses every request without a user, and each device gets its own user,
with only the access it needs:** the phone reads, with a password; the
workstation publishes, with a token. This is the second lock of the services:
being in the tailnet is not enough. Every service published to the tailnet
later has its own login too.

**The phone receives through its own connection to the server, with
Tailscale always on.**

**Projects reach it through three values, `NTFY_URL`, `NTFY_TOPIC` and
`NTFY_TOKEN`, kept on the workstation in a file that only its owner reads,**
so that a project calls no code of the platform's, and runs without it.
`notify` reads them, and so will the long runs.

**A message carries a status, a run name and numbers, never paths, study
identifiers or patient data:** ADR-007's rule for pings, extended to
notifications.

**Refused: ntfy.sh, the public server,** because a topic's name would be the
only lock, and every message would pass through a third party.

**Refused: a notifier run by a third party,** such as Pushover, a Telegram bot
or email, for the same reason.

**Refused: HTTPS with Tailscale's certificate,** for the names it publishes,
and **Tailscale Funnel,** which would publish ntfy to the internet.

**Refused: the relay through ntfy.sh and Google** (`upstream-base-url`). Only
an iPhone needs it, and it sends a notice of each message through both.

## Consequences

- The [ntfy guide](../guides/install-ntfy.md) installs it from
  `config/ntfy/compose.yaml` and `config/ntfy/server.yml`, and puts
  `scripts/notify.sh` on the workstation.
- A phone out of the tailnet hears nothing until it is back; the server keeps
  messages for 48 hours.
- Every service published to the tailnet from now on says, in its guide, how
  its login works.
- A training's notifications (roadmap, step 2) use the same three values.

## Trade-off

The phone keeps Tailscale on, and the ntfy app keeps a connection and a
notification that stays, which costs some battery. Notifications die with
the house, like everything on the service host, which is why liveness stays
with healthchecks.io. Plain HTTP leaves the encryption to Tailscale alone.

## Revisit when

The phone becomes an iPhone, someone else needs the notifications, ntfy
changes its license or stops being maintained, or a notification has to
reach a device outside the tailnet.
