# Changelog

## [1.3.0] - 2026-09-18

### Added

- Converted plain `todo-*.txt` files into minimum-field Markdown cards before normal synchronization, then moved their sources to `PLAN/.converted/`.
- Updated `--import` to use the same pre-sync conversion and `.converted` handling.

## [1.2.5] - 2026-09-18

### Fixed

- Created checklist entries at the end, then restored the requested order and completion state before verifying a new card.
- Automatically recovered confirmed checklist/item creations whose Trello positions differed, using recorded IDs without creating duplicate cards or entries.
- Versioned the generated card template, added card limits and checklist marker syntax, and made sync create a missing model or upgrade an older managed model in place.

## [1.2.4] - 2026-09-18

### Fixed

- Standardized synchronization, import and CLI failure guidance in English.

## [1.2.3] - 2026-09-18

### Fixed

- Preserved existing Trello titles and descriptions over SyncAssist's write limits, while keeping those limits for new or edited values.
- Included the underlying projection-validation reason in incomplete-card errors.

## [1.2.2] - 2026-09-18

### Fixed

- Included card names, detailed remote failure causes and suggested next steps in failure logs; partial runs and skipped cleanup are now explicit.
- Shortened generated card filenames when a deep Windows project path would exceed `MAX_PATH`, while keeping the full card title in the document.

## [1.2.1] - 2026-09-17

### Documentation

- Corrected the installation, CLI and exit-code guidance to match the setup and synchronization confirmation prompts.
- Recorded the configuration and credential-protection updates that were missing from the 1.2.0 release notes.
- Documentation-only update; the runtime version remains `1.2.0`.

## [1.2.0] - 2026-09-17

### Added

- Excluded archived Trello cards from synchronization, moved existing local files to recovery, and recreated them from current data after unarchiving.
- Required `TRELLO_BOARD_URL`, reused valid saved setup values, and saved a verified board URL before list selection so setup can resume. Existing `.env` content is preserved.
- Made setup add `.env`, `PLAN/` and `sync.py` to `.gitignore` without replacing existing rules.
- Checked all required settings before sync or import, asked before starting setup when settings are missing, and confirmed whether to start synchronization after setup.

## [1.1.1] - 2026-09-14

### Validation

- Completed the authorized real-list validation on `teste/projeto1` under Windows/PowerShell, covering import, reference snapshots, edits, status, labels, checklists/items, conflicts, recovery, archival, deletion, extreme filenames and ambiguous card creation.
- Verified cleanup of all five generated cards and the temporary workspace; Linux/macOS validation remains unavailable because those environments were not present.

## [1.1.0] - 2026-09-14

### Added

- Added board custom-field definitions, card votes and Power-Up data to raw references when available.
- Added per-resource status/error reporting with previous-reference retention for failed complementary reads.
- Added UTF-8 filename bounds, unmanaged-name collision handling, reparse-point checks and duplicate-ID scan protection.
- Added journal base/desired snapshots, operation receipts, destructive-operation counts, recovery paths and explicit no-change output.

### Fixed

- Enforced current Markdown section ordering while retaining one-way legacy reformatting.
- Rendered associated label names, colors and full IDs in the read-only summary.
- Prevented cleanup after incomplete scans, ambiguous checklist/item POSTs, changed local intent or local edits during remote writes.
- Revalidated list/board scope before 404 recovery and preserved resolved conflict artifacts.
- Updated documentation and offline evidence to 102 passing tests.

## [1.0.3] - 2026-09-14

### Documentation

- Audited PLAN.md against the implementation and removed completed checklist items.
- Recorded the current evidence: 82 offline tests passed, syntax/CLI checks passed and real Trello validation remains pending.
- Updated README.md with the current runtime scope, fetched resources and known limitations.
- No runtime behavior changed; the script version remains 1.0.2.

## [1.0.2] - 2026-09-14

### Fixed

- Added simple flushed progress messages, retry/rate-limit wait notices and elapsed request counts.
- Avoided redundant full card reads when no conflict exists.
- Reconciled legacy read-only conflicts so remote completion can update `todo-` files without deleting historical artifacts.
- Printed conflict status, reason and artifact path as soon as a conflict is created.

## [1.0.1] - 2026-09-14

### Fixed

- Preserved imported description newlines and import provenance after card recovery.
- Separated editable synchronization state from volatile read-only Trello references.
- Reconciled unconfirmed card creation without repeating POST requests.
- Hardened pagination, incomplete inventory handling, due-date clearing and conflict filenames.

## [1.0.0] - 2026-09-14

### Added

- Bidirectional synchronization between Trello cards and Markdown planning files.
- Interactive `python sync.py --setup` configuration wizard.
- Automatic native due-date completion status handling.
- Human-readable card documents with a reusable `PLAN/_modelo-card.md` template.
- `python sync.py --import` for converting `PLAN/*.txt` files into Trello todo cards.

### Changed

- Markdown documents prioritize readable title, description, status and read-only information at the top.
- Completion is represented by the native Trello `dueComplete` checkbox instead of a required `Done` label.
- Setup runs the initial synchronization after writing `.env`.

### Fixed

- Trello authentication and transport error handling.
- Preservation of local files during conflicts, partial failures and card recovery.
- Safe atomic writes and credential-free diagnostic output.
