# ADR-012 - SSH goes over Tailscale with each computer's own key, not with Tailscale SSH

## Status

Accepted on 2026-10-25, when the Tailscale guide had to choose how computers
log in to the hosts.

## Context

[ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md) puts
every service behind Tailscale. SSH works without it today: OpenSSH listens
on the LAN, keys only, and each computer has its own key, registered in GitHub
and imported on each host (server guide, appendix A).

Tailscale offers its own SSH server, Tailscale SSH (Linux and macOS only),
which logs in with the tailnet's identity instead of a key. Facts as of
Tailscale 1.104.2, October 2026:

- **Check mode by default.** The default policy runs it in check mode: a new
  browser sign-in every 12 hours, a period that only the paid plans can
  change.
- **Clients that cannot wait.** In check mode, VS Code's Remote-SSH hangs until
  it times out, and scripts, `scp` and `rsync` wait for someone to finish the
  browser check, for up to 30 minutes.
- **Accept mode.** It drops the browser check, and then the Tailscale account
  alone opens every host, as root too under the default rule.
- **Restarts.** Every Tailscale update restarts its daemon, and that ends
  Tailscale SSH sessions; updates are automatic by default.
- **Port 22.** It takes over port 22 only for traffic that arrives over the
  tailnet; SSH from the LAN keeps reaching OpenSSH.

## Decision

**SSH keeps OpenSSH and each computer's own key, over the LAN and over the
tailnet alike, because then a login needs two things: being in the tailnet,
and holding a key that the host accepts.** Taking over the Tailscale account
is not enough, and neither is a stolen key without the tailnet, from outside
the house.

**Tailscale carries the traffic and gives each host a name that works from
anywhere.**

**Refused: Tailscale SSH in check mode,** for the browser sign-in every 12
hours, fixed on the Personal plan, and the hanging VS Code.

**Refused: Tailscale SSH in accept mode,** because the Tailscale account would
become the only lock on both hosts.

## Consequences

- Besides Tailscale, a new computer needs its own key, that key in GitHub, and
  `ssh-import-id` on each host, run from a computer that already connects. The
  [Tailscale guide](../guides/install-tailscale.md) lists the steps.
- On each computer, `server` names the host in the tailnet, and `server-lan`
  keeps its LAN address: the way in at home when Tailscale is out of reach.
- Retiring a computer means removing it from the tailnet and its key from
  GitHub and from each host.

## Trade-off

More steps per computer than signing in to Tailscale, and a new computer
depends on one that already connects, or on the host's own screen, to get its
key imported. `ssh-import-id` imports every key in the GitHub account, so that
account matters too: a key added there by someone else would come in at the
next import, which is why every import ends with a look at the list of
fingerprints.

## Revisit when

Tailscale SSH works with VS Code in check mode, the check period can be
changed on the plan in use, or the number of computers makes a key per
computer a burden.
