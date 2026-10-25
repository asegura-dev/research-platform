# ADR-011 - The service host runs without Secure Boot, because its firmware offers only a test key

## Status

Accepted on 2026-10-25, after the first run of the server install guide found
that the service host's firmware holds no Secure Boot keys. It supersedes, for
that host, the Secure Boot point of
[ADR-008](ADR-008-a-service-host-comes-back-on-its-own.md); the rest of
ADR-008 stands.

## Context

ADR-008 kept Secure Boot on, with the 2023 Microsoft certificates applied,
because the 2011 ones expired in June 2026. What the service host's firmware
turned out to be, on 2026-10-25:

- **A generic firmware.** An AMI firmware, version 5.16, dated 2025-10-27,
  whose manufacturer and product fields read `Default string`. It does not
  name its vendor, so no vendor firmware update or support channel is known.
- **No keys in use.** The firmware is in Setup Mode: PK, KEK, db and dbx do
  not exist, and `mokutil --sb-state` reports `SecureBoot disabled` and
  `Platform is in Setup Mode`. Ubuntu was installed and runs in that state. A
  check in the install guide hid it: `mokutil --db | grep 'Subject:'` prints
  nothing both when db is empty and when it lacks the 2023 certificates.
- **Factory keys that stop at a test key and at 2011.** The keys its setup
  can install are: as platform key, `DO NOT TRUST - AMI Test PK`, a test key
  shipped by mistake (PKfail, CVE-2024-8105; at least one such key's private
  half has leaked); as KEK, `Microsoft Corporation KEK CA 2011`; in db,
  `Microsoft Corporation UEFI CA 2011` and `Microsoft Windows Production PCA
  2011`. None of the 2023 certificates.
- **Nothing for fwupd to do.** fwupd 2.0.20 offers no certificate update: with
  KEK and db empty, there is nothing to update.
- **What Secure Boot would have added here.** The disk is not encrypted
  (ADR-008), so anyone with physical access reads it with or without Secure
  Boot. Services are reached only through Tailscale
  ([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)),
  and the host holds no images or patient data. What remains is protection
  against malware that, having gained root, hides in the boot loader or the
  kernel.

## Decision

**The service host runs without Secure Boot, because the only platform key
its firmware offers is a test key, and its factory certificates stop at
2011.** Installing them would turn on a check whose root key may be public,
still without the 2023 certificates that ADR-008 asked for.

**Refused: installing the factory keys and turning Secure Boot on.** It
would block casual tampering, but anyone holding the leaked test key, if this
is that key, could sign their own boot loader; and the 2023 certificates
would still depend on an update for a firmware whose vendor is unknown.

**Refused for now: replacing the test key with keys made for this host.** It
is the only way to a Secure Boot whose root is trusted, but a mistake in it
can leave the host unable to start, and the threat it covers is narrow here.

## Consequences

- Step 8 of the
  [server install guide](../guides/install-ubuntu-server.md) gained the case of
  a firmware without keys, and its checks now show `is empty`.
- The certificate rollout no longer affects starting this host: the firmware
  checks no signature, so boot loaders signed with the 2023 CA start as well.
- The kernel runs without lockdown: root can load unsigned kernel modules.
  What protects the host is security updates installed automatically, no
  service reachable outside Tailscale, the accounts behind Tailscale and
  GitHub, and backups that make a reinstall cheap.

## Trade-off

Malware that gains root could settle below the operating system, in the boot
loader or in the kernel, survive reinstalling packages, and hide from the
tools that would find it; only a reinstall from the guide clears it. ADR-008
wanted that door closed, and it is open.

## Revisit when

The host is replaced, a firmware update for it brings a vendor platform key
or the 2023 certificates, it starts storing sensitive data, or replacing the
test key with keys made for this host becomes worth its risk.
