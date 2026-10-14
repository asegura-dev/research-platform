# ADR-005 - Forgejo, not GitLab, for private code

## Status

Accepted on 2026-10-09, once the mini PC's hardware was known.

## Context

Private repositories need more than storage: CI for tests and linters, issues
with a board, and a web interface for review. They live on the mini PC
([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)): 4
cores, 4 threads, 16 GB.

- **GitLab** documents that it can run with at least 8 GB of memory in some
  cases, and recommends four Puma workers for 4 cores and 8 GB. It would take
  half the memory and every core before anything else ran.
- **Forgejo** descends from Gitea, whose documentation considered 2 cores and
  1 GB enough for small teams. It has kanban boards and its own CI, Forgejo
  Actions, whose workflows resemble GitHub Actions without being compatible
  with them.
- **A bare repository over SSH** stores code and gives none of the rest.

## Decision

**Forgejo on the mini PC, with its runner on the same host and one job at a
time, because it covers CI, issues, boards and review within the mini PC's
means and leaves room for the other services.**

**Refused: GitLab** (too heavy for this host) **and a bare repository** (no CI,
issues or web interface).

## Consequences

- CI workflows of private repositories are written for Forgejo Actions.
- Forgejo's database and repositories are irreplaceable data, so they enter the
  backup plan.

## Trade-off

Public repositories run their CI on GitHub
([ADR-006](ADR-006-public-repositories-on-github-private-on-forgejo.md)), so the
platform keeps two CI dialects, and a workflow cannot always move between them
unchanged. Forgejo is also one more service to update and secure.

## Revisit when

Jobs wait in the runner's queue longer than the work can afford, or
GitHub-compatible workflows become a requirement.
