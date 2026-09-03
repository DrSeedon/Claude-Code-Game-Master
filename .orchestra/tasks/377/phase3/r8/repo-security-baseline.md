# R8 — Future private-repository security baseline

Status: executable configuration and evidence plan only. No repository, organization, provider setting, credential, backup, or production system was created or changed during this research. Provider features and terms are time-sensitive as of 2026-08-16.

## Baseline decision

The future repository is an **organization-owned GitHub private repository**, created empty with no README, license, `.gitignore`, template, import, fork, or initial commit. It is not a personal repository, an internal-visibility repository, or a converted copy of either current repository. GitHub states that private repository access is limited to explicitly granted users and relevant organization members, while organization owners retain access [1]; “private” is therefore one control, not a security boundary by itself.

The repository uses two non-circular gates. Configuration that does not need a real branch is proved before the bootstrap push, including negative rehearsals in a disposable private repository under the same organization, plan, policies, and actor roles. Controls that inherently need the real root/branch are proved immediately after one constrained bootstrap push and before any product code. There is no migration branch or temporary import containing prohibited blobs.

## Gate A — before the one bootstrap push

| Control | Required future state | Durable evidence | Fail-closed stop condition |
|---|---|---|---|
| Ownership and visibility | Named legal entity owns the organization; empty target reports `private=true` and `visibility=private`; exactly two continuity owners, both individually named and security-key/passkey capable | target API response, organization owner list, legal-entity and IP-review record | Unknown entity, personal ownership, internal/public visibility, or unreviewed owner blocks bootstrap |
| Authentication | Organization requires 2FA for every member and outside collaborator; security key or passkey is required for owners/admins and recommended for writers; recovery codes held in separate controlled storage | Organization security settings export and member compliance list | Any noncompliant privileged account or shared account blocks bootstrap |
| Access | Base organization permission `none`; target grants only named bootstrap administrator plus prepared `repo-readers`, `repo-writers`, and `repo-admins` teams; no outside collaborator or deploy key | Target collaborators/teams API output with role, approver, expiry, and business purpose | Unexpected principal, stale grant, shared identity, or unbounded bootstrap authority blocks bootstrap |
| Forking and visibility changes | Private/internal repository forking disabled; members cannot change visibility; repository transfer/deletion restricted to owners under two-person review | Organization/target policy export | Forking enabled or one-person visibility/transfer path blocks bootstrap |
| Ruleset design | `main` target ruleset is configured for PR, independent approval, stale-approval dismissal, last-push approval, required CI, CODEOWNERS, signed commits, linear history, blocked force-push/deletion | Target ruleset API output plus rejected direct-push and reviewer-policy rehearsals in a disposable private repository with the same ruleset and roles | Policy cannot be configured for a future branch, disposable rehearsal succeeds incorrectly, or a standing bypass exists |
| Actions | Only explicitly allowed actions pinned to full commit SHA; default `GITHUB_TOKEN` read-only; per-job permissions minimal; no production secrets; initial workflow static check passes locally | Target Actions policy export and initial-tree workflow review | Tag-only third-party action, write-all token, untrusted PR secret exposure, or unknown action blocks bootstrap |
| Secret protection | Host push protection/scanning licensed and enabled for private repositories; writer self-bypass forbidden; local pinned scanner defense in depth | Target security-feature API output plus a synthetic blocked-secret rehearsal in the disposable repository using the future writer role | Feature unavailable, bypass uncontrolled, or disposable rehearsal accepts the synthetic secret |
| Bootstrap tree | Proposed root commit contains only the allowlist below, has no parent, and passes path, all-object, credential, binary, provenance, rights, and independent two-reviewer checks before it leaves the local machine | proposed commit hash, `git fsck`, root/path/object/scan reports, two signed reviews | Parent/imported ancestry, product code, third-party runtime dependency, unknown blob, scan finding, or uncleared manifest row blocks bootstrap |
| Backup readiness | Separate encrypted off-provider mirror destination/identity and runbook configured; recovery owner and 24-hour RPO/4-hour RTO accepted; job prepared for the target identifier | destination/access evidence and dry configuration validation; no claim of a successful target mirror yet | Same credential/failure domain, no recovery owner/runbook, or destination cannot accept a target mirror |
| Incident ownership | Security lead primary, independent backup, legal/IP escalation owner, provider contacts, revocation paths, and bootstrap break-glass expiry recorded | incident roster and out-of-band contact/revocation rehearsal | No named revoker or no out-of-band recovery channel blocks bootstrap |

### One-time bootstrap procedure

1. Two independent reviewers approve the exact parentless commit hash and Gate A evidence. The commit contains scaffolding only and no product source, assets, provider integration, deployment credential/configuration, or runtime dependency.
2. A named owner grants one named `repo-bootstrap` identity a bypass limited to the target repository, exact purpose, and at most 15 minutes. The record contains approvers, actor, start/expiry, reason, rules bypassed, expected branch, and exact commit hash. No general writer receives bypass.
3. That identity pushes the exact reviewed commit as `main`. A post-receive check compares the remote root/tree hash byte-for-byte with the approved hash. Any mismatch triggers immediate repository freeze and incident handling.
4. The owner revokes bootstrap authority immediately, records revocation and audit events, and begins Gate B. Bootstrap authority is never reused; a failed attempt requires a fresh reviewed record rather than widening the grant.

## Gate B — after bootstrap, before any product-code push

All conditions below must pass on the real target repository:

- the bootstrap bypass is absent, ordinary writers cannot push directly, force-push, delete `main`, change visibility, or bypass required checks, and a rejected attempt records audit evidence;
- a synthetic PR proves required CI, independent approval, CODEOWNERS delivery, stale-approval dismissal, last-push approval, signed-commit enforcement, and two approvals for high-risk paths; the author cannot self-satisfy either class;
- a synthetic secret push by the ordinary writer role is blocked on the target with no bypass, while no synthetic secret enters Git history;
- the remote has exactly one root and its commit/tree/object inventory matches the pre-approved bootstrap record; the all-object scanner remains clean;
- the first encrypted off-provider mirror succeeds, `git fsck --full` passes on the mirror, its recorded root/tree hashes match the target, and access uses the separate backup identity;
- access, fork, Actions, security feature, ruleset, audit, and backup evidence is captured with timestamps; the incident owner signs Gate B closure.

Only then may the first protected PR add product source, runtime dependencies, assets, provider integration, deployment configuration, or campaign functionality. Dependencies in that PR are selected afresh, exactly version/hash locked, and accompanied by a direct/transitive SBOM with license source, notices, source/network obligations, vulnerability result, and reviewer decision. Unknown/no license, unresolved AGPL/network-source duty, mutable source, unreviewed transitives, or an unlocked install blocks the product PR.

GitHub can require 2FA for organization members and outside collaborators, and documents passkeys, security keys, authenticator applications, GitHub Mobile, and SMS as methods [3]. The stronger owner/admin requirement above is a project control. GitHub rulesets can require pull requests, reviews, status checks, signed commits, linear history, and can block force pushes and deletion [5]. Any emergency bypass is time-limited, reason-coded, audited, independently reviewed within one business day, and revoked within 24 hours; there is no standing bypass identity.

GitHub's documentation says full commit SHAs are the only immutable way to reference third-party Actions [7]. A SHA is not a trust decision: the action owner, source, permissions, inputs, outputs, license, and necessity still require review. Reusable workflows and nested actions are included in the closure.

GitHub secret scanning and push protection availability for private organization repositories depends on the account/product features [8][9]. This project requires a host/plan with non-bypassable enforcement for writers. If GitHub cannot supply that control, **no product push occurs** until an equivalent host or server-side pre-receive enforcement is selected. A local hook alone is not sufficient because it can be skipped.

## Initial tree and provenance

The initial commit allowlist is:

- `README.md` containing no product secrets or copied prose;
- the signed destination rights notice with the exact legal entity;
- minimal package/build metadata created afresh;
- `.gitignore`, `.gitattributes`, CODEOWNERS, pinned CI definitions, and security policy;
- provenance/third-party manifest, architectural decisions, independently authored delivery tests, and dependency/SBOM records.

Everything else is excluded until a later reviewed PR. The following are never imported from either current repository: Git history, source or tests, prompt/rules prose, fixtures, campaign/world/session data, books/PDFs/source material, RAG/vector stores, caches, databases or WAL/SHM files, `.env` files, credentials, provider profiles, cookies, tokens, keys/certificates, raw speech/enrollment recordings, generated binaries, deployment units, nginx/systemd/DNS configuration containing site or secret data, and assets without an approved manifest row.

The future `.gitignore` must cover at least:

- `.env`, `.env.*` except a synthetic `.env.example`; credential/key/certificate formats; provider CLI profiles and cookies;
- campaign/world/session/log/export paths and all source books, PDFs, archives, RAG/vector/model stores;
- `*.sqlite`, `*.sqlite3`, `*.db`, `*-wal`, `*-shm`, dumps and backups;
- raw/enrollment speech and working audio/video formats outside an explicit cleared-assets path;
- build products, package caches, coverage, generated provider output, and local deployment/secrets files.

Ignore rules do not establish safety. The all-object scanner checks names, strong prefixes, high-entropy candidates, private-key material, credentials, large/binary objects, forbidden extensions, and asset hashes before push. A reviewer resolves every finding; there is no blanket baseline acceptance. Current-repository measurements found that sampled SQLite and WAV paths were not ignored, so copying the current ignore file is not allowed.

Each contributor must be an individual identity covered by a written employment/assignment or authorized contribution instrument for the destination legal entity. A Git signature, DCO sign-off, or GitHub author field proves an account asserted authorship; it is not a substitute for ownership or transfer evidence.

## Dependency and supply-chain policy

The future project resolves a fresh minimal graph. It does not copy either current manifest or lockfile. For every direct and transitive package, the provenance record contains package ecosystem/name, exact version, resolved artifact URL and SHA-256, publisher/source repository, license text/source, notices, source-offer/network-use implications, vulnerabilities and review date, runtime/build/dev scope, and decision. Unknown metadata is a hard failure.

Installs use the committed lock and hashes only; the expected delivery checks are `uv lock --check` and `uv sync --locked` once the destination Python project exists. A lock change and SBOM/license diff are reviewed together. Dependency updates never auto-merge. Packages sourced from Git are pinned to an immutable commit and archive hash. Typosquatting/name similarity, maintainer transfer, new install scripts, unexpected binary wheels, or a license change triggers a hold and re-review.

## Access lifecycle and audit

- Grant least privilege through teams, never a shared account. Every temporary access grant has an owner, ticket, reason, and automatic expiry no later than seven days.
- Review owners/admins monthly and all repository access quarterly; re-review immediately on team or contract change. Disable access within four hours of termination or suspected compromise and revoke sessions, PATs, SSH keys, app grants, and recovery paths.
- Organization audit-log retention/export is configured according to the available plan; security-relevant repository events are exported to a separately controlled store. Alerts cover visibility, ruleset/bypass, collaborator, secret, Actions, deploy-key/app, and branch deletion/force-push changes.
- GitHub Apps are preferred to broad PATs. Every app has a named owner, exact repository allowlist, minimal permissions, expiry/review date, webhook secret rotation, and removal rehearsal. Fine-grained PATs, if unavoidable, are short-lived and restricted to this repository.
- Machine credentials never belong to a person and never appear in repository settings until a specific runtime requires them. I0 repository creation needs no production deployment credential.

## Backup and restore

GitHub documents `git clone --mirror` for repository data and `git lfs fetch --all` for LFS objects [10]. The project performs an encrypted daily mirror to storage controlled by a different credential and failure domain, retains 30 daily and 12 monthly recovery points, and verifies completion. If LFS is later enabled, its objects are included. Secrets and raw voice data remain outside Git and have separate encrypted backup/retention policy.

Quarterly, a recovery operator with no routine write access restores into an isolated private test organization/repository, runs `git fsck --full`, verifies branches/tags/objects/LFS against the recorded manifest, verifies access is private before import, and records actual RPO/RTO. The target is RPO ≤24 hours and RTO ≤4 hours. GitHub notes that migration archives do not necessarily include all repository data and does not document them as a restoration mechanism [10]; issues, PRs, releases, rules, settings, and audit exports therefore need separate export only if the project elects to make them critical. Architecture decisions and required delivery evidence stay in Git so the code mirror is sufficient for I0 continuity.

## Secret incident route

1. The security lead immediately blocks use, revokes/rotates the secret at its authority, invalidates related sessions/tokens, and freezes risky automation. History rewriting is never the first containment step.
2. Record secret class, exposure window, repository/object/PR/log locations, accesses, forks/clones/caches/backups, and authority-side evidence without copying the secret into the ticket or audit log.
3. Search all Git objects, Actions artifacts/logs, caches, package/container images, forks, mirrors, local clones, and backups. Notify provider/security/legal owners according to impact.
4. Purge exposed material only after rotation and preservation of required evidence. Rebuild affected artifacts and mirrors, then rerun the exclusion scan. Git history deletion is treated as propagation reduction, not credential revocation.
5. Restore service with a newly scoped secret, verify old-secret failure, record root cause and preventive control, and obtain independent closure approval.

Repository compromise uses the same ownership: revoke sessions/apps/keys, freeze merges and Actions, preserve audit evidence, compare protected refs and releases against signed records, rebuild from a verified backup if needed, and rotate any credential the repository could reach.

## Future evidence commands

These are delivery checks for the future repository and were deliberately not run in this research:

```bash
gh api repos/ORG/REPO --jq '{private,visibility,archived,security_and_analysis}'
gh api repos/ORG/REPO/collaborators --paginate
gh api repos/ORG/REPO/rulesets --paginate
gh api repos/ORG/REPO/actions/permissions
git rev-list --max-parents=0 HEAD | wc -l
git fsck --full
git ls-tree -r --name-only HEAD
git rev-list --objects --all
uv lock --check
uv sync --locked
```

The evidence package also includes the organization 2FA and fork policies, team membership, host push-protection negative rehearsal, CODEOWNERS delivery test, scanner command/version/checksum and full output, dependency/SBOM reports, first backup log, restore rehearsal, and qualified IP/security signatures. API output is captured with timestamps and repository identifiers but no credentials.

## Confidence, gaps, and counter-evidence

- **CONFIRMED:** the listed GitHub controls and limitations are documented by GitHub primary sources [1]–[10]. Their availability on the eventual plan is not yet confirmed.
- **CONFIRMED:** local current-tree/ignore measurements are recorded in `ip-route.md`; they do not prove historical cleanliness.
- **LIKELY:** the baseline prevents the most direct first-push provenance and secret failures when every negative rehearsal passes. This is a design inference, not a measurement on a future repository.
- **UNCERTAIN / blocking:** future organization, legal entity, owners, plan/features, access roster, scanner, backup target, and signed IP instruments do not exist in the evidence. These block the first product push.
- A private repository reduces casual disclosure but organization owners, collaborators, compromised accounts/apps, Actions, forks, backups, and host personnel remain access paths. The controls therefore do not rely on visibility alone.
- Signed commits and reviews improve attribution and change control but cannot prove code ownership, eliminate insider copying, or make a vulnerable dependency safe.

## Sources

1. [GitHub Docs, About repositories](https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories) — primary provider documentation.
2. [GitHub Docs, Managing teams and people with repository access](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository) — primary provider documentation.
3. [GitHub Docs, Requiring two-factor authentication in an organization](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-two-factor-authentication-for-your-organization/requiring-two-factor-authentication-in-your-organization) — primary provider documentation.
4. [GitHub Docs, Managing the forking policy for a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-the-forking-policy-for-your-repository) — primary provider documentation.
5. [GitHub Docs, Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) — primary provider documentation.
6. [GitHub Docs, Managing GitHub Actions settings for a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-github-actions-settings-for-a-repository) — primary provider documentation.
7. [GitHub Docs, Secure use reference for GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use) — primary provider documentation.
8. [GitHub Docs, Quickstart for securing a repository](https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository) — primary provider documentation.
9. [GitHub Docs, About secret-scanning alerts](https://docs.github.com/en/code-security/secret-scanning/secret-scanning-alerts/about-alerts) — primary provider documentation.
10. [GitHub Docs, Backing up a repository](https://docs.github.com/en/repositories/archiving-a-github-repository/backing-up-a-repository) — primary provider documentation.
