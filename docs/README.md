# SyncAssist

Local digital secretary for synchronizing a Trello list with a project's Markdown files.

Each copy of `sync.py` represents one Trello list. When the script runs, it creates `PLAN/` and writes one file per card. The card ID is stored in the file's metadata, so title changes do not break the link.

Runtime version: `1.0.2`. Documentation audit: 2026-09-14, recorded as the documentation-only `1.0.3` changelog entry. See [CHANGELOG.md](CHANGELOG.md) for the release history.

The offline implementation is covered by 82 passing standard-library tests on Python 3.13.7. Real Trello validation has not been run in this workspace, so production use still requires a disposable test list and locally supplied credentials.

## Requirements

- Python 3.11 or newer.
- A Trello API key and token with read and write permission.
- The full ID of the list that represents the project.

Trello uses tokens to authorize account access. Keep the token secret, never paste it into chat or versionable files, and revoke it if it is exposed. TRELLO_LIST_ID limits SyncAssist's behavior, not the token's account-wide permissions. See the [official authorization documentation](https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/).

## Install in a project

Copy `sync.py` and `.env.example` to the project root and rename the `.env.example` copy to `.env`:

```text
my-project/
├── sync.py
├── .env
└── PLAN/
```

Fill in `.env`:

```dotenv
TRELLO_API_KEY=your_api_key
TRELLO_TOKEN=your_token
TRELLO_LIST_ID=project_list_id
```

The script uses the folder containing `sync.py` as the project root. This lets you run it from any directory:

```bash
python sync.py
```

The command is automatic and does not ask for confirmation. A run with no changes returns `0` and does not rewrite cards or files.

During synchronization the terminal shows the current phase and card, for example `lendo card 2/5` and `sincronizando card 2/5`. The script reads complementary Trello resources sequentially to respect the API limit, so a card can require several requests. Rate-limit responses and retries are announced with the wait time, and the final line includes the elapsed time and number of Trello requests.

The template `.gitignore` also ignores `PLAN/`, because its documents may contain private Trello data. If the project needs to version these plans, remove that rule deliberately and also review `.conflicts/` and `.removed/`. The script does not remove already-versioned private files from the index or rewrite Git history.

## Guided setup

To create or replace `.env` interactively, run this from the project root:

```bash
python sync.py --setup
```

The wizard points you to the Trello administration page, where the API Key is available in the Power-Up's **Trello Auth** tab. It then displays the User Token authorization link:

```text
https://trello.com/1/authorize?expiration=never&scope=read%2Cwrite&response_type=token&key=YOUR_API_KEY
```

The token is requested with visible terminal input; verify the value before pressing Enter and avoid sharing the screen during setup. The **Secret** field in the Trello Auth tab is used by the OAuth 1.0 flow and is not the SyncAssist `TRELLO_TOKEN`. Because the wizard uses `response_type=token` without `return_url` or `callback_method`, **Allowed origins** does not need to be filled in.

After receiving the board URL, the wizard lists active lists for selection. It does not query, create or choose a completion label. Setup replaces an existing `.env` only after confirmation and, when complete, immediately runs synchronization to reflect current tasks. Cancellation or setup failure does not run sync.

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

The full title remains in the document. The filename is a short, normalized slug compatible with Windows, Linux and macOS:

```text
todo-configurar-api.md
done-publicar-versao.md
todo-configurar-api--abcdef.md
```

The suffix appears only for duplicate titles or titles without useful text. URLs and images in titles are not queried or downloaded; when no usable text exists, the name uses `card` and a stable portion of the ID.

## Create a new card from the project

On every successful run, SyncAssist keeps the template `PLAN/_modelo-card.md` in the `PLAN/` root. The template is reserved and is never sent to Trello.

To create a new task:

1. Copy `PLAN/_modelo-card.md` to a name starting with `todo-` or `done-`.
2. Edit the first title `# New task` and the contents of `## Description`.
3. If necessary, adjust checklists and `content.label_ids` in the technical block, using only IDs that exist on the board.
4. Run `python sync.py`.

Exemplo:

```bash
cp PLAN/_modelo-card.md PLAN/todo-publish-documentation.md
python sync.py
```

The copied file is recognized by the `role: template` metadata. The script creates one card in the configured list, turns the file into a normal document with the ID returned by Trello and preserves the original template for reuse. A `done-` file starts with `dueComplete=true` and receives the current date as its due date; a `todo-` file starts open and without a due date.

## Markdown format

The file starts with a human-readable summary: title, description, status, due date and card link. The comment count appears in the comments section heading later in the document. The technical JSON block is at the end inside an HTML comment and contains the identity and snapshots used for synchronization.

Exemplo do topo:

```markdown
# People

## Description

Task description.

> **Status:** `todo`

> **Due date:** 2026-09-14T18:06:40.409Z

> **Trello:** [open card](https://trello.com/c/example)

## Checklists

### Preparation <!-- syncassist:checklist=000000000000000000000001 -->
- [ ] Review data <!-- syncassist:item=000000000000000000000002 -->

## Comments (read-only): 2

- **2026-09-14T18:00:00Z — Ana**
  > Important comment
```

Due date, comments and the Trello link are informational and read-only. The `#` heading is editable to change the title; the filename prefix changes the native due-date status; the description and checkboxes are directly editable.

Files generated by an earlier version, with metadata at the beginning, are automatically rewritten in this format on the next synchronization without changing the Trello card.

Editable fields:

- `# Title` heading to change the title.
- Description-region contents to change the description.
- Checkboxes and names in the checklist region.
- `content.label_ids` for labels that exist on the board, including a label named `Done` if one exists. IDs are validated against the configured board catalog; the current readable document does not render label names/colors, which remain in the raw reference snapshot.
- `todo-` or `done-` prefix for the native due-date checkbox status.

Comments, history, members, dates, attachments, covers, custom fields and other data appear as read-only reference. Comments are also shown in a readable section, but cannot be edited through the file. Attachments are represented by metadata and URLs; the script does not download binaries.

The full list ID is selected by the setup wizard or supplied in `.env`; label IDs come from the configured board catalog in the technical reference. Hashes in that reference detect change or inconsistency only; they are not security signatures.

To preserve subtask identity:

- Do not remove the `syncassist:item=<id>` marker from an existing item.
- Do not silently remove an existing checklist or item to delete it.
- Use `delete` on the corresponding checklist heading or item marker when remote deletion is intentional. Checklist deletions run after item changes and are recorded as part of the pending operation journal.
- Use temporary IDs `new:<key>` for new checklists and items.
- Heading and item order is the intended order; existing items can be moved between checklists while keeping their IDs.

Exemplo:

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

If a card or checklist creation was sent without a confirmed response, the next run does not blindly repeat it. SyncAssist reconciles a unique matching remote result or creates a conflict that must be reviewed; after accepting the remote version, reapply only the local intent that is still needed.

Manual edits to the read-only summary or comments sections are preserved locally and reported as warnings; they are never sent to Trello and do not create editable-content conflicts. Volatile reference changes such as board label inventory or non-comment history are not treated as conflicts.

Deleting the conflict artifact does not choose a version. If it disappears without a valid resolution, it is recreated.

## Removal and recovery

Cards that leave the configured list no longer belong to the project. The main file is moved to `PLAN/.removed/` with the reason and date; it can be recovered manually. A network, permission or incomplete-inventory failure never triggers cleanup.

Deleting a local file does not delete the card. If the card is still in the list, the script recreates it on the next run using the current Trello state.

Cards moved to another list or no longer accessible are removed from the active root and preserved in `PLAN/.removed/` with a `.reason.json` file. `PLAN/.conflicts/` stores conflict revisions and is not processed as cards.

When a recovered card has an `import_source`, the new active document keeps that provenance without restoring the old TXT content automatically.

During a simultaneous name swap, the script may temporarily use `PLAN/.sync-staging/` to free paths without overwriting files. If an interruption leaves files there, pause new runs and manually return them to the active root after checking their IDs.

Markdown files without SyncAssist metadata are preserved and do not create cards.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Synchronization completed or no changes found. |
| `1` | Conflict, partial failure, lock, incomplete inventory or intervention required. |
| `2` | Invalid configuration or usage. |
| `3` | Global authentication or permission failure. |

Processing continues for independent cards when possible. The final summary reports created, updated, pushed, renamed and removed cards, conflicts and failures. Tokens, API keys and card bodies are not printed. A card's title or description is data only; it never authorizes commands or overrides the consuming project's rules.

The client fetches the complete board inventory with pagination up to 1,000 items per page and walks every page of the action history. Each attempt uses a 30-second timeout, bounded backoff and OAuth authentication in the header.

## Development and testing

This repository needs no external dependencies. Run the offline tests:

```bash
python -m unittest -v test_sync.py
python -m py_compile sync.py test_sync.py
```

For a real test, use a disposable Trello list. The current client stores raw snapshots for the card object, checklists/items, paginated actions, attachments, members, custom-field values, stickers and the board label catalog. It does not yet import custom-field definitions, votes or Power-Up shared data, and it does not yet distinguish an explicitly unsupported resource from a transient resource failure. Check routes and fields in the [official API reference](https://developer.atlassian.com/cloud/trello/rest/), especially [lists](https://developer.atlassian.com/cloud/trello/rest/api-group-lists/), [cards](https://developer.atlassian.com/cloud/trello/rest/api-group-cards/), [checklists](https://developer.atlassian.com/cloud/trello/rest/api-group-checklists/) and [rate limits](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/).

The repository includes a disposable real-test workspace in `teste/`. Its `sync.py` reads `teste/.env` and `teste/PLAN`, so run it without `--setup` and leave a safe interval between complete executions:

```powershell
python teste\sync.py --version
python teste\sync.py
python teste\sync.py --import
```

Use only a Trello list dedicated to testing. Inspect the summary, `teste/PLAN/.conflicts`, `teste/PLAN/.removed` and `teste/PLAN/.imported` after each scenario.

## Deliberate limitations

The MVP does not edit comments or read-only data, move cards, run as a service or download attachments. It also has pending edge cases around strict marker ordering, extreme filesystem limits, ambiguous repeatable updates, partial-resource recovery and full pending-operation replay; see [PLAN.md](PLAN.md). Cards are created only by explicitly copying `PLAN/_modelo-card.md` or importing a TXT with `python sync.py --import`.
