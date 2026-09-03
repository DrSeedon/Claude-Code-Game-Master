# R8 — Fail-closed IP and content route

Status: research decision for the future private repository; no repository, source, test, asset, campaign data, credential, or provider resource was created or transferred. Evidence was collected on 2026-08-16. This is an engineering provenance route, not legal advice; the named qualified IP/legal reviewer remains a release gate.

## Authoritative artifact index

The exact delivered paths for R8 are:

- `docs/tasks/377/phase3/r8/ip-route.md`
- `docs/tasks/377/phase3/r8/transfer-manifest.tsv`
- `docs/tasks/377/phase3/r8/repo-security-baseline.md`
- `docs/tasks/377/phase3/r8/remote-authority-threat-model.md`
- `docs/tasks/377/phase3/r8/codex-review.md`

The flattened `phase3/r8-*.md` names in the parent plan are artifact labels, not duplicate delivery locations. The orchestrator's exact R8 instruction selected the nested directory above; duplicating the files would create two authorities.

## Question and decision test

- **Context:** the I0 product is to be implemented in a new private repository while this DnD repository is CC BY-NC-SA 4.0 and Orchestra is AGPL-3.0/commercially licensed.
- **Change under test:** start with a clean, proprietary repository and independently implement only specified behavior, allowing literal material only after row-level provenance and license clearance.
- **Baseline:** copy selected implementation, tests, dependencies, or creative assets because the destination repository is private.
- **Measurable outcome:** every candidate has a complete row in `transfer-manifest.tsv`; an incomplete owner, grant, dependency closure, intended-use analysis, notice, or review field makes the executable action `AVOID` or `BEHAVIORAL_REWRITE`. No uncleared blob enters the future Git object database.

### Hypotheses and falsifiers

1. **Leading hypothesis:** behavioral rewrite is the only currently executable route for DnD and Orchestra implementation and tests because the local licenses and contribution history do not establish a proprietary-product transfer grant. This would be wrong if a qualified reviewer produced written, owner-authorized grants covering the exact blobs, all dependencies, patents where relevant, commercial/network use, modification, sublicensing/distribution, and required notices.
2. **Alternative:** file-level literal transfer can be safe merely because a file uses only the Python standard library or has a known Git author. This would be wrong if author metadata is not ownership evidence, the repository license still governs the file, or a transitive copied component has an incompatible or unknown obligation. Current evidence falsifies this alternative.
3. **Content hypothesis:** SRD 5.2.1 and cleared original/commissioned assets can support the product without D&D branding or closed-book content. This would be wrong if the required behavior depends on non-SRD product identity/content, or if a specific asset lacks a written commercial grant and provenance record. No such dependency was found in the canonical specification; the asset grants do not yet exist.

## Executable route

### I0 implementation: independent behavioral rewrite

The default and presently approved engineering action is **zero literal transfer from this DnD repository and Orchestra**. The future team may independently implement behavior-level requirements described as inputs, outputs, invariants, and failure cases, but must not copy or mechanically transform protectable expression in source, tests, comments, schemas, prompt prose, CLI text, UI text, filenames as a set, or generated assets. Whether a particular element is protectable is jurisdiction- and fact-specific and remains subject to qualified review. The US Copyright Office states that US copyright in a computer program does not cover ideas, program logic, algorithms, systems, methods, concepts, or layouts [8]; that supports this risk-reduction route but is not a worldwide clean-room certification.

The rewrite procedure is executable:

1. A specification author records only product behavior and observable oracles from the canonical MVP specification: request/response shapes, state invariants, error semantics, concurrency cases, and acceptance examples. No source or existing test body is attached.
2. An implementer starts from an empty, access-controlled repository and writes a new architecture, names, code, fixtures, and tests from that behavior contract and applicable public standards. Existing repository files are not opened or pasted into the destination during implementation.
3. Every dependency is selected afresh and entered into the destination dependency/SBOM record with package, exact version/hash, license source, direct/transitive closure, intended server/network use, notice/source obligations, and reviewer decision. The current `pyproject.toml` or lockfile is not copied.
4. Before merge, a reviewer who did not author the new code checks the behavior contract, destination diff, provenance rows, dependency closure, and an exclusion/similarity report. Similarity is a triage signal, not proof of non-infringement.
5. A qualified IP/legal reviewer records the legal entity, contributor-assignment basis, product-use analysis, and any exception. An exception is blob-specific; it never converts neighboring files into approved material.

Existing tests are behavioral clues, not reusable artifacts. New tests must be independently worded and structured around the product specification. A test name or assertion that exists only in the source repository is not transferred.

### Literal-material decision algorithm

Literal transfer is allowed only when one manifest row has all of the following and the recorded reviewer signs it:

1. exact source repository, immutable commit/version, path, and blob/content hash;
2. legal owner or authorized licensor supported by a written grant, not inferred from Git authorship;
3. license/grant that covers the destination's commercial, private, hosted/network, modification, distribution, and sublicensing facts as applicable;
4. complete copied and linked dependency closure, including data, fonts, models, prompts, fixtures, generated output, and build/runtime packages;
5. all attribution, notice, source-offer, share-alike, trademark, patent, privacy/consent, and retention obligations;
6. a qualified reviewer's identity, decision, date, and evidence location.

Any blank, `unknown`, unverifiable dependency, incompatible network/source obligation, or unclear ownership makes the action **AVOID**. If only the behavior is useful, the action is **BEHAVIORAL_REWRITE**. Privacy of the destination does not cure copyright or license obligations.

## Rules content and branding

### Selected route: SRD 5.2.1 only

Wizards' official SRD page identifies SRD 5.2.1, published 2025-05-01, as the 2024/5.5e rules document and states that both 5.1 and 5.2.1 are CC BY 4.0 [1]. I0 will use **SRD 5.2.1 only** to prevent silent rules-version mixing. The whole PDF is not vendored. Each future literal excerpt or data value must record the PDF version/hash, page or section, destination, transformation, and attribution review before use.

The destination legal notice must reproduce the attribution statement prescribed on page 1 of SRD 5.2.1, including the official SRD URL and CC BY 4.0 legal-code URL [2]. The PDF permits the compatibility phrase “5E compatible” [2]. The product name, UI, domain, package metadata, and promotional material must not use “Dungeons & Dragons,” “D&D,” the dragon ampersand, Wizards logos, setting names, product names, or other Wizards branding. The official creator FAQ distinguishes SRD content from the non-CC Basic Rules and identifies those marks [4].

SRD 5.1 is not forbidden: Wizards says both SRDs can be mixed with appropriate attribution [1]. It is excluded from I0 to eliminate version ambiguity. If a later requirement demonstrably needs a 5.1-only rule, the team must add a content-level manifest row, both applicable attributions, a deterministic conflict rule, tests for the chosen version, and qualified review. Content from Basic Rules, closed adventures, settings, books, D&D Beyond pages outside the SRD grant, or third-party wikis is `AVOID`.

### Original story and creative assets

- Story, characters, locations, maps, item flavor, dialogue, prompt prose, UI copy, and campaign data are newly authored or commissioned. The destination records the author, assignment/license, creation date, source files, content hash, and permitted uses.
- The three tracked PNG files in this repository have commits and blob hashes but no embedded rights grant or source receipt; they are `AVOID`. The two absolute-path images referenced by the canonical specification are concept references with no transferable provenance; they are also `AVOID`.
- Art, fonts, music, SFX, and audio are admitted only from original work, a written commission/assignment, CC0, CC BY with fulfilled attribution, or a stock license whose receipt and terms snapshot expressly cover commercial hosted use and required redistribution. CC BY-NC, CC BY-SA, unknown, scraped, and “free to use” without license evidence are fail-closed pending qualified review.
- Generated assets require the generator/provider, account/plan, prompt/input provenance, model/version if disclosed, creation time, output hash, terms snapshot, human/third-party reference inputs, and reviewer decision. An output is not admitted merely because a provider generated it.

### Voice and provider output

The brand voice route is a commissioned performer with signed commercial recording, voice-model, synthetic-output, modification, caching, and distribution rights, plus consent/withdrawal, geography, term, and deletion/retention terms. No voice is cloned without documented authorization. ElevenLabs' official policy requires rights/consent and prohibits unauthorized or deceptive impersonation [12]; its cloning documentation says technical verification cannot guarantee that a recording belongs to the requester [11].

If ElevenLabs remains the selected provider, the production account must be on a paid plan whose generation-time terms permit commercial use [10]. The EEA terms effective 2026-03-31 state that the user retains rights as between user and provider while granting the provider broad rights to use submitted content and voice data to provide, improve, and develop services [9]. That term snapshot and performer consent must be reviewed before enrollment. Public Voice Library voices are not the sole or fallback brand identity: the official documentation permits owners to remove a shared voice and describes notice windows [13]. Raw enrollment recordings and consent records stay encrypted outside Git with least-privilege access; cached output enters `assets/cleared/` only after its manifest row is approved.

## Evidence from the current repositories

Measurements were taken locally without copying material:

- DnD HEAD was `ae25d6e48776c0f361fbcb6806e5195203542941`. `LICENSE` and `pyproject.toml` declare CC BY-NC-SA 4.0 and identify Sean Stobo. Git history shows multiple authors; author metadata supplies provenance leads, not ownership grants. Creative Commons advises against using CC licenses for software because they lack software-specific source-code and patent terms [7]. **Confidence: CONFIRMED** for repository declarations/history (direct measurement); **UNCERTAIN** for ultimate ownership (no contracts or assignments were supplied).
- Orchestra HEAD was `366367f5d6d3fe85c90be0aa91f2c7608ce95460`. Its `LICENSE` is GNU AGPL-3.0 with commercial licensing offered separately. AGPL section 13 requires a modified network-interacting program to offer Corresponding Source to remote users [6]. No commercial grant for this product was supplied. **Confidence: CONFIRMED** for the license declaration (direct measurement and primary license); therefore literal reuse is `AVOID` for a proprietary route.
- Candidate DnD blobs, first-add commits, immediate imports, and Orchestra behavior clusters are recorded in `transfer-manifest.tsv`. Standard-library-only imports reduce dependency work but do not establish transfer rights. **Confidence: CONFIRMED** (Git/object and source inspection).
- The tracked-tree inventory contained 391 files, three PNGs, no tracked databases/WAL files, raw audio, PDFs, private keys, certificates, or campaign-state paths, and one `.env.example`. A targeted current-tree scan found zero strong-prefix matches for AWS, GitHub, OpenAI, private-key, or ElevenLabs-like credentials. This was not a full historical entropy scan, and no secret-scanning product was installed. **Confidence: CONFIRMED only for the measured current-tree predicates; UNCERTAIN for history and generic secrets.**
- `.gitignore` ignored sampled campaign state, source PDFs, `.env`, `.key`, and `.pem` paths, but did not ignore sampled `data.sqlite` or `voice.wav`. **Confidence: CONFIRMED** (direct `git check-ignore` measurement). The future repository must use the stricter baseline in `repo-security-baseline.md`.

## Counter-evidence and limits

- CC BY-NC-SA permits noncommercial sharing and adaptation under its conditions [5]; this does not prove that every tracked file is unusable. The fail-closed decision is narrower: commercial intent is unresolved, software licensing is ill-suited, ownership grants are absent, and no row-level dependency/legal closure exists.
- AGPL software can be used in a hosted product if its obligations are accepted, and a separate commercial grant could authorize another route. The selected proprietary/private route does not accept an AGPL source offer and has no commercial grant, so literal reuse is not executable now.
- SRD 5.1 and 5.2.1 can legally be mixed under Wizards' stated CC route [1]. The I0 exclusion of 5.1 is a version-control and scope decision, not a claim that 5.1 is prohibited.
- A clean rewrite cannot guarantee absence of every copyright, patent, trademark, publicity, privacy, or contract claim. Qualified review and contributor/asset contracts remain necessary.

## Gaps and blockers

The following are actual gates, not questions for the owner:

1. No written assignment or commercial transfer grant was supplied for any DnD or Orchestra blob. This blocks all literal source/test transfer, but does **not** block behavioral rewrite.
2. The exact destination legal entity and contributor employment/assignment instruments are not recorded. Qualified IP/legal review must fill them before the first product-code commit.
3. No future Git host configuration evidence, licensed non-bypassable secret protection, access list, or backup restore proof exists. Those block the first product push under `repo-security-baseline.md`, not the research route.
4. No art, audio, performer consent, stock receipt, provider account/plan evidence, or generation-time terms snapshot exists. This blocks asset admission, not placeholder-free core implementation.
5. The current-tree credential scan did not cover complete Git history or high-entropy generic values. The future exclusion scan must cover all objects before any approved exception is imported.

## Sources

1. [Wizards of the Coast, System Reference Document landing page](https://www.dndbeyond.com/srd) — primary source.
2. [Wizards of the Coast, SRD 5.2.1 PDF](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf) — primary source.
3. [Wizards of the Coast, SRD 5.1 PDF](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf) — primary source.
4. [Wizards of the Coast, Creator FAQ](https://www.dndbeyond.com/creator-faq) — primary source.
5. [Creative Commons, CC BY-NC-SA 4.0 deed and legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/) — primary license source.
6. [GNU Project, GNU Affero General Public License v3](https://www.gnu.org/licenses/agpl-3.0.html) — primary license source.
7. [Creative Commons, frequently asked questions on software licensing](https://creativecommons.org/faq/) — primary publisher guidance.
8. [US Copyright Office, computer-program registration guidance](https://www.copyright.gov/register/tx-programs.html) — primary US government source.
9. [ElevenLabs, EEA terms of service](https://elevenlabs.io/terms-of-use-eu) — primary provider terms, time-sensitive.
10. [ElevenLabs, text-to-speech documentation](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) — primary provider documentation, time-sensitive.
11. [ElevenLabs, voice-cloning documentation](https://elevenlabs.io/docs/eleven-api/concepts/voice-cloning) — primary provider documentation, time-sensitive.
12. [ElevenLabs, prohibited-use policy](https://elevenlabs.io/use-policy) — primary provider policy, time-sensitive.
13. [ElevenLabs, Voice Library documentation](https://elevenlabs.io/docs/eleven-creative/voices/voice-library) — primary provider documentation, time-sensitive.

Local primary evidence: `LICENSE`, `pyproject.toml`, Git objects/history, candidate imports, tracked-tree inventory, and ignore checks in the DnD repository at the stated HEAD; `LICENSE`, Git objects/history, and behavior-cluster source inspection in Orchestra at the stated HEAD.
