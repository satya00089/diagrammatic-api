# Local requirements migration and assessment evaluation

These tools do not import application settings, load `.env`, inspect private
attempts, call an LLM, upload Langfuse data, or change caches. Boto3 remains the
existing dependency; the Langfuse SDK baseline remains **4.15.2**. Run from the
API checkout. Outputs must be new local paths; existing output files are refused.

## Export, audit, and draft

```powershell
.\.venv\Scripts\python.exe scripts\requirements_migration.py export --input tests\fixtures\walkthroughs\problems.json --output docs\requirements-catalog-export.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py audit --snapshot docs\requirements-catalog-export.json --guide-dir ..\diagrammatic\src\data\public\problemGuides --output docs\requirements-catalog-audit.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py draft --snapshot docs\requirements-catalog-export.json --revision requirements-v2-preserved --output docs\requirements-catalog-draft.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py validate --manifest docs\requirements-catalog-draft.json --output docs\requirements-catalog-validation-new.json
```

Those first three outputs already exist from the local 145-record snapshot.
Do not run those commands again against the same paths. The audit reports actual
counts and compares them with the plan's 145 live / 146 static observation. It
marks static-only `job-scheduler` as `unresolved_alias`; it does not create a new
problem, rename a slug, or assume a scheduler equivalence. Guide differences are
editorial leads, not proof of contradiction. No guide assumptions enter a spec.

The source whitelist contains public catalog fields only. All original
`requirements` and `constraints` sentences remain exact, in source order; an
entry containing several sentences is not split or paraphrased. Stable IDs are
`req-<16 hex digits>` from problem ID, source attribute/index, exact text and
explicit original scope. Existing matching spec IDs/scopes are retained. Empty
functional/non-functional groups appear explicitly in the dry-run report.

Classification is a proposal. Legacy requirements get a heuristic functional or
quality category; constraints initially remain constraints because they mix
restrictions, capabilities and qualities. A reviewer can move a constraint
into a spec category while retaining the original constraints array. Ambiguous
scope is marked `needs_review`, including the difference between optional
capability and optional per-request input. No draft is publishable.

## Review and seal a manifest

For each proposed change, review **every** provenance row. Keep its exact
`text`, `sourceAttribute`, `sourceIndex`, and `originalScope`. Set its
`classification` to `functional`, `nonFunctional`, or `constraint`; only source
constraints may stay solely in the constraint bucket. Set the proposed `scope`
and optional category, preserving any explicitly recorded old scope. Keep the
row's stable ID. Match `proposedSpec` entries exactly to those reviewed rows.

Mark each row `status: reviewed`, supply `reviewer` and a meaningful `reason`,
and mark the problem-level `review` as reviewed with a reviewer. A content or
scope change beyond preserved source text requires a separate editorial
revision, not a silent migration. Assumptions cannot be copied from public
guides. Existing assumptions/spec requirements cannot disappear.

Before sealing, `readerCompatibility` must attest `status: verified`, include
schema version 1, and name the deployed reader version and evidence for API,
frontend, legacy, custom/free-form and historical-attempt compatibility. Merely
passing local model tests is not deployed-reader evidence. `cachePlan` must be
reviewed and name a release version. Its notes call for a targeted page-cache
version, matching static projection, and only affected walkthrough/session cache
versions. Counts are unchanged. No global cache flush is implemented.

```powershell
.\.venv\Scripts\python.exe scripts\requirements_migration.py validate --manifest docs\requirements-reviewed.json --publish --output docs\requirements-publish-check.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py validate --manifest docs\requirements-reviewed.json --approve-by REVIEWER --output docs\requirements-approved.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py apply --manifest docs\requirements-reviewed.json --output docs\requirements-dryrun.json
```

The approved file binds proposals, originals, active base revision, provenance,
reader gate, target table/region, and cache release plan with a digest. Any edit
after sealing invalidates approval. Historical originals live in bounded local
export/manifest/journal files rather than unbounded DynamoDB item history.

## Explicit remote operations (parent/operator only)

The agent implementing these tools has **not run** these operations. An
authorized operator may explicitly export the public table using `export
--remote-read --table diagrammatic_problems --region ap-south-1 --output NEWFILE`.
Scans project public fields and follow every `LastEvaluatedKey`, including empty
pages. A scan is not a transactional snapshot; apply preflights all current
records and then uses conditions to close the read/write race.

```powershell
.\.venv\Scripts\python.exe scripts\requirements_migration.py apply --apply --approved docs\requirements-approved.json --journal docs\requirements-apply-journal.json --output docs\requirements-applied.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py rollback --approved docs\requirements-approved.json --journal docs\requirements-apply-journal.json --output docs\requirements-rollback-dryrun.json
.\.venv\Scripts\python.exe scripts\requirements_migration.py rollback --apply --approved docs\requirements-approved.json --journal docs\requirements-apply-journal.json --output docs\requirements-rolled-back.json
```

Only `requirementSpec` and additive `requirementSpecProvenance` are set/removed.
There is no `put_item`, record replacement, deletion, ID/slug update, legacy-array
rewrite, or attempt-table operation. Conditions guard each original source and
changed attribute, including the active spec revision. Reads use strong
consistency. A conservative item-size budget rejects oversized candidates.

The local journal records exact originals/current values before each write and
is refreshed atomically with flushed writes. Every updated item is read back.
Any failure stops the batch; previous changes and pending/uncertain writes stay
in the journal. There is no automatic retry. Rollback validates the journal
against approval and restores/removes only the changed attributes, conditioned
on exactly the migration's current values. A later relevant edit blocks
rollback; an unrelated later field is preserved. Inspect partial or ambiguous
outcomes before proceeding. Static content/cache version rollback is a separate
operator action described in the journal, not a hidden mutation.

AWS contracts: [conditional UpdateItem](https://docs.aws.amazon.com/boto3/latest/reference/services/dynamodb/table/update_item.html)
and [paginated Scan](https://docs.aws.amazon.com/boto3/latest/reference/services/dynamodb/table/scan.html).

## Public walkthrough evaluation

```powershell
.\.venv\Scripts\python.exe scripts\assessment_evaluation.py check --walkthrough-dir data\assessment-reference-candidates\walkthroughs --manifest docs\requirements-catalog-draft.json --output docs\requirements-structure-new.json
.\.venv\Scripts\python.exe scripts\assessment_evaluation.py prepare --walkthrough-dir data\assessment-reference-candidates\walkthroughs --manifest docs\requirements-catalog-draft.json --output docs\requirements-evaluation-new.json
.\.venv\Scripts\python.exe scripts\assessment_evaluation.py plan --bundle docs\requirements-assessment-evaluation-bundle.json --output docs\requirements-run-plan.json
.\.venv\Scripts\python.exe scripts\assessment_evaluation.py evaluate --bundle docs\requirements-assessment-evaluation-bundle.json --results docs\requirements-recorded-results.json --output docs\requirements-evaluation-results.json
```

The original `tests/fixtures/walkthroughs/{problem_id}.json` version 1.0 files are
read only. `--walkthrough-dir` can select candidates or any separately reviewed
version. The pure replay handles `add_component`, `add_connection`, and
`update_component` with `{componentUpdate: {nodeId, properties}}`. Any accepted
step carrying `componentUpdate`, including decision/scale steps, applies that
payload. A viewed explanation or decision without an application payload is
not implemented evidence. Broken endpoints, duplicate IDs, missing protocols,
invalid property updates and mismatched revisions fail before model calls.
Candidate guides that declare `requirementRevision` require a matching spec in
the manifest even for the offline structure check; a revision label alone is
not a reviewed brief.

Replay with no selected IDs simulates accepting every explicit action. Use
`build_architecture(guide, applied_step_ids=[...])` for actual accepted actions.
Semantic catalog identities, properties, descriptions, connection protocols and
explicit choices survive the local replay; geometry/runtime props do not enter
the assessment request. Frontend apply/save/reload tests independently establish
parity; this Python helper does not claim to have run a browser.

`prepare` creates five complete candidates, five component-removal defect drafts,
and two ID/geometry equivalence drafts when given the five saved guides. These
generated labels are explicitly `generated-not-human-truth`; editors must
review defect validity, core coverage, severity, forbidden unsupported claims
and score bands. Supply `--alternative-dir` with two public alternative case
JSON files to replace the generated representations with reviewed provider or
architectural alternatives. Each alternative has `id`, `kind: alternative`,
`counterpart`, `request`, and optional `expected`/`provenance`; its frozen problem
context must match the counterpart. Generated representation variants do not
qualify as reviewed architectural alternatives for release.

The plan contains exactly five runs per case. Expected labels never enter
`request`. The parent can invoke `await run_evaluation(bundle, reviewer,
experiment)` with its existing authorized reviewer; this hook calls each input
once, captures errors and elapsed time, and never repairs or retries. The CLI
itself only prepares/reads local files and makes no model/network/SDK calls.

Recorded results contain `bundleHash`, frozen `experiment` (`model`,
`modelConfigHash`, `promptVersion`, `rubricVersion`), and `runs`. Each run includes
`caseId`, repeat 1–5, `inputHash`, fixture/config `provenance`, `result` or `error`,
and optional `latencyMs`. Preserve raw results. Provenance includes walkthrough
and requirement hashes/versions. A new bundle cannot reuse old result hashes.

Scores count only with `source: ai` and explicit `scoreAvailable: true` (or API
`score_available`). Complete/valid-alternative runs must all score at least 96,
cover core requirements, and have no critical/unsupported findings. API
`requirement_coverage`, `requirement_id`, `evidence_ids`, and `requirement_ids`
are supported alongside frontend camel-case fields. Invalid references, missing
coverage, malformed results, fallback scores, absent runs, extra runs and
duplicate/replacement runs fail. Negatives must detect their intended reviewed
defect and score lower than their complete counterpart on the same repeat. A
constant-98 reviewer fails that gate. Reports retain scores, variation, latency,
trace provenance and every failure; no score is forced.

`acceptancePassed` describes recorded test behavior. `releaseEligible` remains
false for draft labels/specs, candidate versions, an incomplete 5/5/2 dataset,
or generated representation alternatives. Structural checks and mocked scores
are not live acceptance. Human review, frozen live repeat runs and deployed
reader/cache validation remain operator responsibilities; no live upload occurs.

## Focused tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_requirement_migration.py tests\test_assessment_evaluation.py
```

On Windows sandbox hosts where the default pytest temp directory is inaccessible,
use a **new, unused** workspace `--basetemp` path and `-p no:cacheprovider`.
Pytest clears its base-temp target, so never point that option at a workspace
root, existing user directory, or retained fixture/output directory.
