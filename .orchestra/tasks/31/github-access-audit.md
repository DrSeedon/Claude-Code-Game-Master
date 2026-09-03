# GitHub access audit and private-repository setup

Date: 2026-08-17 (Europe/Berlin)  
Operator: persistent AI-table Sol lead  
Execution identity: `kesha` (UID 1001); non-interactive sudo unavailable

## Verdict

Before the owner-authorized device flow, the VPS had no verified non-interactive GitHub API credential available to `kesha` that could create `DrSeedon/ai-table-mvp`. Three `kesha` SSH identities authenticated as DrSeedon-related identities, but SSH is Git transport and cannot create a GitHub repository. The inaccessible homes of `root`, `tunnel`, `codexproxy`, and `tailscaleadmin`, plus one unreadable root-owned service environment, remain `unknown`; the audit does not turn permission denial into an absence claim.

The owner then explicitly authorized a GitHub CLI device flow. The resulting `kesha` credential authenticates as `DrSeedon`, has scopes `gist`, `read:org`, and `repo`, and was used to create and populate the private repository. The one-time device code and token are intentionally absent from this artifact.

Current result:

- Repository: `https://github.com/DrSeedon/ai-table-mvp`
- SSH origin: `git@github.com:DrSeedon/ai-table-mvp.git`
- Visibility: authenticated API reports `private=true`, `visibility=private`.
- Public exposure check: unauthenticated repository and contents API requests both return HTTP 404.
- Main commit: `78df176da76378b9542e371165da76243acd2fa4`; `git ls-remote origin refs/heads/main` returns the same object.
- All four local branch heads were pushed and exactly match four remote branch heads; there were no local tags.
- `/home/kesha/projects/ai-table-mvp` and its `.git` directory remain `kesha:kesha` mode 0700; the worktree is clean.

## Evidence table

This table distinguishes the read-only pre-authentication audit from the explicitly authorized setup that followed it.

| principal/context | credential mechanism | exact path/source owner+mode | authenticated GitHub login if safely testable | scopes/capabilities | read-only test command | result | sufficient for create-private-repo yes/no/unknown |
|---|---|---|---|---|---|---|---|
| `kesha`, pre-authentication | GitHub CLI host store | `/home/kesha/.local/bin/gh` `kesha:kesha` 0755; `/home/kesha/.config/gh/hosts.yml` absent at audit time | none | none | `gh auth status --hostname github.com` with token lines redacted | not logged in | no |
| `kesha`, post-owner authorization | GitHub CLI OAuth credential | `/home/kesha/.config/gh` `kesha:kesha` 0700; `/home/kesha/.config/gh/hosts.yml` `kesha:kesha` 0600 | `DrSeedon`, active account, SSH Git protocol | `gist`, `read:org`, `repo`; private-repository creation demonstrated | `gh auth status --hostname github.com` with token lines redacted; authenticated repository metadata query | private repository creation and authenticated metadata query succeeded | yes |
| `kesha` | SSH identities | `/home/kesha/.ssh` 0700; `id_ed25519`, `id_ed25519_cog`, and `id_ed25519_github` each `kesha:kesha` 0600; config and known_hosts 0600 | `DrSeedon/kesha-tg-bot`, `DrSeedon/COG-second-brain`, and `DrSeedon` respectively | Git transport to existing authorized repositories; no repository-creation API | `ssh -T` with BatchMode, strict existing known_hosts, and one explicit identity per probe | all three identities authenticated; GitHub's expected `-T` exit was 1 | no |
| `kesha` | Git credential helpers, fill, netrc, stored HTTPS credentials, hub | `/home/kesha/.gitconfig` `kesha:kesha` 0664; `.config/git/config`, `.netrc`, `.git-credentials`, and `.config/hub` absent; `/etc/gitconfig` absent | none | no helper and no username/secret returned by the internally reduced fill probe | `git config --show-origin --get-all credential.helper`; credential-fill output reduced to presence booleans | helper unset; username present=no; secret present=no | no |
| `root` | gh, Git helper/stores, SSH | `/root` `root:root` 0700; descendant candidate paths inaccessible | unknown | unknown | parent-directory metadata only; no privilege escalation | current `kesha` identity cannot inspect or safely test root's stores | unknown |
| `tunnel`, `codexproxy`, `tailscaleadmin` | gh, Git helper/stores, SSH | respective `/home/<principal>` directories owned by that principal, mode 0750; descendant candidate paths inaccessible | unknown | unknown | parent-directory metadata only; no privilege escalation | current `kesha` identity cannot inspect or safely test these stores | unknown |
| systemd service contexts | EnvironmentFile credentials/config | `/opt/kesha-bot/.env` `kesha:kesha` 0600; `/home/kesha/orchestra/.env` `kesha:kesha` 0644; `/etc/seedon-lead-audit.env` `kesha:kesha` 0600; `/opt/orchestra-proxy/.env` `root:root` 0600 | not tested | readable files and processes exposed no `GH_TOKEN`, `GITHUB_TOKEN`, or `GITHUB_PERSONAL_ACCESS_TOKEN` variable name; root-owned proxy content unknown | `systemctl show ... -p EnvironmentFiles`; value-free environment-name parser | three readable sources had no GitHub authentication variable name; proxy source unreadable | unknown overall; readable contexts no |
| running process contexts | Environment variables | 343 `/proc/<pid>/environ` entries enumerated; 162 readable under their owning contexts | not tested | `GITHUB_PERSONAL_ACCESS_TOKEN=0`, `GITHUB_TOKEN=0`, `GH_TOKEN=0`; `GH_PAGER` is not a credential | NUL-delimited parser emitting variable names only | no readable process GitHub API credential | no for readable contexts; unknown for unreadable contexts |
| Claude external GitHub connector | MCP descriptor using `GITHUB_PERSONAL_ACCESS_TOKEN` by name | `/home/kesha/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/github/.mcp.json` and plugin manifest, `kesha:kesha` 0644 | not tested | descriptor present; active checked `mcpServers` maps empty; required variable absent from readable processes | key-only JSON inspection and path-only token-name search | installation path exists but no active credential/capability was demonstrated | no in current context |
| Orchestra source | webhook and workflow-log GitHub API integration | `/home/kesha/orchestra/app/routes/system.py` `kesha:kesha` 0644 | not tested | webhook verification and failed-log retrieval symbols; no repository-creation endpoint or call | safe symbol-only search for repo-create/API/SDK/Terraform patterns | no repository-creation mechanism matched | no |
| project Git configurations | GitHub remotes | 55 Git configs checked; 12 GitHub remote configs, owned by `kesha`, modes 0644 or 0664 | not tested | 8 SSH and 4 HTTPS remotes; zero helper or URL-rewrite matches | path-only Git config scan and safe scheme/helper classification | remotes exist but no API credential/provisioning mechanism | no |
| GitHub Actions workflow contexts | workflow `GITHUB_TOKEN` references | 79 workflow files checked; 15 candidate paths; modes 0644 or 0664 | not available from the VPS audit identity | repository-scoped workflow permissions; zero explicit repository-creation pattern matches | path/key-only scan for workflow token and create-repository patterns | workflow declarations are not a locally usable provisioning credential | no |

## Coverage and method

Two independent Luna extraction slices enumerated evidence; the persistent Sol lead joined the rows, resolved `yes/no/unknown`, performed the authorized setup, and verified the resulting remote.

- Five passwd principals were in scope: `root`, `kesha`, `tunnel`, `codexproxy`, and `tailscaleadmin`.
- Per-principal user-store scan: 65 fixed candidate paths, seven installation/system paths, three explicit SSH identity probes, five project-local helper contexts, and four service EnvironmentFile contexts.
- Service/project scan: 1,062 unit/drop-in files, 72 environment declarations, 144 `.env*` paths in accessible trees, 343 process environments (162 readable), 55 Git configs, 79 workflow files, zero Terraform files, and six connector/MCP directories.
- Token-pattern searches returned path and key/variable names only. Credential values, private-key contents, and the device code were never included in audit output or this artifact.
- Permission-denied paths are reported as `unknown`, never as absent.

## Authorized setup and verification

Commands below were run with `GH_TOKEN` and `GITHUB_TOKEN` explicitly unset so GitHub CLI used its configured `kesha` account. Outputs were reduced to non-secret fields.

```text
gh auth status --hostname github.com
  Logged in to github.com account DrSeedon (/home/kesha/.config/gh/hosts.yml)
  Active account: true
  Git operations protocol: ssh
  Token scopes: 'gist', 'read:org', 'repo'

gh repo create DrSeedon/ai-table-mvp --private --source=. --remote=origin
https://github.com/DrSeedon/ai-table-mvp

git push -u origin main
git push origin --all
git push origin --tags
main pushed; three additional local branch heads pushed; tags already up to date

gh api repos/DrSeedon/ai-table-mvp --jq '[.full_name,(.private|tostring),.visibility,.default_branch,.ssh_url,.html_url]|@tsv'
DrSeedon/ai-table-mvp  true  private  main  git@github.com:DrSeedon/ai-table-mvp.git  https://github.com/DrSeedon/ai-table-mvp

unauthenticated GET https://api.github.com/repos/DrSeedon/ai-table-mvp
HTTP 404

unauthenticated GET https://api.github.com/repos/DrSeedon/ai-table-mvp/contents
HTTP 404

local HEAD       78df176da76378b9542e371165da76243acd2fa4
remote main HEAD 78df176da76378b9542e371165da76243acd2fa4
local branches   4
remote branches  4
all branch heads match: yes
worktree status entries: 0
```

The GitHub credential boundary was tightened and then checked:

```text
/home/kesha/.config/gh           kesha:kesha 0700 directory
/home/kesha/.config/gh/hosts.yml kesha:kesha 0600 regular file
```

No DND or Orchestra runtime file was modified. In the DND repository, this task changes only sanitized evidence under `docs/tasks/31/`. The product repository changed only its local Git remote configuration; tracked files and commit history were not rewritten.

## Review disposition

The canonical security route required a fresh Sol technical review. The reviewer was `gpt-5.6-sol`; its artifact is `docs/tasks/31/codex-review.md`. It independently rechecked the credential modes, remote identity, branch-head equality, clean product tree, unauthenticated 404 responses, table completeness, and secret-safety. Verdict: `APPROVED`, with zero blocking findings and no material suggestions or questions. Cross-family review was not required because this task authored evidence only and changed no executable code or runtime.
