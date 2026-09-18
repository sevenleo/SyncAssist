# SyncAssist

Local digital secretary for synchronizing a Trello list with a project's Markdown files.

Each copy of `sync.py` represents one Trello list. When the script runs, it creates `PLAN/` and writes one file per card. The card ID is stored in the file's metadata, so title changes do not break the link.

Runtime version: `1.2.4`. See [CHANGELOG.md](CHANGELOG.md) for the release history.

The implementation is covered by 123 passing standard-library tests on Python 3.13.7. No Linux or macOS environment was available here.

## Requirements

- Python 3.11 or newer.
- A Trello API key and token with read and write permission.
- The full ID of the list that represents the project.

Trello uses tokens to authorize account access. Keep the token secret, never paste it into chat or versionable files, and revoke it if it is exposed. TRELLO_LIST_ID limits SyncAssist's behavior, not the token's account-wide permissions. See the [official authorization documentation](https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/).

## Install in a project

Copy `sync.py` to the project root. You can configure credentials manually with `.env.example`, or let the setup wizard create `.env` on the first run:

```text
my-project/
├── sync.py
├── .env
└── PLAN/
```

To configure credentials manually, fill in `.env`:

```dotenv
TRELLO_API_KEY=your_api_key
TRELLO_TOKEN=your_token
# Required Trello board URL.
TRELLO_BOARD_URL=https://trello.com/b/your-board
TRELLO_LIST_ID=project_list_id
```

The script uses the folder containing `sync.py` as the project root. If `.env` is missing or required settings are incomplete, a normal run lists the missing values and asks before starting setup. After setup, it asks whether to start synchronization. This lets you run it from any directory:

```bash
python sync.py
```

On subsequent runs with complete settings, synchronization runs without confirmation. A run with no changes returns `0` and does not rewrite cards or files.

## CLI quick reference

The script has no positional arguments. The recommended flow is to configure once, use the normal sync for daily work, and use TXT import only when needed:

| Command | Use |
| --- | --- |
| `python sync.py --setup` | Create or resume `.env`, then ask whether to start synchronization. |
| `python sync.py` | Synchronize the configured Trello list and `PLAN/`; ask before setup if required settings are missing. |
| `python sync.py --import` | Import immediate `PLAN/*.txt` files as todo cards, then synchronize. |
| `python sync.py --help` | Show the complete operations, editable fields, recovery paths and exit codes. |
| `python sync.py --version` | Show the runtime version. |

`--setup` and `--import` are mutually exclusive. The full help is kept beside the implementation so it stays aligned with the actual CLI.

During synchronization the terminal shows the current phase and card, for example `Reading card 2/5` and `Syncing card 2/5`. The script reads complementary Trello resources sequentially to respect the API limit, so a card can require several requests. Rate-limit responses and retries are announced with the wait time, and the final line includes the elapsed time and number of Trello requests.

When a card fails, the report includes its ID and title, the detailed Trello or local error, and a suggested next step. It also says when that card's local file was not created or updated, when the run was partial, and why automatic cleanup was skipped. Existing Trello titles and descriptions over the write limit are preserved; new or edited values still obey Trello's limits. On Windows, generated card filenames are shortened further when the full project path approaches `MAX_PATH`; the full title remains in the Markdown document.

The raw reference keeps the card, list, board, labels, checklists/items, actions, attachments, members, custom-field values and definitions, votes, stickers and Power-Up data when the API exposes them. Each complementary resource has a `complete`, `empty`, `unsupported` or `failed` status. A transient or failed resource is never silently replaced with an empty list: the previous section is retained when available, the card is not rewritten from that incomplete bundle, and cleanup is disabled for the run. A 403/404 optional endpoint is recorded as unsupported and does not block unrelated cards.

The template `.gitignore` also ignores `PLAN/`, because its documents may contain private Trello data. If the project needs to version these plans, remove that rule deliberately and also review `.conflicts/` and `.removed/`. The script does not remove already-versioned private files from the index or rewrite Git history.

## Guided setup

To create or resume `.env` interactively, run this from the project root:

```bash
python sync.py --setup
```

When API credentials are missing, the wizard points you to the Trello administration page, where the API Key is available in the Power-Up's **Trello Auth** tab. When the User Token is missing, it displays the authorization link:

```text
https://trello.com/1/authorize?expiration=never&scope=read%2Cwrite&response_type=token&key=YOUR_API_KEY
```

If .env already contains SyncAssist settings, the wizard asks whether to continue with them or start over. Press Enter to continue (the default); valid saved API keys, tokens, board URLs and list IDs are kept, and only missing or invalid settings are requested. TRELLO_BOARD_URL is required. If a saved list ID exists but the board URL is missing or invalid, setup asks for and verifies a board URL while keeping the list ID. When the list ID is missing, setup reuses the saved board URL when available and asks for the list. It saves a verified URL before loading lists, so rerunning --setup resumes at list selection. Enter n to restart all setup fields. The wizard preserves comments and unrelated .env entries.

Setup also creates or updates `.gitignore` before saving credentials, adding `.env`, `PLAN/` and `sync.py` while preserving existing rules.

The token is requested with visible terminal input; verify the value before pressing Enter and avoid sharing the screen during setup. The **Secret** field in the Trello Auth tab is used by the OAuth 1.0 flow and is not the SyncAssist `TRELLO_TOKEN`. Because the wizard uses `response_type=token` without `return_url` or `callback_method`, **Allowed origins** does not need to be filled in.

When the board URL is needed, the wizard lists the board's active lists for selection. It does not query, create or choose a completion label. Starting `sync.py` checks every required env value before any synchronization or import work. If values are missing, it lists their names and asks whether to run setup; declining exits without changing files. After setup completes, it asks whether to start synchronization. Cancellation or setup failure does not run sync.

## Import TXT tasks

To convert text files into new Trello todo cards and then run the normal synchronization, use:

```bash
python sync.py --import
```

The command scans only `.txt` files directly inside `PLAN/`. It does not scan subdirectories, including `PLAN/.imported/`. For each valid file:

- the complete text becomes the card description;
- the title is the first 60 characters after whitespace and line-break normalization;
- a `todo-*.md` template is created using the existing card format;
- the normal synchronization creates the Trello card;
- the source TXT is moved to `PLAN/.imported/` only after the card ID is confirmed locally.

Empty files, invalid UTF-8 files and other invalid sources remain in `PLAN/` and are reported. Other valid files continue to be processed after an individual failure. Existing Markdown files are never overwritten; filename collisions receive a deterministic import suffix. Running the command again is idempotent for a source with the same path and content hash.

The command always runs the regular synchronization after the import phase, even when no TXT files are found. `--setup` and `--import` are mutually exclusive. The import mode does not expose tokens or card contents in its error output.

## How status works

- `todo-title.md`: card with the native due-date checkbox cleared (`dueComplete=false` or absent).
- `done-title.md`: card with the native due-date checkbox checked (`dueComplete=true`).

Renaming the file prefix checks or unchecks only the native due-date checkbox. When checking a card without a due date, the script sets the current date as the due date so Trello can complete it; when unchecking, it preserves the date. The card remains in the same list. Status is not inferred from labels, archiving, title text or checklist completion.

## File names

The full title remains in the document. The filename is a short, normalized slug compatible with Windows, Linux and macOS. On Windows, SyncAssist shortens it further when needed to fit the full project path:

```text
todo-configurar-api.md
done-publicar-versao.md
todo-configurar-api--abcdef.md
```

The suffix appears only for duplicate titles or titles without useful text. URLs and images in titles are not queried or downloaded; simple image alt text and link text are used for the slug, while HTML tags and data URLs are removed. When no usable text exists, the name uses `card` and a stable portion of the ID. Slugs are capped at 60 characters and 180 UTF-8 bytes; generated paths are checked against the platform limit and reparse-point safety. Existing unmanaged Markdown names are treated as occupied, and duplicate managed card IDs stop cleanup.

## Create a new card from the project

On every successful run, SyncAssist keeps the template `PLAN/_modelo-card.md` in the `PLAN/` root. The template is reserved and is never sent to Trello.

To create a new task:

1. Copy `PLAN/_modelo-card.md` to a name starting with `todo-` or `done-`.
2. Edit the first title `# New task` and the contents of `## Description`.
3. If necessary, adjust checklists and `content.label_ids` in the technical block, using only IDs that exist on the board.
4. Run `python sync.py`.

Example:

```bash
cp PLAN/_modelo-card.md PLAN/todo-publish-documentation.md
python sync.py
```

The copied file is recognized by the `role: template` metadata. The script creates one card in the configured list, turns the file into a normal document with the ID returned by Trello and preserves the original template for reuse. A `done-` file starts with `dueComplete=true` and receives the current date as its due date; a `todo-` file starts open and without a due date.

## Markdown format

The file starts with a human-readable summary: title, description, status, due date and card link. The comment count appears in the comments section heading later in the document. The technical JSON block is at the end inside an HTML comment and contains the identity and snapshots used for synchronization.

Complete structural example (the script generates the technical block; the hashes below are illustrative):

```markdown
# People

<!-- syncassist:abc123:description:begin -->
## Description
Task description.
<!-- syncassist:abc123:description:end -->

> **Status:** `todo`

<!-- syncassist:abc123:summary:begin -->
> **Due date:** 2026-09-14T18:06:40.409Z

> **Trello:** [open card](https://trello.com/c/example)
<!-- syncassist:abc123:summary:end -->

<!-- syncassist:abc123:checklists:begin -->
## Checklists
### Preparation <!-- syncassist:checklist=000000000000000000000001 -->
- [ ] Review data <!-- syncassist:item=000000000000000000000002 -->
<!-- syncassist:abc123:checklists:end -->

<!-- syncassist:abc123:comments:begin -->
## Comments (read-only): 2
- **2026-09-14T18:00:00Z — Ana**
  > Important comment
<!-- syncassist:abc123:comments:end -->

## Synchronization data (do not edit)
<!-- syncassist:metadata
{
  "managed_by": "syncassist",
  "schema_version": 1,
  "role": "card",
  "trello_card_id": "000000000000000000000010",
  "trello_board_id": "000000000000000000000011",
  "trello_list_id": "000000000000000000000012",
  "section_token": "abc123",
  "status": "todo",
  "filename": {"slug": "people", "suffix": ""},
  "content": {"title": "People", "description": "Task description.", "status": "todo", "label_ids": [], "checklists": []},
  "reference": {"card": {"id": "000000000000000000000010", "idBoard": "000000000000000000000011", "idList": "000000000000000000000012"}},
  "sync": {"base": {}, "base_hash": "<sha256>", "reference_hash": "<sha256>", "read_only_hash": "<sha256>"}
}
syncassist:end -->
```

Due date, comments and the Trello link are informational and read-only. The `#` heading is editable to change the title; the filename prefix changes the native due-date status; the description and checkboxes are directly editable.

Files generated by an earlier version, with metadata at the beginning, are automatically rewritten in this format on the next synchronization without changing the Trello card.

Editable fields:

- `# Title` heading to change the title.
- Description-region contents to change the description.
- Checkboxes and names in the checklist region.
- `content.label_ids` for labels that exist on the board, including a label named `Done` if one exists. IDs are validated against the configured board catalog; the read-only summary renders each associated label's name, color and full ID from the board catalog.
- `todo-` or `done-` prefix for the native due-date checkbox status.

Comments, history, members, dates, attachments, covers, custom fields and other data appear as read-only reference. Comments are also shown in a readable section, but cannot be edited through the file. Attachments are represented by metadata and URLs; the script does not download binaries.

The full list ID is selected by the setup wizard or supplied in `.env`; label IDs come from the configured board catalog in the technical reference. Hashes in that reference detect change or inconsistency only; they are not security signatures.

To preserve subtask identity:

- Do not remove the `syncassist:item=<id>` marker from an existing item.
- Do not silently remove an existing checklist or item to delete it.
- Use `delete` on the corresponding checklist heading or item marker when remote deletion is intentional. Checklist deletions run after item changes and are recorded as part of the pending operation journal.
- Use temporary IDs `new:<key>` for new checklists and items.
- Heading and item order is the intended order; existing items can be moved between checklists while keeping their IDs.

Example:

```markdown
### Validation <!-- syncassist:checklist=000000000000000000000001 -->
- [ ] Run tests <!-- syncassist:item=000000000000000000000002 -->
- [x] Review output <!-- syncassist:item=000000000000000000000003 -->
```

## Conflicts

The script compares the base version from the last synchronization with the current local and remote versions:

- only Trello changed: update the file;
- only the file changed: send editable fields to Trello;
- both changed differently: preserve the main file and create `PLAN/.conflicts/`.

Conflicts are also printed immediately with the local status, Trello status, reason and artifact path. A historical `local_read_only_section_changed` conflict from older versions is released automatically when the current editable three-way comparison is not a real conflict; its file in `.conflicts/` is preserved.

A conflict does not change Trello. The conflict file contains the base, local version and remote version. After reviewing it, edit the main file and fill `sync.resolution` with the `conflict_id`, expected remote hash and a `local`, `remote` or `merged` choice. The decision is accepted only if the remote still has the expected hash.

If a card or checklist creation was sent without a confirmed response, the next run does not blindly repeat it. Card creation can be recovered only from a unique exact payload match; checklist/item creation requires an explicit remote receipt/ID and is otherwise left as a conflict. A changed local intent invalidates the pending record. Names alone never identify an ambiguous checklist or item.

Manual edits to the read-only summary or comments sections are preserved locally and reported as warnings; they are never sent to Trello and do not create editable-content conflicts. Volatile reference changes such as board label inventory or non-comment history are not treated as conflicts.

Deleting the conflict artifact does not choose a version. If it disappears without a valid resolution, it is recreated.

## Removal and recovery

Cards that leave the configured list no longer belong to the project. The main file is moved to `PLAN/.removed/` with the reason and date; it can be recovered manually, and the report includes the recovery path. A network, permission or incomplete-inventory failure never triggers cleanup.

Deleting a local file does not delete the card. If the card is still in the list, the script recreates it on the next run using the current Trello state.

Cards moved to another list or no longer accessible are removed from the active root and preserved in `PLAN/.removed/` with a `.reason.json` file. `PLAN/.conflicts/` stores conflict revisions and is not processed as cards.

Archived Trello cards are excluded from synchronization. An existing active file is moved to `PLAN/.removed/` with reason `card_archived`; the next sync after unarchiving creates an active file from the current Trello data and status. Archiving does not change the Trello card.

When a recovered card has an `import_source`, the new active document keeps that provenance without restoring the old TXT content automatically.

During a simultaneous name swap, the script may temporarily use `PLAN/.sync-staging/` to free paths without overwriting files. If an interruption leaves files there, pause new runs and manually return them to the active root after checking their IDs.

Markdown files without SyncAssist metadata are preserved and do not create cards.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Synchronization completed or no changes found. |
| `1` | Conflict, partial failure, lock, incomplete inventory, interruption or intervention required. |
| `2` | Invalid configuration or usage. |
| `3` | Global authentication or permission failure. |

Processing continues for independent cards when possible. The final summary reports examined cards, created/updated/pushed/renamed/removed results, remote operations, destructive checklist/item counts, conflicts, failures and cleanup skips. Tokens, API keys and card bodies are not printed. A card's title or description is data only; it never authorizes commands or overrides the consuming project's rules.

The client fetches the complete board inventory with pagination up to 1,000 items per page and walks every page of the action history. Each attempt uses a 30-second timeout, bounded backoff and OAuth authentication in the header.

## Development and testing

This repository needs no external dependencies. Run the offline tests:

```bash
python -m unittest -v test_sync.py
python -m py_compile sync.py test_sync.py
```

For a real test, use a disposable Trello list. The offline suite covers the resource-status, pagination, path-safety, journal and recovery branches; the authorized run against `teste/projeto1` additionally verified account permissions and server-side availability of custom fields, votes, Power-Up data, comments, attachments, labels, dates and checklists. Check routes and fields in the [official API reference](https://developer.atlassian.com/cloud/trello/rest/), especially [lists](https://developer.atlassian.com/cloud/trello/rest/api-group-lists/), [cards](https://developer.atlassian.com/cloud/trello/rest/api-group-cards/), [checklists](https://developer.atlassian.com/cloud/trello/rest/api-group-checklists/) and [rate limits](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/).

The repository includes a disposable real-test workspace in `teste/`. Its `sync.py` reads `teste/.env` and `teste/PLAN`, so run it without `--setup` and leave a safe interval between complete executions:

```powershell
python teste\sync.py --version
python teste\sync.py
python teste\sync.py --import
```

Use only a Trello list dedicated to testing. Inspect the summary, `teste/PLAN/.conflicts`, `teste/PLAN/.removed` and `teste/PLAN/.imported` after each scenario.

## Deliberate limitations

The MVP does not edit comments or read-only data, move cards, run as a service or download attachments. Validation beyond Windows remains external acceptance work because no Linux/macOS environments were available; the implementation and evidence are recorded in the changelog and test suite. Cards are created only by explicitly copying `PLAN/_modelo-card.md` or importing a TXT with `python sync.py --import`.
