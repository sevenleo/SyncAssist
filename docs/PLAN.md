# SyncAssist Pending Work Implementation Plan

> For agentic workers: use the executing-plans or subagent-driven-development workflow and track every step with checkboxes.

**Goal:** Implement and verify every incomplete or unproven item carried over from the SyncAssist audit while preserving the one-file, standard-library product.

**Architecture:** Keep sync.py as the portable entry point. Extend its existing layers in place: REST/resource acquisition, document parsing/rendering, filename/path safety, journaled mutation, scope cleanup, reporting and CLI. Add focused unittest cases in test_sync.py before each production change, then update the user-facing documentation.

**Tech Stack:** Python 3.11+, standard library only, urllib REST client, pathlib, argparse and unittest.

**Spec:** docs/PLAN.md is the execution plan; the previous audited requirements are represented by Tasks 1–6 below.

## Global constraints

- Keep runtime compatibility with Python 3.11 or newer.
- Do not add dependencies, a Trello SDK, a database, a daemon, a scheduler, a webhook, a GUI or a custom API.
- Keep the fixed Trello HTTPS origin, OAuth header, bounded retries and redacted diagnostics.
- Keep full Trello IDs as identity; filenames remain presentation/status input only.
- Never infer completion from labels, titles, checklist completion or archiving; use dueComplete.
- Never delete, move or archive a Trello card because a local file is absent.
- Never repeat an uncertain POST automatically; reconcile by identity or preserve an explicit conflict.
- Preserve local bytes and remote receipts across partial failures.
- Do not commit changes.

## Evidence baseline

Before implementation, the current repository has 82 passing offline tests, successful py_compile, and working --help/--version. No real Trello list has been used. Existing tests and helpers must be reused; no second parser, client or report model may be introduced.

---

### Task 1: Complete remote resource acquisition

**Files**

- Modify: sync.py, TrelloClient resource methods and sync_once inventory flow.
- Test: test_sync.py, ClientTests and SyncOnceTests.
- Update: docs/README.md with fetched/unsupported resource behavior.

**Interfaces**

- Keep TrelloClient.get_card_bundle(card_id, previous_reference=None) returning the existing bundle shape plus resource_status and resource_errors.
- Keep incomplete bundles non-writable.
- Preserve current fake APIs by using a small adapter in sync_once when an injected fake does not accept previous_reference.

- [x] Add failing tests for partial complementary-resource failure, explicit unsupported resources and pagination of every resource that exposes a cursor.
- [x] Add resource loading that records status per resource: complete, empty, unsupported or failed; never map a failed request to [].
- [x] Pass the prior parsed reference when available and retain prior sections when the new request fails.
- [x] Keep card/list/board/labels/actions/checklists/attachments/members/custom-field values/stickers in the raw reference snapshot.
- [x] Add custom-field definitions, votes and Power-Up shared data only when their official endpoint and response are available; otherwise preserve an explicit unsupported entry.
- [x] Preserve board-label and action pagination with cursor advancement and repeated-cursor protection; apply the same helper only to endpoints whose contract supports pagination.
- [x] Set cleanup_allowed false whenever a resource or inventory cannot be complete, but continue independent cards.
- [x] Run focused ClientTests/SyncOnceTests, then the complete offline suite.

### Task 2: Harden document contract and readable labels

**Files**

- Modify: sync.py, parse_document, metadata validation and summary rendering.
- Test: test_sync.py, DocumentTests and SyncOnceTests.
- Update: docs/README.md and the generated-format section of this plan.

**Interfaces**

- Keep parse_document(path, text) -> ParsedDocument.
- Keep render_document(metadata) -> str.
- Add private validators only; do not expose a new schema or duplicate editable fields.

- [x] Add failing tests for missing, repeated, out-of-order and truncated current-format regions, invalid metadata types, invalid base hashes, duplicate checklist/item IDs and mismatched reference identity.
- [x] Require the current format's sections exactly once and in order before mutation; continue to parse the known legacy format only for one-way reformatting.
- [x] Validate content, status, labels, checklists, items, base and hashes before three-way comparison.
- [x] Require the remote card ID, board ID and list ID to match the managed document and current configured scope before a write.
- [x] Keep visible title/description/checklists as the local editable sources; treat technical content snapshots as synchronization data only.
- [x] Render associated labels with name, color and full ID from board_labels, and explain content.label_ids as the edit input.
- [x] Add explicit checklist-heading deletion coverage; deletion must remain after item operations and appear in the report.
- [x] Add the hash warning: hashes detect changes/inconsistency and do not prove authenticity.
- [x] Run focused parser/validation tests and the full offline suite.

### Task 3: Make filenames and paths portable and collision-safe

**Files**

- Modify: sync.py, slugify_title, choose_filename, _filename_plan, _assert_safe_plan_file and local scanning.
- Test: test_sync.py, FilenameTests and SyncOnceTests.
- Update: docs/README.md with the heuristic and limits.

**Interfaces**

- Keep slugify_title(title) -> str and choose_filename(status, title, card_id, ...).
- Extend _filename_plan with optional occupied_names while preserving existing callers.
- Keep generated names limited to todo-/done- plus a safe slug and optional deterministic ID suffix.

- [x] Add failing tests for UTF-8 byte truncation, reserved names/variants, full-path limits, image alt text, HTML/data URI removal, unmanaged collisions and duplicate managed IDs.
- [x] Normalize with NFKC, preserve Unicode letters/numbers, sanitize forbidden characters and truncate by both characters and UTF-8 bytes at character boundaries.
- [x] Use the image alt text for simple images, link text for simple links, and a safe card-ID fallback for media-only titles; never query a URL.
- [x] Add the intentional ponytail comment for the limited non-parser Markdown heuristic.
- [x] Validate target path length and reparse-point/junction safety before reads, writes, staging or recovery moves.
- [x] Treat all immediate PLAN Markdown names as occupied, ignore unmanaged Markdown as cards, disambiguate generated names safely and block every duplicate-ID document.
- [x] Preserve suffixes across status changes, card disappearance and title changes; keep global swap staging.
- [x] Run focused filename/path tests and the full offline suite.

### Task 4: Make journal replay, writes and removals recoverable

**Files**

- Modify: sync.py, OperationJournal, pending reconciliation, conflict resolution, removal flow and reporting.
- Test: test_sync.py, SyncOnceTests, ClientTests and new failure-injection cases.
- Update: docs/README.md with pending, recovery and removal procedures.

**Interfaces**

- Keep OperationJournal as the per-card journal; extend its pending record with base, desired projection and operation receipts.
- Keep sync_once(config, api=None, now=None, progress=None) -> report.
- Extend the report with examined, operations, deleted_items, deleted_checklists, recovery_paths and cleanup_skipped without removing existing keys.

- [x] Add failing tests for title limits, uncertain repeatable mutations, pending replay, changed local intent, local edits during HTTP, second-operation failure, disk/permission failures and interrupted rename.
- [x] Validate pending records against an allowlist, card scope, IDs, base and desired projection before using them.
- [x] Rebuild expected remote state from base plus confirmed operations; confirm observable update/label/delete results through GET and never match checklist/item creations by name alone.
- [x] Detect local intent changes while pending and preserve both states in a conflict.
- [x] Persist remote receipts when a file changes during HTTP, preserving the external file and preventing a false synchronized state.
- [x] Validate non-empty card titles against the Trello limit without truncation.
- [x] Count card results separately from remote operations and explicitly count destructive checklist/item operations.
- [x] Preserve resolved conflict artifacts with choice/date metadata.
- [x] Before a 404 removal, revalidate list/board access and perform a second complete inventory; cancel cleanup on global failures.
- [x] Create review artifacts for removals with local edits, conflicts or pending operations; preserve the original bytes and report the recovery path.
- [x] Keep .removed recoverable, do not purge it, and never overwrite unmanaged files.
- [x] Print an explicit no-change result, use stdout for summaries and stderr for errors, and keep credentials/card bodies out of output.
- [x] Run focused journal/removal/report tests and the full offline suite.

### Task 5: Complete orchestration, security documentation and CLI evidence

**Files**

- Modify: sync.py orchestration, local scan and report/CLI output.
- Test: test_sync.py, setup/CLI/security/removal coverage.
- Update: docs/README.md, docs/CHANGELOG.md and this plan.

**Interfaces**

- Keep argparse as the only CLI parser and preserve --setup/--import mutual exclusion.
- Keep normal sync non-interactive; --setup remains the deliberate interactive configuration exception.
- Keep exit codes 0/1/2/3 as currently documented.

- [x] Add failing tests for divergent binding stopping all mutations, corrupt scan disabling cleanup, global authentication priority after partial work and untrusted diagnostics.
- [x] Parse CLI flags before reading .env; preserve network-free --help and --version.
- [x] Stop before mutations for divergent board/list bindings; on other scan errors process only unambiguous identities and disable cleanup.
- [x] Continue independent cards while prioritizing global authentication failure and returning the documented code.
- [x] Report examined cards, created/recreated, updated, renamed, removed, pushed, unchanged, conflicts, failures, operations and recovery paths.
- [x] Verify no browser/credential prompt occurs during normal sync, no speculative CLI option is added and conflict resolution stays in the file.
- [x] Document private-data/Git behavior, token scope, untrusted card instructions, output streams and current resource limitations.
- [x] Keep .env.example, .gitignore and README aligned without removing already-versioned files.
- [x] Run CLI, security and complete offline tests.

### Task 6: Real-list and cross-platform validation

**Files**

- Update: docs/README.md and this plan's execution record only.
- Test: disposable Trello list designated by the owner; no production cards.

- [x] Run the complete import/reference snapshot scenario, including archived cards, comments, attachments, labels, dates and checklists.
- [x] Run template creation, local/remote edits, status changes, labels, checklist/item creation/move/deletion and conflict resolutions.
- [x] Run local deletion, moved-card recovery, archived-in-list behavior, permanent deletion of one disposable card and unchanged rerun.
- [x] Run extreme title/filename and ambiguous-operation scenarios.
- [x] Record actual results for available environments: Windows/PowerShell passed; no Linux distribution or macOS host was available in this workspace.

## Verification gates

- [x] After each task, run its focused tests and then python -m unittest -v test_sync.py.
- [x] Before completion, run py_compile, --help, --version, git diff --check and the complete test suite from the final worktree.
- [x] Inspect the final diff to confirm that only requested source/tests/documentation changed and no credentials or generated private data were added.
- [x] Reconcile every checkbox in this plan against command output or real-list evidence; all planned items are now evidenced.
- [x] Bump the runtime SemVer for behavior changes and record the same release in CHANGELOG.md.

## Execution record

| Task | Date | Result | Evidence | Pending |
| --- | --- | --- | --- | --- |
| Baseline audit | 14/09/2026 | 82 offline tests passed | python -m unittest -q test_sync.py; py_compile; CLI checks | All tasks below |
| Task 1 | 14/09/2026 | Complete offline and real-list verified | 102-test suite plus disposable-list resource snapshot | None for the available target |
| Task 2 | 14/09/2026 | Complete offline and real-list verified | strict parser, identity, labels, deletion and reference snapshot tests | None for the available target |
| Task 3 | 14/09/2026 | Complete offline and Windows verified | filename/path, unmanaged, suffix and extreme-title scenario | Linux/macOS unavailable |
| Task 4 | 14/09/2026 | Complete offline and real-list verified | journal, pending, conflict, recovery, deletion and report scenarios | None for the available target |
| Task 5 | 14/09/2026 | Complete offline | CLI/security/output tests and documentation | None offline |
| Task 6 | 14/09/2026 | Complete on authorized disposable list | Windows/PowerShell real run; 1,891 requests; 5 generated cards cleaned; all five Task 6 scenarios passed | Linux/macOS unavailable |
