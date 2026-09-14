# Changelog

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
