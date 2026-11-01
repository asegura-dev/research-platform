# ADR-013 - GitHub, not a forge at home, for private code

## Status

Accepted on 2026-10-31, before the thesis's code repository was created, when
the order of the platform's remaining work was revised. It supersedes
[ADR-005](ADR-005-forgejo-not-gitlab-for-private-code.md), and
[ADR-006](ADR-006-public-repositories-on-github-private-on-forgejo.md) where
it puts private repositories on Forgejo; the rest of ADR-006 stands.

## Context

ADR-005 weighed only options at home: GitLab, Forgejo and a bare repository.
ADR-006 refused only "everything on Forgejo with a mirror". Neither weighed
private repositories on GitHub, which already holds the public ones. Facts as
of 2026-10-31:

- **What GitHub gives private repositories.** Its free plan has unlimited
  private repositories with issues, projects and pull requests, and 2,000
  Actions minutes a month for them. Pro raises the minutes to 3,000 and adds
  protected branches and wikis on private repositories; GitHub Education
  gives it free to verified students.
- **What a forge at home costs.** One more service to update and secure
  (ADR-005's own trade-off), its data in the backups, a runner that executes
  workflow code beside the host's secrets, two CI dialects, and a move to
  GitHub when a repository is published (ADR-006).
- **What home would not add.** A stolen service host exposes what it stores
  ([ADR-008](ADR-008-a-service-host-comes-back-on-its-own.md)), on a disk
  without encryption and a firmware without Secure Boot
  ([ADR-011](ADR-011-the-service-host-runs-without-secure-boot.md)).
- **What GitHub already holds.** The public repositories, their CI, and the
  SSH keys that every host imports
  ([ADR-012](ADR-012-ssh-over-tailscale-with-a-key-per-computer.md)).
- **Its terms on training.** GitHub does not use the content of private
  repositories at rest to train models. Since 2026-04-24 it trains on Copilot
  interaction data (inputs, outputs, code snippets and their context) from
  Copilot Free, Pro and Pro+ users who have not opted out, including what
  Copilot sees while it is used in a private repository.
- **Its secret scanning.** On a personal account it covers public
  repositories only, with push protection on by default, and it recognises
  token formats, not instance data.

## Decision

**Private repositories live on GitHub too, with their CI on GitHub Actions,
because GitHub already gives what ADR-005 asked of a forge, and a forge at
home would load the least protected host with a service, a runner and
backups, for confidentiality that host cannot give.** A repository that is
published changes its visibility, not its home.

**Refused: Forgejo on the service host,** for the costs above.

**Refused: another hosted forge,** because it adds a second account and a
second CI dialect for nothing GitHub lacks.

**Refused: a bare repository on the service host,** because it gives no CI,
issues or review, as ADR-005 found.

## Consequences

- Code hosting and CI leave the service host, which keeps ntfy
  ([ADR-004](ADR-004-compute-and-always-on-services-on-separate-hosts.md)).
- Every workflow is written for GitHub Actions: one CI dialect. Tests that
  need a GPU still run by hand on the workstation; no self-hosted runner is
  planned.
- The account's setting that lets GitHub train on Copilot interaction data is
  off (checked on 2026-10-31), and is checked again at each maintenance.
- Private repositories keep the rules of public ones: no instance data, and
  the same guard against it ([roadmap](../roadmap.md)), because publishing a
  repository publishes its whole history.
- The private repositories named in ADR-006 are created on GitHub, as
  private.
- The README's principle on outside services is restated: GitHub holds
  private code by choice, not because the job cannot be done at home.

## Trade-off

A company holds the unpublished thesis and its code under terms it can
change, and whoever takes over the account can read them, so the account's
second factor and recovery codes become part of the platform's security.
What is not in git (issues, review comments, boards) lives only on GitHub,
although every clone holds the code's full history. Leaving costs a
migration: Forgejo imports a GitHub repository with its issues, labels,
milestones, releases and wiki.

## Revisit when

GitHub's terms let it use the content of private repositories at rest, or its
opt-out stops covering what Copilot sees in them; those terms change in
public, in the `github/site-policy` repository. Also when private
repositories or their CI stop fitting in the free plan, or in Pro while the
education benefit lasts; when the university, a data agreement or a
publisher requires the code off third-party services; or when a test needs a
GPU on every push, because a runner on the workstation would bring back the
isolation question that this record avoids.
