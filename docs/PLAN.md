# PLAN.md — SyncAssist

Consolidation date: 14/09/2026. This is the residual implementation and validation plan after the current-state audit.

## Current status

SyncAssist runtime version 1.0.2 contains the offline implementation for one Trello list: configuration, REST transport, paginated inventory, Markdown card documents, bidirectional editable synchronization, native due-date status, labels, checklists, conflicts, recovery, locking, template-based creation and TXT import.

Evidence collected in this audit:

- Python 3.13.7 on Windows.
- 82 offline unittest cases passed.
- sync.py and test_sync.py compile successfully.
- --help and --version work without .env or network access.
- No real Trello list was used in this audit; integration and cross-platform validation remain pending.

The completed items were removed from the active checklist below. Remaining checkboxes are incomplete implementation work, missing test evidence or real Trello validation. This document does not authorize production-card experiments or commits.

## 1. Scope retained

| Topic | Decision |
| --- | --- |
| Technology | Python 3.11+ and standard library only. |
| Distribution | One portable sync.py per project, with local .env configuration. |
| Binding | TRELLO_LIST_ID identifies the project list; names never determine identity. |
| Direction | Bidirectional for title, description, checklists, label associations and completion status. |
| Identity | Full Trello IDs live in the Markdown technical metadata. |
| Local state | Base snapshot, hashes, pending operations and conflicts live in the card document. |
| Status | todo-/done- maps to Trello dueComplete; cards never move to represent status. |
| Creation | Only an explicit copy of PLAN/_modelo-card.md or a valid --import source creates a card. |
| Removal | A missing local file never deletes a card. Cards leaving scope are moved to PLAN/.removed/ after the required checks. |
| Conflicts | Divergent local and remote edits preserve base/local/remote and require an explicit resolution. |
| Security | .env stays outside Git; paths, IDs and remote text are untrusted; logs exclude credentials and card bodies. |

The reference scale of approximately 200 cards is not a product limit. A hash detects inconsistency/change only; it is not a cryptographic authenticity signature.

The MVP remains manual and non-interactive during normal synchronization. It does not add a daemon, scheduler, webhook, GUI, dashboard, custom API, database, SDK, packager, dry-run mode or automatic line-level merge. It does not edit comments, members, dates, attachments, covers, votes, custom fields or Power-Up data remotely, and never downloads binaries or visits URLs from card content.

## 2. Current implementation baseline

The following baseline is already implemented and documented in README.md and the tests, so it is no longer repeated as a pending task:

- Copy-based installation, .env parsing and validation, root resolution and board/list binding.
- Standard-library Trello client with HTTPS origin pinning, OAuth header, timeout, bounded retry, rate-limit spacing and redacted errors.
- Complete board-card inventory with filtering by list, archived-card coverage, deduplication and paginated board labels/actions.
- Markdown v1 layout with stable card identity, editable title/description/checklists/labels/status, read-only reference data, safe metadata serialization and legacy reformatting.
- Three-way synchronization, semantic hashes, idempotent unchanged runs and remote rereads before writes.
- Checklist/item identity, reordering, moves, explicit item/checklist deletion markers, temporary IDs and pending operation journaling.
- Portable slug generation, deterministic collision suffixes, title preservation, global rename planning and swap staging.
- Native due-date completion, ordinary label association, explicit template creation and idempotent TXT import.
- Conflict artifacts and versioned resolution, recoverable removals, local-file recreation, lock handling, atomic writes and credential-free reporting.

## 3. Remaining implementation work

### 3.1 Remote completeness and failure semantics

- [ ] Import custom-field definitions together with custom-field values when the board and token expose them.
- [ ] Import votes and shared Power-Up data when exposed, or record their explicit unavailability instead of implying a complete snapshot.
- [ ] Fetch every page of every resource that exposes pagination, not only the currently covered board-label and action cursors.
- [ ] Preserve already collected reference sections when a complementary request fails, while marking the card collection incomplete.
- [ ] Distinguish an explicitly unsupported resource from a transient failure in the reference snapshot and report both states clearly.
- [ ] Confirm remote state with GET before repeating an uncertain update, label association or sub-item deletion.

### 3.2 Document validation and readable reference data

- [ ] Require every generated/read section exactly once and in the defined order; reject missing, repeated, out-of-order or truncated markers before any mutation.
- [ ] Validate all metadata types, required values, checklist/item ID uniqueness and base_hash integrity before comparing versions.
- [ ] Prevent a manually edited card ID from authorizing writes to another card; validate card ownership and the configured board/list before every write.
- [ ] Display each associated label with name, color and ID while keeping content.label_ids as the only editable association input.
- [ ] Keep title and description as single editable sources rather than allowing competing editable copies in the technical block.

### 3.3 Filename and filesystem edge cases

- [ ] Enforce both the 60-character slug limit and the 180-byte UTF-8 limit at character boundaries.
- [ ] Handle Windows reserved names and extension variants exactly as specified, including the card- fallback for useful text.
- [ ] Validate total target-path length and preserve the original document when the filesystem rejects the destination.
- [ ] Use image alt text for simple Markdown images; remove data URIs and HTML tags from slug input without querying URLs.
- [ ] Keep the limited Markdown slug heuristic documented and add the planned ponytail comment if the heuristic remains intentionally non-parsing.
- [ ] Treat unmanaged files as occupied names, resolve safe collisions where possible and block every duplicate-ID file together rather than accepting one.
- [ ] Reject PLAN and control folders/files implemented as unsafe symlinks, junctions or reparse points outside the project.

### 3.4 Remote writes, resumption and local integrity

- [ ] Validate non-empty titles against the API's current limits without truncating the Trello title.
- [ ] Keep explicitly marked deletions last and report destructive sub-item operation counts separately from card counts.
- [ ] Rebuild expected remote state from the base and confirmed operations before resuming; validate pending operation types, IDs, scope and desired projections.
- [ ] Handle local intent changes while pending without mixing batches silently; preserve both states for review.
- [ ] When a local file changes after a remote write, persist the response/receipt in a conflict while preserving the external edit.
- [ ] Preserve a recoverable complete document during renames, block duplicate IDs after interrupted swaps and cover full-disk, permission, open-file and invalid-path failures.
- [ ] Retain a resolved conflict artifact as an inactive record containing the decision and date.

### 3.5 Scope, removals and orchestration

- [ ] Stop before any mutation when a managed file has a divergent board/list binding; do not continue with unrelated mutations in that run.
- [ ] Disable cleanup whenever local scanning is incomplete or corrupted, while still processing cards with unambiguous identity.
- [ ] Before removing after a 404, reconfirm list/board access and obtain a second complete inventory; cancel cleanup after any global post-inventory failure.
- [ ] For removals with local edits, conflicts or pending operations, create the related review information, return 1 and report the recovery path.
- [ ] Ignore unmanaged Markdown even when its filename starts with todo- or done-, and never overwrite it to satisfy a generated filename.
- [ ] Report explicit no-change runs and distinguish examined cards, card-level results and individual remote operations.

### 3.6 Documentation and distribution gaps

- [ ] Add a complete parseable fictional card example, including technical metadata and test-derived hashes.
- [ ] Add edit examples for title, description, ordinary labels, status, checklist/item creation and explicit checklist/item deletion.
- [ ] Document recovery after ambiguous operations, .removed backups, stale locks, interrupted renames and duplicate IDs.
- [ ] Document the difference between network failure, missing card, moved card and archived card.
- [ ] State that hashes detect change/inconsistency but do not prove authenticity, and document stdout/stderr usage without permanent logs.

## 4. Offline validation still pending

The current suite proves the main happy paths and several safety cases, but it does not yet prove all requirements in the sections above.

- [ ] Cover full configuration isolation: missing .env, empty values, invalid credentials, root resolution from another working directory and divergent binding with zero writes.
- [ ] Cover all filesystem naming cases: UTF-8 byte truncation, reserved variants, path-length failure, HTML/data URI input, image alt text, unmanaged collisions and duplicate IDs.
- [ ] Cover strict document structure: invalid JSON, unknown schema, repeated/missing/out-of-order/truncated regions and all metadata/checklist validation failures.
- [ ] Cover every B/L/R decision branch, title-edit filename update, slug-only rename behavior and all label/status combinations.
- [ ] Cover HTTP 400, 401, 403, 404, 429, 5xx, invalid JSON and timeout classification, including global failure after partial work.
- [ ] Cover failed complementary resources, explicit unsupported resources and archived cards still belonging to the list.
- [ ] Cover a valid empty list and verify that it is not confused with an incomplete inventory.
- [ ] Cover pending replay, uncertain repeatable mutations, second-operation failure, local edits during HTTP, disk/permission failures and interrupted renames.
- [ ] Cover absent-card removal after two inventories, pending/conflicted removals, unsafe reparse points, unmanaged todo-/done- files and returning cards.
- [ ] Cover report metrics, destructive operation reporting and the absence of credentials/card bodies in every diagnostic path.

Expected offline command:

    python -m unittest -v test_sync.py

## 5. Real Trello validation pending

Run only against a disposable list designated by the owner, with credentials stored locally.

- [ ] Import a card containing description, two checklists, labels, comment, attachment and dates; compare the raw/reference snapshot.
- [ ] Create a card from a copied template and confirm the remote ID, file conversion and template preservation.
- [ ] Change title/description remotely and locally and verify both directions.
- [ ] Check/uncheck items, create checklist/items, move an item and explicitly delete test objects.
- [ ] Associate/disassociate an ordinary label without changing its board name or color.
- [ ] Rename todo- to done- and back; verify dueComplete and no list movement.
- [ ] Check/uncheck the native due-date checkbox in Trello; verify status is independent of labels and archiving.
- [ ] Exercise repeated, very long, Unicode, image, URL, reserved-name and collision titles.
- [ ] Create divergent local/remote edits and resolve local, remote and merged choices, including an obsolete remote hash.
- [ ] Delete a local file and verify recreation without a Trello DELETE.
- [ ] Move a test card to another list and verify recoverable removal from the original project.
- [ ] Archive a card that remains in the configured list and verify it remains represented.
- [ ] Permanently delete only a disposable test card and verify the absence/recovery behavior.
- [ ] Run again without changes and verify no unnecessary Trello writes or Markdown rewrites.
- [ ] Record the systems actually tested; do not claim portability from code review alone.

## 6. Completion acceptance

- [ ] Every remaining implementation item is completed or explicitly accepted as a documented limitation.
- [ ] Offline tests cover conflict, removal, partial-failure, pending-operation and filesystem-integrity behavior.
- [ ] README matches the parser and documents the actual runtime behavior and limitations.
- [ ] Runtime version 1.0.2 and schema_version 1 remain consistent.
- [ ] A real Trello test list has been validated, or the pending status is retained explicitly.
- [ ] Windows, Linux and macOS results are recorded only when actually run.
- [ ] No commit is created without explicit authorization.

## 7. Execution record

| Area | Date | Result | Evidence | Pending |
| --- | --- | --- | --- | --- |
| Runtime baseline | 14/09/2026 | Implemented | sync.py, .env.example, .gitignore, docs/README.md | Residual items in section 3 |
| Offline tests | 14/09/2026 | 82 passed | python -m unittest -v test_sync.py | Expand coverage in section 4 |
| Syntax | 14/09/2026 | Passed | python -m py_compile sync.py test_sync.py | — |
| CLI | 14/09/2026 | Passed | python sync.py --help; python sync.py --version | — |
| Trello integration | 14/09/2026 | Not run | Requires owner-designated test list and local credentials | Section 5 |
| Windows | 14/09/2026 | Offline validation only | PowerShell and Python 3.13.7 | Real-list validation |
| Linux | — | Not validated | — | Run offline and real-list checks |
| macOS | — | Not validated | — | Run offline and real-list checks |

The current implementation is suitable for controlled Trello validation, not for claiming complete requirement coverage. Keep the residual items visible until their implementation or evidence exists.
