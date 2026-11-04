# Set up the instance-data guard in a clone

> **Scope:** a clone of this repository, on a computer where you commit. At
> the end, Git refuses a commit that carries instance data, that computer has
> its list of your instance's values, and GitHub runs the same check at every
> push. Section 2 is repeated in every clone, and section 3 on every computer.
> The thesis repositories take the guard when they are created.

> **Status:** written on 2026-11-01, and first run the same day on the
> workstation, sections 1 to 5: the list was generated as section 3 shows,
> every test of section 4 passed, the guard's own commit went through its
> hooks, and the workflow's first run on GitHub was green. Revised from that
> run: section 3 generates most of the list, and section 2 shows the hooks'
> mode as Ubuntu prints it.

This repository publishes the design of the platform, never its instance
([ADR-006](../adr/ADR-006-public-repositories-on-github-private-on-forgejo.md)):
no host names, addresses, notification topics, ping URLs, tokens or hardware
identifiers. A private repository follows the same rule, because publishing it
publishes its whole history
([ADR-013](../adr/ADR-013-github-not-a-forge-at-home-for-private-code.md)).

The guard holds that rule in three places, with one script,
`scripts/check-instance-data.py`:

- **Before each commit, on your computer.** Two Git hooks check the lines a
  commit adds, the names of its files, its author's address and its message.
  This is the check that matters: once a commit reaches a public repository,
  it is public for good.
- **At each push, on GitHub.** A workflow checks every commit of every branch,
  in case one was made where the hooks were off, or on GitHub's website, which
  runs no hooks. The same workflow checks every relative link and anchor in
  the Markdown files, with `scripts/check-links.py`.
- **By hand, before a private repository goes public,** over its whole history
  (section 6).

The script recognises instance data in two ways:

- **By its shape:** an address in a private range or in one of Tailscale's
  ranges, a name under `ts.net`, a MAC address, an SSH host fingerprint or
  public key, a GPU's UUID, a disk's EUI, any other UUID or long hexadecimal
  string, a BitLocker recovery key, a Tailscale, GitHub or ntfy token, a
  healthchecks.io ping URL, an ntfy.sh topic, an e-mail address.
- **By your instance's own values,** which no shape can know, such as each
  host's name. You list them on each computer, outside every repository
  (section 3).

GitHub's secret scanning does not cover this: on a personal account it reads
public repositories only, and it recognises tokens, not names or addresses.

A finding names the place and the rule, never the value, so that a log on
GitHub does not publish it again.

Every step ends with a check. Read-only commands come first, and nothing that
changes the clone runs until they match what you expect.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| What a commit is checked for | Instance data in the lines it adds, the names of its files, its message and its author's address | Each of them stays in a public repository's history | [ADR-006](../adr/ADR-006-public-repositories-on-github-private-on-forgejo.md) |
| Author's address | One of GitHub's noreply addresses | Every commit carries an address, and a personal one is instance data | This guide |
| How instance data is recognised | By its shape, and by a list of your instance's own values | A shape cannot know a host's name; the list can | This guide |
| Where the list lives | `~/.config/research-platform/instance-values.txt`, on each computer, outside every repository | One list serves every clone on that computer, and no `git add` can take it | This guide |
| What the list holds | Identifiers: names, addresses, your personal address; never secrets | A secret in a plain file is one more place to steal it from, and the shapes already catch tokens and recovery keys | This guide |
| Public values that look like instance data | Allowed one by one in `scripts/instance-data-allow.txt`, each with what it is | A vendor's key fingerprint or a dataset's checksum is public on purpose, and an exception without a reason is a hole | This guide |
| How the hooks run | `core.hooksPath` set to `.githooks`, once per clone; the script in Python, with nothing to install | Git takes no hooks from a clone by itself, and Ubuntu comes with Python | This guide |
| On GitHub | The whole history at every push, and every relative link and anchor; `actions/checkout` pinned to a commit | A short history takes seconds to read, and a pinned action cannot change under the workflow | This guide |
| What a finding prints | The place and the rule, never the value; on GitHub, not even a file's name | A workflow's log in a public repository is public too | This guide |

## 1. What you need

- A clone of this repository, on `main`, with the commit that brought the
  guard. Every command of this guide runs in the clone's folder.
- Git, and Python 3.8 or later. Ubuntu 24.04 has both.
- Your private note: section 3 copies values from it.

```bash
git status -sb                    # ## main...origin/main, and nothing else
ls .githooks scripts              # commit-msg and pre-commit; the guard's three files
python3 --version                 # Python 3.8 or later
```

**Check:** the three outputs match.

## 2. Turn the hooks on in this clone

Git runs the hooks in `.githooks` only when the clone says so, in its own
configuration. That setting is not part of the repository: every clone needs
it once, and a new clone of the same repository needs it again.

```bash
ls -l .githooks                   # commit-msg and pre-commit, both with x: -rwxrwxr-x on Ubuntu
git config core.hooksPath         # nothing yet
```

Both hooks need their `x`: Git ignores a hook without it. Then:

```bash
git config core.hooksPath .githooks
git config core.hooksPath         # .githooks
```

**Check:** both hooks show `x`, and the last line prints `.githooks`. Git looks
for the hooks from the top of the clone, so a commit from any of its folders
runs them.

## 3. List your instance's values on this computer

The list lives in `~/.config/research-platform/instance-values.txt`: one value
per line, and a line that starts with `#` is a comment. Every clone on this
computer uses it, and no `git add` can take it, because it is outside every
repository. Case does not matter.

What goes in:

- each host's and each computer's name;
- the tailnet's name;
- the hosts' addresses, in the house and in the tailnet (their shapes are
  caught already; listing them costs nothing);
- the name of the house's Wi-Fi network;
- your personal e-mail address;
- any other value that a guide sends to your private note and that is not a
  secret.

What stays out:

- **Secrets:** tokens, passwords, recovery keys, ping URLs. Their shapes are
  caught, and a secret in a plain file is one more place to steal it from.
- **What is public on purpose:** your name, your GitHub account, the
  repositories' names, hardware models and versions. A value in the list is
  refused everywhere, these included.
- **Values shorter than four characters:** they would match too much; the
  script skips them and says so.

Create the file, readable by you only:

```bash
mkdir -p ~/.config/research-platform
chmod 700 ~/.config/research-platform
touch ~/.config/research-platform/instance-values.txt
chmod 600 ~/.config/research-platform/instance-values.txt
```

On the workstation, this block writes most of the list from what the computer
already knows: each device's name in the tailnet, the tailnet's name, the
server's and the workstation's addresses in the house, and the Wi-Fi network.
It adds to the end of the file and prints only how many values the file has,
so no value shows on the screen:

```bash
F=~/.config/research-platform/instance-values.txt
{
  echo "# devices: their names in the tailnet"
  tailscale status --json | python3 -c 'import json, sys; s = json.load(sys.stdin); print("\n".join(p["DNSName"].split(".")[0] for p in [s["Self"], *(s.get("Peer") or {}).values()] if p.get("DNSName")))'
  echo "# the tailnet"
  tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["CurrentTailnet"]["MagicDNSSuffix"])'
  echo "# addresses in the house: the server, then this computer"
  ssh -G server-lan | awk '/^hostname /{print $2}'
  hostname -I | tr ' ' '\n' | grep -E '^[0-9.]+$' | grep -v '^100\.'
  echo "# the Wi-Fi network"
  nmcli -t -f active,ssid dev wifi | awk -F: '$1 == "yes" {print $2}'
} >> "$F"
grep -vc '^#' "$F"                # how many values the list has
```

Then open the list, add your personal e-mail address on a line of its own, and
delete any device name that is a common word, such as `localhost`: the guard
would refuse that word in every text. On another computer, copy the list from
the workstation, or type it.

```bash
nano ~/.config/research-platform/instance-values.txt
```

Ctrl+O and Enter save; Ctrl+X leaves. An editor keeps the values out of the
shell's history, where a command line with a value would stay.

Then pass the list through the script. Each value must be found, and the
output shows no value:

```bash
ls -l ~/.config/research-platform/instance-values.txt     # -rw-------, owned by you
python3 scripts/check-instance-data.py --stdin < ~/.config/research-platform/instance-values.txt
```

**Check:** every value of the list appears as `instance value (line N of your
list)`, and no line says `shorter than 4 characters`. An address may also
appear under the rule of its shape, `private-ipv4` or `tailnet-ipv4`.

## 4. Test that the guard refuses

Three tests: the script on a line made up as it runs, so that no address is
written in this guide; an empty commit whose message carries that line, which
the hooks must refuse; and this repository's whole history.

```bash
printf 'the server is at 192.168.%s\n' 1.20 | python3 scripts/check-instance-data.py --stdin   # stdin:1: private-ipv4
printf 'nothing to find here\n' | python3 scripts/check-instance-data.py --stdin             # nothing
```

```bash
git log --oneline -1
git commit --allow-empty -m "test $(printf '192.168.%s' 1.20)"   # 1 finding(s). Nothing was committed.
git log --oneline -1                                             # the same commit as before
```

```bash
python3 scripts/check-instance-data.py --history                 # nothing
```

**Check:** the made-up line is found and the clean one is not; the test commit
is refused, so both `git log` lines show the same commit; and the history
prints nothing.

## 5. The check on GitHub

`.github/workflows/checks.yml` runs at every push and pull request, with
read-only access to the repository. Nothing needs to be set up on GitHub.

After the first push that brings it, open the repository on GitHub, then
*Actions*: a run of `checks` appears for the push, and turns green after a
minute or two. The same mark shows next to the latest commit on the
repository's page.

A run that fails names its step, *No instance data in any commit* or *Every
relative link and anchor resolves*, and the step's log names the commit or the
file, and the rule.

**Check:** the run of the push is green.

## 6. Before a repository goes public

A private repository becomes public with every commit it has. Before changing
its visibility, check its whole history, from its own clone:

```bash
python3 scripts/check-instance-data.py --history                 # nothing
```

A repository without the guard can use this clone's script: from the folder of
that repository's clone, run it with its full path, such as
`python3 ~/src/research-platform/scripts/check-instance-data.py --history`.

**Check:** nothing is printed. A finding in a history is not fixed by a new
commit, because the value stays in the old one. Taking it out means rewriting
that history, which is a plan of its own: the repository stays private until
then.

## 7. Living with the guard

- **When it stops a commit,** nothing was committed. Each finding names the
  file and line, or the line of the message, and the rule. Change the line:
  a placeholder in the text, and the value in your private note. Then
  `git add` and commit again.
- **A value that is public on purpose,** such as a vendor's key fingerprint or
  a dataset's checksum, goes in `scripts/instance-data-allow.txt`, with a
  comment that says what it is and where it appears, in a commit of its own.
- **`git commit --no-verify` skips both hooks.** It has no use in these
  repositories: a commit that the guard refuses needs its text or the guard
  fixed, not skipped.
- **A finding on GitHub** means the value is public already, in the commit
  that GitHub names. A new commit does not take it back, and a clone or a
  cache may hold it. A secret is treated as disclosed and replaced: a token
  revoked, a ping URL regenerated. An identifier is written down in your
  private note, with the date it was published.
- **A new computer** needs section 3 once; **a new clone**, section 2.
- **Binary files,** such as images and PDFs, are not read; the pre-commit hook
  names each one it skips. Look at them before committing: a screenshot can
  show a host's name.

## If something goes wrong

| Section | What you see | What to do |
|---|---|---|
| 1, 2 | `ls` cannot find `.githooks` or `scripts` | The clone is older than the guard: `git pull`. |
| 2 | The hooks show no `x`, such as `-rw-rw-r--` | Git ignores them: `chmod +x .githooks/commit-msg .githooks/pre-commit`. If `git status` then lists them as modified, the repository had lost their mode: commit that change. |
| 3 | `no list of instance values at`, and a path | The file is not where the script looks: `ls -l ~/.config/research-platform`. When `XDG_CONFIG_HOME` is set, the script looks there instead of in `~/.config`. |
| 3 | The block that writes the list prints an error from `tailscale`, `ssh` or `nmcli` | That part of the list is missing: Tailscale is not running (`tailscale status`), `server-lan` is not in `~/.ssh/config` (Tailscale guide, section 6), or the computer has no Wi-Fi. Add those values by hand, in `nano`. |
| 3 | A value of the list is not reported | It is shorter than four characters, or its line starts with `#`. |
| 4 | `--history` prints `instance value` for commits that are already public | A value of your list is a common word, or it is in the history already. A common word comes out of the list. A published value stays published: write it in your private note, with the date (section 7). |
| 4 | The test commit was created: the second `git log` shows a new commit | The hooks did not run (section 2). Take the commit out before anything else, with `git reset --soft HEAD~1`, and never push it. |
| 4, any commit | `not a GitHub noreply address` | `git config user.email` is not your noreply address. GitHub shows it in *Settings*, *Emails*; set it with `git config --global user.email` followed by that address. |
| 4, any commit | `python3: not found` | Install Python 3: `sudo apt install python3`. Without it, every commit is refused. |
| 5 | The run on GitHub is red, at *No instance data in any commit* | Its log names the commit and the rule; on GitHub, a finding in a file's name hides the name. Run `python3 scripts/check-instance-data.py --history` in your clone to see it, then section 7. |
| 5 | The run is red, at *Every relative link and anchor resolves* | Its log names the file, the line and the link. Fix the link, and run `python3 scripts/check-links.py` before committing again. |
| any | A finding on a value that is public on purpose | Section 7: the list of allowed values. |

## Next

The service host's heartbeat, next in the [roadmap](../roadmap.md). The thesis
repositories take this guard when they are created: its script, its hooks and
a list of allowed values of their own.

## References

- Git, *githooks* (where hooks run, `pre-commit`, `commit-msg`,
  `--no-verify`, and why a hook needs its executable bit):
  https://git-scm.com/docs/githooks
- Git, `git config`, `core.hooksPath` (a relative path is taken from where the
  hooks run): https://git-scm.com/docs/git-config
- GitHub, *About secret scanning* (on personal accounts, public repositories
  only):
  https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning
- GitHub, *Secure use reference* (pin actions to a commit):
  https://docs.github.com/en/actions/reference/security/secure-use
- GitHub, `actions/checkout` v7.0.1:
  https://github.com/actions/checkout/releases/tag/v7.0.1
- Tailscale, *How Tailscale assigns IP addresses* (its IPv4 range and its IPv6
  prefix): https://tailscale.com/docs/concepts/ip-and-dns-addresses
- IETF, RFC 1918, *Address Allocation for Private Internets*:
  https://www.rfc-editor.org/rfc/rfc1918
- Microsoft, *BitLocker recovery overview* (the 48-digit recovery password):
  https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/recovery-overview
