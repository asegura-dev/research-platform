# ADR-006 - Public repositories on GitHub, private ones on Forgejo

## Status

Accepted on 2026-10-09, together with the names of the first repositories.

## Context

Forgejo is reachable only inside the tailnet
([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)), so a
repository marked public there is invisible to everyone else. Forgejo can push
a mirror to GitHub, but it force-pushes: the GitHub copy becomes read-only,
anything pushed to it directly is lost, and it shows the code without its CI.

## Decision

**A repository lives where its readers are: public ones on GitHub with their
CI, private ones on Forgejo.** When a private repository is published, it
moves.

**The first repositories:**

| Repository | Visibility | Home |
|---|---|---|
| `research-platform` (this one) | Public | GitHub |
| `run-signals` | Public | GitHub, released on PyPI |
| `petct-kd-segmentation` | Private until the thesis is published | Forgejo, then GitHub |
| `petct-kd-segmentation-thesis` | Private | Forgejo |

**Public repositories publish the design, never the instance.** Hostnames,
tailnet addresses, ntfy topics, ping URLs and tokens stay out of git. A public
repository ships templates (`*.example.*`), and the real values live in files
that git ignores.

**A published project must install without this platform.** That is why
`run-signals` goes to PyPI: a dependency that points at a personal server
breaks when the server does.

**Refused: everything on Forgejo with a mirror to GitHub,** because of the
force-push behaviour described above.

## Consequences

- `.gitignore` ignores local configuration by its shape (`.env*`, `*.local.*`,
  `/local/`), not by one predicted file name.
- `run-signals` needs its name confirmed as free on PyPI before its first
  release.
- Every commit to a public repository is public for good, history included.

## Trade-off

Two homes and two CI dialects, and a private repository that becomes public has
to change home. A secret committed once to a public repository stays in its
history even after it is deleted; the protection is reviewing every commit
before it is pushed, plus secret scanning.

## Revisit when

Forgejo becomes reachable from the internet, or GitHub stops being where the
readers are.