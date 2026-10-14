# ADR-007 - Liveness is watched from outside, because the house can go dark

## Status

Accepted on 2026-10-09, as the answer to "what tells me the platform died
without warning?".

## Context

ntfy on the mini PC can announce what happens on the platform, but not its own
death: a power cut, a hang or a lost internet connection silences the notifier
together with what it watches. Both hosts share the same power and internet
([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)), so a
watcher on either one fails in the same event.

A dead man's switch inverts the signal: the platform pings periodically, and
the absence of pings is the alarm. healthchecks.io offers this as a service,
with email alerts; its free plan includes 20 checks (as of October 2026).

## Decision

**healthchecks.io watches the platform from outside, because a watcher at home
dies with the house.** This is the platform's one deliberate exception to
running everything on owned hardware.

**Two levels of heartbeat:**

- **Per host.** A system timer pings every few minutes; silence means the host
  or its connection is down.
- **Per run.** A training run signals its start, pings every few epochs, and
  reports success or failure. A run that started and does not report success
  within the grace time counts as failed. The period and the grace time come
  from the epoch times that the smoke test measures.

**A ping carries a status and an epoch number, nothing else.** The service
stores the body of every ping, so no paths, study identifiers or patient data
travel in one.

**Ping URLs are credentials.** Anyone holding one can report a false success and
silence a real failure.

**Refused: a self-hosted instance at home,** for the reason above.

## Consequences

- Each host and each kind of run gets its own check. Ping URLs live in
  environment variables, outside git.
- Training code reaches healthchecks through a notification port with a null
  adapter (`run-signals`), so it runs anywhere without the service.
- The per-run check must not raise false alarms between runs; how is decided in
  the guide for operating long runs.

## Trade-off

A third party learns when the platform is up and how its runs progress, and the
alarm depends on that service being available and on email arriving. Its plans
and limits can change.

## Revisit when

The free plan stops covering the checks the platform needs, or a watcher away
from home becomes available (for example, a machine at another location).
