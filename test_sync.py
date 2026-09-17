import io
import json
import tempfile
import urllib.error
import unittest
from pathlib import Path
from unittest import mock

from sync import (
    AmbiguousOperation,
    ConfigError,
    Config,
    IncompleteInventory,
    OperationJournal,
    SCRIPT_VERSION,
    METADATA_BEGIN,
    METADATA_END,
    RemoteError,
    SCHEMA_VERSION,
    SyncAssistError,
    TEMPLATE_FILENAME,
    TrelloClient,
    build_parser,
    canonical_hash,
    build_remote_projection,
    choose_filename,
    decide_sync,
    finalize_imports,
    import_txt_tasks,
    _filename_plan,
    _assert_safe_plan_file,
    _load_local_documents,
    _new_report,
    _print_report,
    _validate_projection_shape,
    main,
    parse_document,
    parse_board_url,
    parse_env_text,
    render_document,
    run_setup,
    _section_marker,
    sync_once,
    slugify_title,
)


def projection(title="Card", description="", status="todo", labels=None, checklists=None):
    return {
        "title": title,
        "description": description,
        "status": status,
        "label_ids": list(labels or []),
        "checklists": list(checklists or []),
    }


class EnvTests(unittest.TestCase):
    def test_parses_values_without_expanding_or_losing_hashes(self):
        values = parse_env_text(
            "\ufeff# comment\n"
            "TRELLO_API_KEY=key=value\n"
            "TRELLO_TOKEN=\"token#value\"\n"
            "TRELLO_LIST_ID=list-id\n"
        )
        self.assertEqual(values["TRELLO_API_KEY"], "key=value")
        self.assertEqual(values["TRELLO_TOKEN"], "token#value")

    def test_rejects_duplicate_keys_and_unclosed_quotes(self):
        with self.assertRaises(ValueError):
            parse_env_text("A=1\nA=2\n")
        with self.assertRaises(ValueError):
            parse_env_text("A=\"unclosed\n")

    def test_config_requires_the_three_project_values(self):
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            Config.from_values({"TRELLO_API_KEY": "key"}, root)

        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        self.assertEqual(config.plan_dir, root / "PLAN")

    def test_empty_report_explicitly_says_no_changes(self):
        output = io.StringIO()
        _print_report({"created": 0, "updated": 0, "pushed": 0, "renamed": 0, "removed": 0, "unchanged": 0, "conflicts": 0, "failures": 0, "warnings": [], "errors": [], "examined": 0, "operations": 0, "deleted_items": 0, "deleted_checklists": 0, "recovery_paths": [], "cleanup_skipped": []}, output=output, errors=io.StringIO())
        self.assertIn("No changes.", output.getvalue())


class FilenameTests(unittest.TestCase):
    def test_slug_is_short_portable_and_keeps_full_title_elsewhere(self):
        slug = slugify_title('  A <very> long: title/\U0001f5bc\ufe0f ' + "x" * 200)
        self.assertLessEqual(len(slug), 60)
        self.assertNotRegex(slug, r'[<>:"/\\|?*]')
        self.assertNotIn("  ", slug)

    def test_url_only_title_uses_card_fallback(self):
        self.assertEqual(slugify_title("https://example.com/a/image.png"), "card")
        self.assertEqual(slugify_title("![image](https://example.com/a.png)"), "card")
        self.assertIn("--", choose_filename("todo", "!!!", "abcdef1234567890abcdef12"))
        self.assertIn("--", choose_filename("todo", "CON", "abcdef1234567890abcdef12"))

    def test_slug_uses_image_alt_text_and_is_utf8_bounded(self):
        slug = slugify_title("![Release notes](https://example.com/notes.png) " + "é" * 200)
        self.assertTrue(slug.startswith("release-notes"))
        self.assertLessEqual(len(slug.encode("utf-8")), 180)

    def test_slug_removes_html_and_data_urls(self):
        self.assertEqual(slugify_title("<b>Ship</b> data:image/png;base64,abc"), "ship")

    def test_filename_plan_disambiguates_unmanaged_occupancy(self):
        card_id = "abcdef1234567890abcdef12"
        bundles = {card_id: {"card": {"id": card_id, "name": "Title", "desc": "", "idLabels": []}}}
        filenames = _filename_plan(bundles, occupied_names={"todo-title.md"})
        self.assertEqual(filenames[card_id], "todo-title--cdef12.md")

    def test_filename_plan_preserves_a_stable_suffix_after_title_change(self):
        card_id = "abcdef1234567890abcdef12"
        old_projection = projection(title="Old title")
        path = Path(tempfile.mkdtemp()) / "todo-old-title--cdef12.md"
        path.write_text(
            render_document(
                {
                    "managed_by": "syncassist",
                    "schema_version": SCHEMA_VERSION,
                    "role": "card",
                    "trello_card_id": card_id,
                    "trello_board_id": "abcdef1234567890abcdef90",
                    "trello_list_id": "abcdef1234567890abcdef34",
                    "section_token": "abc123",
                    "status": "todo",
                    "filename": {"slug": "old-title", "suffix": "cdef12"},
                    "content": old_projection,
                    "reference": {},
                    "sync": {"base": old_projection, "base_hash": canonical_hash(old_projection), "reference_hash": canonical_hash({})},
                }
            ),
            encoding="utf-8",
        )
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        bundles = {card_id: {"card": {"id": card_id, "name": "New title", "desc": "", "idLabels": []}}}

        filenames = _filename_plan(bundles, {card_id: parsed})

        self.assertEqual(filenames[card_id], "todo-new-title--cdef12.md")

    def test_plan_path_length_is_checked_before_writes(self):
        with self.assertRaises(SyncAssistError):
            _assert_safe_plan_file(Path("C:/" + "a" * 270 + ".md"), Path("C:/"))

    def test_unmanaged_markdown_is_ignored_even_with_a_card_like_name(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        plan_dir.mkdir()
        plan_dir.joinpath("todo-personal.md").write_text("# Personal note\n", encoding="utf-8")
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        report = _new_report()

        documents, new_documents, scan_complete = _load_local_documents(plan_dir, config, report)

        self.assertEqual(documents, {})
        self.assertEqual(new_documents, [])
        self.assertTrue(scan_complete)
        self.assertEqual(report["failures"], 0)

    def test_projection_rejects_title_limit_and_duplicate_subtask_ids(self):
        with self.assertRaises(ValueError):
            _validate_projection_shape(projection(title="x" * 164))
        duplicate = projection(
            checklists=[
                {
                    "id": "abcdef1234567890abcdef90",
                    "name": "Checklist",
                    "items": [
                        {"id": "abcdef1234567890abcdef91", "name": "One", "state": "incomplete"},
                        {"id": "abcdef1234567890abcdef91", "name": "Two", "state": "incomplete"},
                    ],
                }
            ]
        )
        with self.assertRaises(ValueError):
            _validate_projection_shape(duplicate)

    def test_duplicate_uses_stable_id_only_when_needed(self):
        self.assertEqual(
            choose_filename("todo", "Implement API", "abcdef1234567890abcdef12"),
            "todo-implement-api.md",
        )
        self.assertEqual(
            choose_filename(
                "todo",
                "Implement API",
                "abcdef1234567890abcdef12",
                duplicate=True,
            ),
            "todo-implement-api--cdef12.md",
        )

    def test_collision_is_independent_of_todo_done_prefix(self):
        bundles = {
            "111111111111111111111111": {
                "card": {"id": "111111111111111111111111", "name": "Same title", "desc": "", "idLabels": []}
            },
            "222222222222222222222222": {
                "card": {
                    "id": "222222222222222222222222",
                    "name": "Same title",
                    "desc": "",
                    "idLabels": ["done-label"],
                    "dueComplete": True,
                }
            },
        }
        filenames = _filename_plan(bundles)
        self.assertEqual(filenames["111111111111111111111111"], "todo-same-title--111111.md")
        self.assertEqual(filenames["222222222222222222222222"], "done-same-title--222222.md")

    def test_collision_expands_the_id_suffix_when_six_characters_are_equal(self):
        bundles = {
            "111111111111111111abcdef": {
                "card": {"id": "111111111111111111abcdef", "name": "Same title", "desc": "", "idLabels": []}
            },
            "222222222222222222abcdef": {
                "card": {"id": "222222222222222222abcdef", "name": "Same title", "desc": "", "idLabels": []}
            },
        }
        filenames = _filename_plan(bundles)
        self.assertEqual(filenames["111111111111111111abcdef"], "todo-same-title--11abcdef.md")
        self.assertEqual(filenames["222222222222222222abcdef"], "todo-same-title--22abcdef.md")

    def test_filename_plan_uses_local_titles_for_a_two_card_swap(self):
        card_one = "111111111111111111111111"
        card_two = "222222222222222222222222"
        bundles = {
            card_one: {"card": {"id": card_one, "name": "Alpha", "desc": "", "idLabels": []}},
            card_two: {"card": {"id": card_two, "name": "Beta", "desc": "", "idLabels": []}},
        }

        def local_document(card_id, filename, local_title, base_title, token):
            base = projection(title=base_title)
            metadata = {
                "managed_by": "syncassist",
                "schema_version": SCHEMA_VERSION,
                "role": "card",
                "trello_card_id": card_id,
                "trello_board_id": "333333333333333333333333",
                "trello_list_id": "444444444444444444444444",
                "section_token": token,
                "content": projection(title=local_title),
                "reference": {"card": {"name": base_title}},
                "sync": {
                    "base": base,
                    "base_hash": canonical_hash(base),
                    "reference_hash": canonical_hash({"card": {"name": base_title}}),
                },
                "filename": {"slug": filename.removeprefix("todo-").removesuffix(".md"), "suffix": ""},
            }
            return parse_document(Path(filename), render_document(metadata))

        local_documents = {
            card_one: local_document(card_one, "todo-alpha.md", "Beta", "Alpha", "1111111111111111"),
            card_two: local_document(card_two, "todo-beta.md", "Alpha", "Beta", "2222222222222222"),
        }
        filenames = _filename_plan(bundles, local_documents)
        self.assertEqual(filenames[card_one], "todo-beta.md")
        self.assertEqual(filenames[card_two], "todo-alpha.md")


class DocumentTests(unittest.TestCase):
    def test_description_round_trip_preserves_trailing_newlines(self):
        for description in ("", "Task", "Task\n", "Task\n\n"):
            with self.subTest(description=repr(description)):
                metadata = {
                    "managed_by": "syncassist",
                    "schema_version": SCHEMA_VERSION,
                    "role": "card",
                    "section_token": "abc123",
                    "content": projection(description=description),
                    "reference": {},
                    "sync": {"reference_hash": canonical_hash({})},
                }
                parsed = parse_document(Path("todo-card.md"), render_document(metadata))
                self.assertEqual(parsed.projection["description"], description)

    def test_document_starts_with_human_summary_and_parses_edited_title(self):
        document = render_document(
            {
                "managed_by": "syncassist",
                "schema_version": SCHEMA_VERSION,
                "role": "card",
                "section_token": "abc123",
                "status": "done",
                "filename": {"slug": "title", "suffix": ""},
                    "content": projection(title="Full title", description="Description"),
                "reference": {
                    "card": {
                        "due": "2026-09-14T18:06:40.409Z",
                        "url": "https://trello.com/c/example",
                    },
                    "actions": [
                        {
                            "type": "commentCard",
                            "date": "2026-09-14T18:00:00Z",
                            "memberCreator": {"fullName": "Ana"},
                            "data": {"text": "Important comment"},
                        }
                    ],
                },
            }
        )

        self.assertTrue(document.startswith("# Full title\n\n"))
        self.assertIn("> **Status:** `done`", document)
        self.assertIn("> **Due date:** 2026-09-14T18:06:40.409Z", document)
        self.assertIn("## Comments (read-only): 1", document)
        self.assertIn("Important comment", document)
        self.assertIn("## Synchronization data (do not edit)", document)
        self.assertGreater(document.index("<!-- syncassist:metadata"), document.index("# Full title"))

        edited = document.replace("# Full title", "# Edited title", 1)
        parsed = parse_document(Path("todo-title.md"), edited)
        self.assertEqual(parsed.projection["title"], "Edited title")

    def test_round_trip_preserves_description_and_metadata(self):
        document = render_document(
            {
                "managed_by": "syncassist",
                "schema_version": SCHEMA_VERSION,
                "role": "card",
                "trello_card_id": "abcdef1234567890abcdef12",
                "trello_board_id": "abcdef1234567890abcdef34",
                "trello_list_id": "abcdef1234567890abcdef56",
                "trello_list_name": "Project",
                "trello_url": "https://trello.com/c/example",
                "section_token": "abc123",
                "status": "todo",
                "filename": {"slug": "card", "suffix": ""},
                "content": projection(
                    title="Full title",
                    description="linha 1\n\n```python\nprint('x')\n```\n",
                    checklists=[
                        {
                            "id": "abcdef1234567890abcdef90",
                            "name": "Checklist",
                            "items": [
                                {
                                    "id": "abcdef1234567890abcdef91",
                                    "name": "Item",
                                    "state": "incomplete",
                                }
                            ],
                        }
                    ],
                ),
                "reference": {"card": {"name": "Full title"}},
                "sync": {
                    "last_synced_at": "2026-09-14T00:00:00Z",
                    "base": projection(title="Full title"),
                    "base_hash": canonical_hash(projection(title="Full title")),
                    "reference_hash": canonical_hash({"card": {"name": "Full title"}}),
                    "pending": None,
                    "conflict": None,
                    "resolution": None,
                },
            }
        )
        parsed = parse_document(Path("todo-card.md"), document)
        self.assertEqual(parsed.projection["title"], "Full title")
        self.assertIn("```python", parsed.projection["description"])
        self.assertEqual(parsed.projection["checklists"][0]["items"][0]["name"], "Item")
        self.assertFalse(parsed.read_only_changed)

    def test_reference_edit_is_detected(self):
        metadata = {
            "managed_by": "syncassist",
            "schema_version": SCHEMA_VERSION,
            "role": "card",
            "section_token": "abc123",
            "content": projection(title="Title"),
            "reference": {"card": {"name": "Title"}},
            "sync": {
                "base": projection(title="Title"),
                "base_hash": canonical_hash(projection(title="Title")),
                "reference_hash": canonical_hash({"card": {"name": "Title"}}),
            },
        }
        document = render_document(metadata).replace('"name": "Title"', '"name": "Changed"')
        parsed = parse_document(Path("todo-card.md"), document)
        self.assertTrue(parsed.read_only_changed)

    def test_untrusted_metadata_and_section_markers_round_trip_safely(self):
        metadata = {
            "managed_by": "syncassist",
            "schema_version": SCHEMA_VERSION,
            "role": "card",
            "section_token": "abc123",
            "content": projection(
                title="<b>Title</b> & -->",
                description="<!-- syncassist:abc123:description:begin -->\ntexto",
            ),
            "reference": {"raw": "<>& -->"},
        }
        document = render_document(metadata)
        metadata_start = document.index("<!-- syncassist:metadata")
        metadata_end = document.index("syncassist:end -->", metadata_start)
        metadata_block = document[metadata_start:metadata_end]
        self.assertIn(r"\u003c", metadata_block)
        parsed = parse_document(Path("todo-card.md"), document)
        self.assertEqual(parsed.projection["title"], "<b>Title</b> & -->")
        self.assertEqual(parsed.projection["description"], metadata["content"]["description"])
        self.assertNotEqual(parsed.metadata["section_token"], "abc123")
        self.assertEqual(document.count("<!-- syncassist:abc123:description:begin -->"), 1)

    def test_current_document_requires_all_sections_in_order(self):
        metadata = {
            "managed_by": "syncassist",
            "schema_version": SCHEMA_VERSION,
            "role": "card",
            "section_token": "abc123",
            "content": projection(title="Title"),
            "reference": {},
            "sync": {"reference_hash": canonical_hash({})},
        }
        document = render_document(metadata)
        token = metadata["section_token"]
        missing_comments = document.replace(_section_marker(token, "comments", "begin") + "\n", "", 1)
        with self.assertRaises(ValueError):
            parse_document(Path("todo-title.md"), missing_comments)

    def test_summary_renders_label_names_colors_and_ids_from_reference(self):
        document = render_document(
            {
                "managed_by": "syncassist",
                "schema_version": SCHEMA_VERSION,
                "role": "card",
                "section_token": "abc123",
                "content": projection(title="Title"),
                "reference": {
                    "card": {"idLabels": ["abcdef1234567890abcdef56"]},
                    "board_labels": [
                        {"id": "abcdef1234567890abcdef56", "name": "Urgent", "color": "red"}
                    ],
                },
                "sync": {"reference_hash": canonical_hash({})},
            }
        )
        self.assertIn("Urgent [red] (abcdef1234567890abcdef56)", document)

    def test_operation_journal_persists_base_desired_and_receipt(self):
        base = projection(title="Base")
        metadata = {
            "managed_by": "syncassist",
            "schema_version": SCHEMA_VERSION,
            "role": "card",
            "section_token": "abc123",
            "content": projection(title="Local"),
            "reference": {},
            "sync": {"base": base, "base_hash": canonical_hash(base), "reference_hash": canonical_hash({})},
        }
        path = Path(tempfile.mkdtemp()) / "todo-card.md"
        path.write_text(render_document(metadata), encoding="utf-8")
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        journal = OperationJournal(path, parsed, parsed.projection, "2026-09-14T00:00:00Z")

        journal.run("update_card", {"card_id": "abcdef1234567890abcdef12", "name": "Local"}, lambda: {"id": "abcdef1234567890abcdef12"})

        pending = parse_document(path, path.read_text(encoding="utf-8")).metadata["sync"]["pending"]
        self.assertEqual(pending["base"], base)
        self.assertEqual(pending["desired"], parsed.projection)
        self.assertEqual(pending["operations"][0]["receipt"], {"id": "abcdef1234567890abcdef12"})


class DecisionTests(unittest.TestCase):
    def test_classifies_the_three_way_sync(self):
        base = projection(title="Base")
        remote = projection(title="Remoto")
        local = projection(title="Base")
        self.assertEqual(decide_sync(base, local, remote), "remote_only")
        self.assertEqual(decide_sync(base, remote, remote), "converged")
        self.assertEqual(decide_sync(base, projection(title="Local"), base), "local_only")
        self.assertEqual(
            decide_sync(base, projection(title="Local"), remote), "conflict"
        )

    def test_equal_documents_are_unchanged_even_when_the_base_is_old(self):
        base = projection(title="Base")
        same = projection(title="New")
        self.assertEqual(decide_sync(base, same, same), "converged")


class RemoteProjectionTests(unittest.TestCase):
    def test_due_complete_is_status_and_labels_are_preserved(self):
        card = {
            "id": "abcdef1234567890abcdef12",
            "idList": "abcdef1234567890abcdef34",
            "name": "Card",
            "desc": "Description",
            "idLabels": ["abcdef1234567890abcdef56", "abcdef1234567890abcdef78"],
            "dueComplete": True,
        }
        bundle = {
            "card": card,
            "checklists": [
                {
                    "id": "abcdef1234567890abcdef90",
                    "name": "Checklist",
                    "checkItems": [
                        {
                            "id": "abcdef1234567890abcdef91",
                            "name": "Item",
                            "state": "complete",
                        }
                    ],
                }
            ],
        }
        result = build_remote_projection(bundle)
        self.assertEqual(result["status"], "done")
        self.assertEqual(
            result["label_ids"], ["abcdef1234567890abcdef56", "abcdef1234567890abcdef78"]
        )
        self.assertEqual(result["checklists"][0]["id"], "abcdef1234567890abcdef90")
        self.assertEqual(result["checklists"][0]["items"][0]["state"], "complete")
        card["dueComplete"] = False
        self.assertEqual(build_remote_projection(bundle)["status"], "todo")


class ClientTests(unittest.TestCase):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def test_card_inventory_uses_the_all_filter_route(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        seen = []
        headers = []

        def opener(request, timeout):
            seen.append(request.full_url)
            headers.append(request.headers)
            return self.Response([])

        TrelloClient(config, opener=opener).get_board_cards("abcdef1234567890abcdef56")
        self.assertIn("/1/boards/abcdef1234567890abcdef56/cards/all?", seen[0])
        self.assertNotIn("token=token", seen[0])
        self.assertEqual(
            headers[0]["Authorization"],
            'OAuth oauth_consumer_key="key", oauth_token="token"',
        )

    def test_client_uses_open_method_for_an_opener_director(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )

        class OpenerDirectorLike:
            def open(self, request, timeout):
                return ClientTests.Response({"id": "abcdef1234567890abcdef56"})

        result = TrelloClient(config, opener=OpenerDirectorLike()).get_board("abcdef1234567890abcdef56")
        self.assertEqual(result["id"], "abcdef1234567890abcdef56")

    def test_card_inventory_paginates_when_the_page_is_full(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        first_page = [{"id": f"{index:024x}", "idList": config.list_id} for index in range(1000)]
        seen = []

        def opener(request, timeout):
            seen.append(request.full_url)
            return self.Response(first_page if len(seen) == 1 else [])

        cards = TrelloClient(config, opener=opener).get_board_cards("abcdef1234567890abcdef56")
        self.assertEqual(len(cards), 1000)
        self.assertEqual(len(seen), 2)
        self.assertIn("before=", seen[1])

    def test_setup_client_lists_board_lists(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.full_url, request.method, request.headers))
            return self.Response([])

        result = TrelloClient.from_credentials("key", "token", opener=opener).get_board_lists(
            "abcdef1234567890abcdef56"
        )
        self.assertEqual(result, [])
        self.assertIn("/1/boards/abcdef1234567890abcdef56/lists?", seen[0][0])
        self.assertIn("fields=id%2Cname%2Cclosed%2CidBoard%2Cpos", seen[0][0])
        self.assertEqual(seen[0][1], "GET")
        self.assertNotIn("token=token", seen[0][0])

    def test_update_card_supports_native_due_completion(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        seen = []

        def opener(request, timeout):
            seen.append((request.full_url, request.method))
            return self.Response({"id": "abcdef1234567890abcdef56"})

        result = TrelloClient(config, opener=opener).update_card(
            "abcdef1234567890abcdef56", {"dueComplete": True}
        )
        self.assertEqual(result["id"], "abcdef1234567890abcdef56")
        self.assertIn("dueComplete=true", seen[0][0])
        self.assertNotIn("key=key", seen[0][0])
        self.assertNotIn("token=token", seen[0][0])
        self.assertEqual(seen[0][1], "PUT")

    def test_update_card_can_clear_due_date(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        seen = []

        def opener(request, timeout):
            seen.append(request.full_url)
            return self.Response({"id": "abcdef1234567890abcdef56"})

        TrelloClient(config, opener=opener).update_card(
            "abcdef1234567890abcdef56", {"due": None, "dueComplete": False}
        )
        self.assertIn("due=null", seen[0])
        self.assertIn("dueComplete=false", seen[0])

    def test_rate_limit_retry_reports_wait_without_exposing_credentials(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        calls = []
        messages = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {"Retry-After": "2"},
                    io.BytesIO(),
                )
            return self.Response({"id": "abcdef1234567890abcdef56"})

        with mock.patch("sync.time.sleep") as sleep:
            result = TrelloClient(config, opener=opener, progress=messages.append).get_board(
                "abcdef1234567890abcdef56"
            )

        self.assertEqual(result["id"], "abcdef1234567890abcdef56")
        self.assertEqual(len(calls), 2)
        self.assertIn("Trello requested a 2.0s delay", messages[0])
        self.assertNotIn("key", messages[0])
        self.assertNotIn("token", messages[0])
        sleep.assert_any_call(2.0)

    def test_label_inventory_paginates_and_rejects_repeated_cursor(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        first_page = [{"id": f"{index:024x}"} for index in range(1000)]
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            return self.Response(first_page if len(calls) == 1 else [])

        labels = TrelloClient(config, opener=opener).get_board_labels("abcdef1234567890abcdef56")
        self.assertEqual(len(labels), 1000)
        self.assertEqual(len(calls), 2)
        self.assertIn("before=0000000000000000000003e7", calls[1])

        def repeating(request, timeout):
            return self.Response(first_page)

        with self.assertRaises(IncompleteInventory):
            TrelloClient(config, opener=repeating).get_board_labels("abcdef1234567890abcdef56")

    def test_action_pagination_detects_repeated_cursor(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        page = [{"id": f"{index:024x}", "date": str(index)} for index in range(1000)]

        with self.assertRaises(IncompleteInventory):
            TrelloClient(config, opener=lambda request, timeout: self.Response(page))._paged_actions(
                "abcdef1234567890abcdef56"
            )

    def test_card_bundle_rejects_an_incomplete_optional_resource(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        responses = [
            {"id": "abcdef1234567890abcdef56"},
            [],
            [],
            [],
            {},
            [],
        ]

        def opener(request, timeout):
            return self.Response(responses.pop(0))

        with self.assertRaises(IncompleteInventory):
            TrelloClient(config, opener=opener).get_card_bundle("abcdef1234567890abcdef56")

    def test_card_bundle_preserves_previous_section_after_complementary_failure(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        card_id = "abcdef1234567890abcdef56"
        previous = {"attachments": [{"id": "old-attachment"}]}

        def request(method, path, **kwargs):
            if path == f"/cards/{card_id}/attachments":
                raise RemoteError("temporary attachment failure", status=503)
            if path == f"/cards/{card_id}":
                return {"id": card_id, "idBoard": "abcdef1234567890abcdef90", "idList": config.list_id}
            if path.endswith("/checklists"):
                return []
            if path.endswith("/members") or path.endswith("/customFieldItems") or path.endswith("/stickers"):
                return []
            if path.endswith("/customFields") or path.endswith("/membersVoted") or path.endswith("/pluginData"):
                return []
            if path.endswith("/actions"):
                return []
            raise AssertionError(path)

        client = TrelloClient(config)
        client._request = request
        bundle = client.get_card_bundle(card_id, previous_reference=previous)

        self.assertEqual(bundle["attachments"], previous["attachments"])
        self.assertEqual(bundle["resource_status"]["attachments"], "failed")
        self.assertIn("attachments", bundle["resource_errors"])

    def test_card_bundle_records_unsupported_optional_resource(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        card_id = "abcdef1234567890abcdef56"

        def request(method, path, **kwargs):
            if path == f"/cards/{card_id}/customFieldItems":
                raise RemoteError("custom fields unavailable", status=403)
            if path == f"/cards/{card_id}":
                return {"id": card_id, "idBoard": "abcdef1234567890abcdef90", "idList": config.list_id}
            if path.endswith("/checklists") or path.endswith("/attachments") or path.endswith("/members"):
                return []
            if path.endswith("/stickers") or path.endswith("/actions"):
                return []
            if path.endswith("/customFields") or path.endswith("/membersVoted") or path.endswith("/pluginData"):
                return []
            raise AssertionError(path)

        client = TrelloClient(config)
        client._request = request
        bundle = client.get_card_bundle(card_id)

        self.assertEqual(bundle["custom_field_items"], [])
        self.assertEqual(bundle["resource_status"]["custom_field_items"], "unsupported")

    def test_create_card_uses_the_configured_list_without_query_credentials(self):
        root = Path(tempfile.mkdtemp())
        config = Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef12",
            },
            root,
        )
        seen = []

        def opener(request, timeout):
            seen.append((request.full_url, request.method))
            return self.Response({"id": "abcdef1234567890abcdef56"})

        result = TrelloClient(config, opener=opener).create_card(
            config.list_id,
            "New task",
            "Description",
            due="2026-09-14T00:00:00Z",
            due_complete=True,
        )
        self.assertEqual(result["id"], "abcdef1234567890abcdef56")
        self.assertIn("/1/cards?", seen[0][0])
        self.assertIn("idList=abcdef1234567890abcdef12", seen[0][0])
        self.assertIn("dueComplete=true", seen[0][0])
        self.assertNotIn("key=key", seen[0][0])
        self.assertNotIn("token=token", seen[0][0])
        self.assertEqual(seen[0][1], "POST")

class SetupApi:
    board_id = "abcdef1234567890abcdef90"
    list_id = "abcdef1234567890abcdef34"

    def __init__(self, labels=None):
        self.labels = list(labels or [])
        self.label_reads = 0

    def get_board(self, board_id):
        if board_id != "board-short":
            raise RemoteError("board not found", status=404)
        return {"id": self.board_id, "name": "Test board", "closed": False}

    def get_board_lists(self, board_id):
        return [
            {"id": "abcdef1234567890abcdef12", "idBoard": self.board_id, "name": "Archived", "closed": True, "pos": 1},
            {"id": self.list_id, "idBoard": self.board_id, "name": "Project", "closed": False, "pos": 2},
            {"id": "abcdef1234567890abcdef56", "idBoard": self.board_id, "name": "Other", "closed": False, "pos": 3},
        ]

    def get_board_labels(self, board_id):
        self.label_reads += 1
        return list(self.labels)

class SetupTests(unittest.TestCase):
    def test_parser_exposes_setup_flag(self):
        self.assertTrue(build_parser().parse_args(["--setup"]).setup)

    def test_parser_exposes_import_flag_and_rejects_combined_modes(self):
        self.assertTrue(build_parser().parse_args(["--import"]).import_tasks)
        with self.assertRaises(SystemExit) as context:
            build_parser().parse_args(["--setup", "--import"])
        self.assertEqual(context.exception.code, 2)

    def test_parser_help_documents_cli_operations_and_contract(self):
        help_text = build_parser().format_help()
        for expected in (
            "python sync.py --setup",
            "python sync.py --import",
            "python sync.py --version",
            "Existing values continue by",
            "Answer no to restart",
            "No positional arguments are accepted",
            "PLAN/.conflicts/",
            "Exit codes:",
        ):
            self.assertIn(expected, help_text)

    def test_product_version_matches_release(self):
        self.assertEqual(SCRIPT_VERSION, "1.2.0")

    def test_main_runs_sync_after_successful_setup(self):
        config = object()
        report = {"failures": 0, "conflicts": 0}
        with mock.patch("sync.run_setup", return_value=0) as setup, \
                mock.patch("sync.Config.from_file", return_value=config) as load_config, \
                mock.patch("sync.sync_once", return_value=report) as sync_call, \
                mock.patch("sync._print_report") as print_report:
            self.assertEqual(main(["--setup"]), 0)

        setup.assert_called_once()
        load_config.assert_called_once()
        sync_call.assert_called_once()
        self.assertIs(sync_call.call_args.args[0], config)
        self.assertIsNotNone(sync_call.call_args.kwargs["progress"])
        print_report.assert_called_once_with(report)

    def test_main_starts_setup_automatically_when_env_is_missing(self):
        config = object()
        report = {"failures": 0, "conflicts": 0}
        with mock.patch("sync.Path.is_file", return_value=False), \
                mock.patch("sync.run_setup", return_value=0) as setup, \
                mock.patch("sync.Config.from_file", return_value=config) as load_config, \
                mock.patch("sync.sync_once", return_value=report) as sync_call, \
                mock.patch("sync._print_report"):
            self.assertEqual(main([]), 0)

        setup.assert_called_once()
        load_config.assert_called_once()
        sync_call.assert_called_once()

    def test_main_does_not_sync_when_setup_is_cancelled(self):
        with mock.patch("sync.run_setup", return_value=1) as setup, \
                mock.patch("sync.Config.from_file") as load_config, \
                mock.patch("sync.sync_once") as sync_call:
            self.assertEqual(main(["--setup"]), 1)

        setup.assert_called_once()
        load_config.assert_not_called()
        sync_call.assert_not_called()

    def test_main_imports_before_running_one_normal_sync(self):
        config = object()
        import_result = mock.Mock(errors=[], failed=0)
        report = {"failures": 0, "conflicts": 0}
        with mock.patch("sync.Path.is_file", return_value=True), \
                mock.patch("sync.Config.from_file", return_value=config), \
                mock.patch("sync.import_txt_tasks", return_value=import_result) as import_tasks, \
                mock.patch("sync.sync_once", return_value=report) as sync_call, \
                mock.patch("sync.finalize_imports") as finalize, \
                mock.patch("sync._print_import_report") as print_import, \
                mock.patch("sync._print_report") as print_report:
            self.assertEqual(main(["--import"]), 0)

        import_tasks.assert_called_once_with(config)
        sync_call.assert_called_once()
        self.assertIs(sync_call.call_args.args[0], config)
        self.assertIsNotNone(sync_call.call_args.kwargs["progress"])
        finalize.assert_called_once_with(config, import_result)
        print_import.assert_called_once_with(import_result)
        print_report.assert_called_once_with(report)

    def test_main_without_flags_keeps_the_normal_sync_path(self):
        config = object()
        report = {"failures": 0, "conflicts": 0}
        with mock.patch("sync.Path.is_file", return_value=True), \
                mock.patch("sync.run_setup") as setup, \
                mock.patch("sync.Config.from_file", return_value=config), \
                mock.patch("sync.import_txt_tasks") as import_tasks, \
                mock.patch("sync.sync_once", return_value=report) as sync_call, \
                mock.patch("sync._print_report") as print_report:
            self.assertEqual(main([]), 0)

        import_tasks.assert_not_called()
        setup.assert_not_called()
        sync_call.assert_called_once()
        self.assertIs(sync_call.call_args.args[0], config)
        self.assertIsNotNone(sync_call.call_args.kwargs["progress"])
        print_report.assert_called_once_with(report)


    def test_board_url_accepts_trello_board_and_rejects_other_routes(self):
        self.assertEqual(parse_board_url("https://trello.com/b/board-short/quad?x=1#fragment"), "board-short")
        self.assertEqual(parse_board_url("https://www.trello.com/b/board-short"), "board-short")
        for value in (
            "http://trello.com/b/board-short",
            "https://trello.com/c/card-short/card",
            "https://example.com/b/board-short",
            "https://trello.com/b/",
            "not a url",
        ):
            with self.assertRaises(ValueError):
                parse_board_url(value)

    def test_setup_uses_visible_token_input_by_default(self):
        root = Path(tempfile.mkdtemp())
        api = SetupApi(labels=[{"id": "abcdef1234567890abcdef56", "idBoard": SetupApi.board_id, "name": "Done"}])
        values = iter(["api-key", "visible-token", "https://trello.com/b/board-short", "1"])
        prompts = []
        output = io.StringIO()

        def visible_input(prompt):
            prompts.append(prompt)
            return next(values)

        result = run_setup(
            root,
            input_fn=visible_input,
            output=output,
            client_factory=lambda api_key, token: api,
        )
        self.assertEqual(result, 0)
        self.assertTrue(any("Paste the User Token:" in prompt for prompt in prompts))
        self.assertIn("TRELLO_TOKEN=visible-token", (root / ".env").read_text(encoding="utf-8"))

    def setup_inputs(self, root, api, visible, secret):
        visible_values = iter(visible)
        secret_values = iter(secret)
        output = io.StringIO()
        result = run_setup(
            root,
            input_fn=lambda prompt: next(visible_values),
            secret_input_fn=lambda prompt: next(secret_values),
            output=output,
            client_factory=lambda api_key, token: api,
        )
        return result, output.getvalue()

    def test_setup_writes_env_without_done_label_configuration(self):
        root = Path(tempfile.mkdtemp())
        api = SetupApi(labels=[{"id": "abcdef1234567890abcdef56", "idBoard": SetupApi.board_id, "name": " done ", "color": "green"}])
        result, output = self.setup_inputs(
            root,
            api,
            ["api-key", "https://trello.com/b/board-short/quad", "2"],
            ["secret-token"],
        )
        self.assertEqual(result, 0)
        env_text = (root / ".env").read_text(encoding="utf-8")
        self.assertIn("TRELLO_API_KEY=api-key", env_text)
        self.assertIn("TRELLO_TOKEN=secret-token", env_text)
        self.assertIn("TRELLO_LIST_ID=abcdef1234567890abcdef56", env_text)
        self.assertNotIn("TRELLO_DONE_LABEL_ID", env_text)
        self.assertIn("scope=read%2Cwrite", output)
        self.assertIn("expiration=never", output)
        self.assertIn("visible", output)
        self.assertNotIn("secret-token", output)
        self.assertEqual(api.label_reads, 0)
        self.assertEqual(
            (root / ".gitignore").read_text(encoding="utf-8").splitlines(),
            [".env", "PLAN/", "sync.py"],
        )

    def test_setup_preserves_gitignore_and_adds_missing_entries_once(self):
        root = Path(tempfile.mkdtemp())
        (root / ".env").write_text(
            "TRELLO_API_KEY=api-key\n"
            "TRELLO_TOKEN=secret-token\n"
            "TRELLO_LIST_ID=abcdef1234567890abcdef34\n",
            encoding="utf-8",
        )
        (root / ".gitignore").write_text("# Existing rules\ncustom/\n.env", encoding="utf-8")

        result = run_setup(
            root,
            input_fn=lambda prompt: "",
            output=io.StringIO(),
            client_factory=lambda api_key, token: self.fail("saved list should skip remote setup calls"),
        )

        self.assertEqual(result, 0)
        lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["# Existing rules", "custom/", ".env", "PLAN/", "sync.py"])

    def test_setup_does_not_create_done_label_when_missing(self):
        root = Path(tempfile.mkdtemp())
        api = SetupApi()
        result, _ = self.setup_inputs(
            root,
            api,
            ["api-key", "https://trello.com/b/board-short", "1"],
            ["secret-token"],
        )
        self.assertEqual(result, 0)
        self.assertEqual(api.label_reads, 0)
        self.assertNotIn("TRELLO_DONE_LABEL_ID", (root / ".env").read_text(encoding="utf-8"))

    def test_setup_retries_invalid_list_selection(self):
        root = Path(tempfile.mkdtemp())
        api = SetupApi(labels=[{"id": "abcdef1234567890abcdef56", "idBoard": SetupApi.board_id, "name": "Done"}])
        result, output = self.setup_inputs(
            root,
            api,
            ["api-key", "https://trello.com/b/board-short", "invalid", "2"],
            ["secret-token"],
        )
        self.assertEqual(result, 0)
        self.assertIn("Choose a number", output)
        self.assertIn("TRELLO_LIST_ID=abcdef1234567890abcdef56", (root / ".env").read_text(encoding="utf-8"))

    def test_setup_does_not_select_between_duplicate_done_labels(self):
        root = Path(tempfile.mkdtemp())
        api = SetupApi(
            labels=[
                {"id": "abcdef1234567890abcdef56", "idBoard": SetupApi.board_id, "name": "Done", "color": "green"},
                {"id": "abcdef1234567890abcdef78", "idBoard": SetupApi.board_id, "name": "DONE", "color": "blue"},
            ]
        )
        result, _ = self.setup_inputs(
            root,
            api,
            ["api-key", "https://trello.com/b/board-short", "1"],
            ["secret-token"],
        )
        self.assertEqual(result, 0)
        self.assertEqual(api.label_reads, 0)
        self.assertNotIn("TRELLO_DONE_LABEL_ID", (root / ".env").read_text(encoding="utf-8"))

    def test_setup_continues_complete_env_by_default_without_reprompting(self):
        root = Path(tempfile.mkdtemp())
        original = (
            "# Keep this file private.\n"
            "OTHER_SETTING=keep-me\n"
            "TRELLO_API_KEY=api-key\n"
            "TRELLO_TOKEN=token\n"
            "TRELLO_LIST_ID=abcdef1234567890abcdef34\n"
        )
        (root / ".env").write_text(original, encoding="utf-8")
        output = io.StringIO()
        prompts = []

        def visible_input(prompt):
            prompts.append(prompt)
            return ""

        result = run_setup(
            root,
            input_fn=visible_input,
            secret_input_fn=lambda prompt: self.fail("saved token should be reused"),
            output=output,
            client_factory=lambda api_key, token: self.fail("saved list should skip remote setup calls"),
        )
        self.assertEqual(result, 0)
        self.assertEqual(prompts, ["Continue with saved values or start from scratch? [Y/n]: "])
        self.assertEqual((root / ".env").read_text(encoding="utf-8"), original)
        self.assertIn("Reusing the saved API Key.", output.getvalue())
        self.assertIn("Reusing the saved User Token.", output.getvalue())
        self.assertIn("board URL and list selection are skipped", output.getvalue())

    def test_setup_continues_partial_env_and_only_prompts_for_missing_list(self):
        root = Path(tempfile.mkdtemp())
        (root / ".env").write_text(
            "# Keep this comment.\n"
            "OTHER_SETTING=keep-me\n"
            "TRELLO_API_KEY=saved-api\n"
            "TRELLO_TOKEN=saved-token\n",
            encoding="utf-8",
        )
        api = SetupApi()
        values = iter(["", "https://trello.com/b/board-short", "2"])
        prompts = []
        output = io.StringIO()

        def visible_input(prompt):
            prompts.append(prompt)
            return next(values)

        result = run_setup(
            root,
            input_fn=visible_input,
            secret_input_fn=lambda prompt: self.fail("saved token should be reused"),
            output=output,
            client_factory=lambda api_key, token: (
                api if (api_key, token) == ("saved-api", "saved-token")
                else self.fail("saved credentials should be reused")
            ),
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            prompts,
            [
                "Continue with saved values or start from scratch? [Y/n]: ",
                "Paste the Trello board URL: ",
                "Choose the project list: ",
            ],
        )
        env = parse_env_text((root / ".env").read_text(encoding="utf-8"))
        self.assertEqual(env["TRELLO_API_KEY"], "saved-api")
        self.assertEqual(env["TRELLO_TOKEN"], "saved-token")
        self.assertEqual(env["TRELLO_LIST_ID"], "abcdef1234567890abcdef56")
        self.assertEqual(env["OTHER_SETTING"], "keep-me")

    def test_setup_continues_saved_list_and_only_prompts_for_missing_token(self):
        root = Path(tempfile.mkdtemp())
        (root / ".env").write_text(
            "TRELLO_API_KEY=saved-api\n"
            "TRELLO_LIST_ID=abcdef1234567890abcdef34\n"
            "OTHER_SETTING=keep-me\n",
            encoding="utf-8",
        )
        prompts = []
        secret_prompts = []
        output = io.StringIO()

        def visible_input(prompt):
            prompts.append(prompt)
            return ""

        result = run_setup(
            root,
            input_fn=visible_input,
            secret_input_fn=lambda prompt: (secret_prompts.append(prompt) or "new-token"),
            output=output,
            client_factory=lambda api_key, token: self.fail("saved list should skip board lookup"),
        )
        self.assertEqual(result, 0)
        self.assertEqual(prompts, ["Continue with saved values or start from scratch? [Y/n]: "])
        self.assertEqual(secret_prompts, ["Paste the User Token: "])
        env = parse_env_text((root / ".env").read_text(encoding="utf-8"))
        self.assertEqual(env["TRELLO_API_KEY"], "saved-api")
        self.assertEqual(env["TRELLO_TOKEN"], "new-token")
        self.assertEqual(env["TRELLO_LIST_ID"], "abcdef1234567890abcdef34")
        self.assertEqual(env["OTHER_SETTING"], "keep-me")

    def test_setup_restarts_saved_values_when_user_says_no(self):
        root = Path(tempfile.mkdtemp())
        (root / ".env").write_text(
            "OTHER_SETTING=keep-me\n"
            "TRELLO_API_KEY=old-api\n"
            "TRELLO_TOKEN=old-token\n"
            "TRELLO_LIST_ID=abcdef1234567890abcdef78\n",
            encoding="utf-8",
        )
        api = SetupApi()
        result, output = self.setup_inputs(
            root,
            api,
            ["n", "new-api", "https://trello.com/b/board-short", "1"],
            ["new-token"],
        )
        self.assertEqual(result, 0)
        env = parse_env_text((root / ".env").read_text(encoding="utf-8"))
        self.assertEqual(env["TRELLO_API_KEY"], "new-api")
        self.assertEqual(env["TRELLO_TOKEN"], "new-token")
        self.assertEqual(env["TRELLO_LIST_ID"], SetupApi.list_id)
        self.assertEqual(env["OTHER_SETTING"], "keep-me")
        self.assertIn("Starting setup from scratch.", output)
        self.assertNotIn("Reusing the saved API Key.", output)

    def test_setup_reasks_for_invalid_saved_api_key_and_list_id(self):
        root = Path(tempfile.mkdtemp())
        (root / ".env").write_text(
            "TRELLO_API_KEY=invalid,api\n"
            "TRELLO_TOKEN=saved-token\n"
            "TRELLO_LIST_ID=not-a-trello-id\n",
            encoding="utf-8",
        )
        prompts = []
        values = iter(["", "new-api", "https://trello.com/b/board-short", "1"])
        output = io.StringIO()
        api = SetupApi()

        def visible_input(prompt):
            prompts.append(prompt)
            return next(values)

        result = run_setup(
            root,
            input_fn=visible_input,
            secret_input_fn=lambda prompt: self.fail("valid saved token should be reused"),
            output=output,
            client_factory=lambda api_key, token: (
                api if (api_key, token) == ("new-api", "saved-token")
                else self.fail("new API key and saved token should be used")
            ),
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            prompts,
            [
                "Continue with saved values or start from scratch? [Y/n]: ",
                "Paste the API Key: ",
                "Paste the Trello board URL: ",
                "Choose the project list: ",
            ],
        )
        self.assertIn("The saved API Key is invalid; enter it again.", output.getvalue())
        self.assertIn("The saved Trello list ID is invalid; select a list again.", output.getvalue())
        env = parse_env_text((root / ".env").read_text(encoding="utf-8"))
        self.assertEqual(env["TRELLO_API_KEY"], "new-api")
        self.assertEqual(env["TRELLO_TOKEN"], "saved-token")
        self.assertEqual(env["TRELLO_LIST_ID"], SetupApi.list_id)

    def test_setup_does_not_write_env_when_board_authentication_fails(self):
        root = Path(tempfile.mkdtemp())

        class UnauthorizedApi:
            def get_board(self, board_id):
                raise RemoteError("unauthorized", status=401)

        with self.assertRaises(RemoteError) as context:
            self.setup_inputs(
                root,
                UnauthorizedApi(),
                ["api-key", "https://trello.com/b/board-short"],
                ["secret-token"],
            )
        self.assertEqual(context.exception.status, 401)
        self.assertFalse((root / ".env").exists())


class FakeApi:
    def __init__(self, bundle):
        self.list_id = "abcdef1234567890abcdef34"
        self.board_id = "abcdef1234567890abcdef90"
        self.labels = [{"id": "abcdef1234567890abcdef56", "name": "done", "color": "green"}]
        self.bundle = bundle
        self.cards = [bundle["card"]]
        self.updated = []
        self.label_changes = []
        self.checkitem_updates = []
        self.bundle_reads = 0

    def get_list(self, list_id):
        return {"id": self.list_id, "idBoard": self.board_id, "name": "Project", "closed": False}

    def get_board(self, board_id):
        return {"id": self.board_id, "name": "Board", "closed": False}

    def get_board_labels(self, board_id):
        return self.labels

    def get_board_cards(self, board_id):
        return list(self.cards)

    def get_card_bundle(self, card_id):
        self.bundle_reads += 1
        if self.bundle["card"]["id"] != card_id:
            raise KeyError(card_id)
        return self.bundle

    def get_card(self, card_id):
        return self.bundle["card"]

    def create_card(self, list_id, name, description="", *, due=None, due_complete=False):
        card = {
            "id": "1234567890abcdef12345678",
            "idBoard": self.board_id,
            "idList": list_id,
            "name": name,
            "desc": description,
            "idLabels": [],
            "due": due,
            "dueComplete": due_complete,
            "url": "https://trello.com/c/new-card",
        }
        self.bundle = {
            "card": card,
            "checklists": [],
            "actions": [],
            "attachments": [],
            "members": [],
            "custom_field_items": [],
            "stickers": [],
        }
        self.cards = [card]
        return card

    def update_card(self, card_id, fields):
        self.updated.append((card_id, fields))
        self.bundle["card"].update(fields)
        return self.bundle["card"]

    def add_label(self, card_id, label_id):
        self.label_changes.append(("add", card_id, label_id))
        self.bundle["card"].setdefault("idLabels", []).append(label_id)

    def remove_label(self, card_id, label_id):
        self.label_changes.append(("remove", card_id, label_id))
        self.bundle["card"]["idLabels"] = [
            value for value in self.bundle["card"].get("idLabels", []) if value != label_id
        ]

    def create_checklist(self, card_id, name, pos=None):
        checklist_id = f"{len(self.bundle.get('checklists', [])) + 1:024x}"
        checklist = {"id": checklist_id, "name": name, "checkItems": []}
        self.bundle.setdefault("checklists", []).append(checklist)
        return checklist

    def update_checklist(self, checklist_id, fields):
        checklist = next(item for item in self.bundle["checklists"] if item["id"] == checklist_id)
        checklist.update(fields)
        return checklist

    def delete_checklist(self, checklist_id):
        self.bundle["checklists"] = [
            item for item in self.bundle["checklists"] if item["id"] != checklist_id
        ]

    def create_checkitem(self, checklist_id, name, pos=None):
        checklist = next(item for item in self.bundle["checklists"] if item["id"] == checklist_id)
        item_id = f"{len(checklist.get('checkItems', [])) + 1:024x}"
        item = {"id": item_id, "name": name, "state": "incomplete"}
        checklist.setdefault("checkItems", []).append(item)
        return item

    def update_checkitem(self, card_id, item_id, fields):
        self.checkitem_updates.append((card_id, item_id, dict(fields)))
        for checklist in list(self.bundle["checklists"]):
            for item in checklist.get("checkItems", []):
                if item["id"] == item_id:
                    target_checklist_id = fields.get("idChecklist")
                    if target_checklist_id and target_checklist_id != checklist["id"]:
                        checklist["checkItems"].remove(item)
                        target = next(
                            value for value in self.bundle["checklists"] if value["id"] == target_checklist_id
                        )
                        target.setdefault("checkItems", []).append(item)
                    item.update(fields)
                    return item
        raise KeyError(item_id)

    def delete_checkitem(self, checklist_id, item_id):
        checklist = next(item for item in self.bundle["checklists"] if item["id"] == checklist_id)
        checklist["checkItems"] = [
            item for item in checklist.get("checkItems", []) if item["id"] != item_id
        ]


class ImportApi:
    list_id = "abcdef1234567890abcdef34"
    board_id = "abcdef1234567890abcdef90"

    def __init__(self):
        self.cards = []
        self.bundles = {}
        self.created = []

    def get_list(self, list_id):
        return {"id": self.list_id, "idBoard": self.board_id, "name": "Project", "closed": False}

    def get_board(self, board_id):
        return {"id": self.board_id, "name": "Board", "closed": False}

    def get_board_labels(self, board_id):
        return []

    def get_board_cards(self, board_id):
        return list(self.cards)

    def get_card_bundle(self, card_id):
        return self.bundles[card_id]

    def create_card(self, list_id, name, description="", *, due=None, due_complete=False):
        card_id = f"{len(self.cards) + 1:024x}"
        card = {
            "id": card_id,
            "idBoard": self.board_id,
            "idList": list_id,
            "name": name,
            "desc": description,
            "idLabels": [],
            "due": due,
            "dueComplete": due_complete,
            "url": f"https://trello.com/c/{card_id[:8]}",
        }
        bundle = {
            "card": card,
            "checklists": [],
            "actions": [],
            "attachments": [],
            "members": [],
            "custom_field_items": [],
            "stickers": [],
        }
        self.cards.append(card)
        self.bundles[card_id] = bundle
        self.created.append((name, description))
        return card


class ImportTests(unittest.TestCase):
    def make_config(self, root):
        return Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": ImportApi.list_id,
            },
            root,
        )

    def test_import_uses_normalized_60_character_title_and_full_description(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        plan_dir.mkdir()
        source_text = "  First   line\r\nsecond line with more than sixty characters " + "x" * 50
        (plan_dir / "source-task.txt").write_bytes(source_text.encode("utf-8"))

        result = import_txt_tasks(self.make_config(root))

        self.assertEqual(result.prepared, 1)
        path = plan_dir / "todo-source-task.md"
        self.assertTrue(path.exists())
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        expected_title = "First line second line with more than sixty characters " + "x" * 50
        self.assertEqual(parsed.projection["title"], expected_title[:60])
        self.assertEqual(parsed.projection["description"], source_text.replace("\r\n", "\n"))
        self.assertLessEqual(len(parsed.projection["title"]), 60)
        self.assertEqual(parsed.metadata["role"], "template")
        self.assertEqual(parsed.metadata["import_source"]["relative_path"], "source-task.txt")

    def test_import_skips_empty_invalid_and_nested_sources(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        (plan_dir / "nested").mkdir(parents=True)
        (plan_dir / "empty.txt").write_text(" \n\t", encoding="utf-8")
        (plan_dir / "invalid.txt").write_bytes(b"\xff\xfe")
        (plan_dir / "nested" / "nested.txt").write_text("Nested", encoding="utf-8")

        result = import_txt_tasks(self.make_config(root))

        self.assertEqual(result.prepared, 0)
        self.assertEqual(result.skipped, 2)
        self.assertTrue((plan_dir / "empty.txt").exists())
        self.assertTrue((plan_dir / "invalid.txt").exists())
        self.assertFalse((plan_dir / "todo-nested.md").exists())
        self.assertEqual(len(result.errors), 2)

    def test_import_is_idempotent_and_uses_hash_suffix_for_unmanaged_collision(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        plan_dir.mkdir()
        source = plan_dir / "same.txt"
        source.write_text("Imported task", encoding="utf-8")
        (plan_dir / "todo-same.md").write_text("human file", encoding="utf-8")

        first = import_txt_tasks(self.make_config(root))
        second = import_txt_tasks(self.make_config(root))

        self.assertEqual(first.prepared, 1)
        self.assertEqual(second.prepared, 0)
        self.assertEqual(second.skipped, 1)
        imported_files = sorted(plan_dir.glob("todo-same*.md"))
        self.assertEqual(len(imported_files), 2)
        self.assertTrue(any("-import-" in path.name for path in imported_files))

    def test_import_syncs_cards_and_moves_only_confirmed_sources(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        plan_dir.mkdir()
        (plan_dir / "alpha.txt").write_text("Alpha task", encoding="utf-8")
        (plan_dir / "beta.txt").write_text("Beta task", encoding="utf-8")
        config = self.make_config(root)
        api = ImportApi()

        result = import_txt_tasks(config)
        report = sync_once(config, api, now="2026-09-14T00:00:00Z")
        finalize_imports(config, result)

        self.assertEqual(report["created"], 2)
        self.assertEqual(len(api.created), 2)
        self.assertEqual(result.imported, 2)
        self.assertEqual(sorted(path.name for path in (plan_dir / ".imported").glob("*.txt")), ["alpha.txt", "beta.txt"])
        self.assertFalse((plan_dir / "alpha.txt").exists())
        self.assertFalse((plan_dir / "beta.txt").exists())
        card_files = plan_card_files(root)
        self.assertEqual(len(card_files), 2)
        self.assertTrue(all(parse_document(path, path.read_text(encoding="utf-8")).metadata["role"] == "card" for path in card_files))

    def test_import_leaves_source_when_card_is_not_confirmed(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        plan_dir.mkdir()
        source = plan_dir / "task.txt"
        source.write_text("Task", encoding="utf-8")
        result = import_txt_tasks(self.make_config(root))

        finalize_imports(self.make_config(root), result)

        self.assertTrue(source.exists())
        self.assertEqual(result.imported, 0)
        self.assertEqual(result.failed, 1)
        self.assertFalse((plan_dir / ".imported").exists())

    def test_import_does_not_move_source_changed_after_preparation(self):
        root = Path(tempfile.mkdtemp())
        plan_dir = root / "PLAN"
        plan_dir.mkdir()
        source = plan_dir / "task.txt"
        source.write_text("Task", encoding="utf-8")
        result = import_txt_tasks(self.make_config(root))
        source.write_text("Changed task", encoding="utf-8")

        finalize_imports(self.make_config(root), result)

        self.assertTrue(source.exists())
        self.assertEqual(result.imported, 0)
        self.assertEqual(result.failed, 1)


def sample_bundle(description="Description"):
    return {
        "card": {
            "id": "abcdef1234567890abcdef12",
            "idBoard": "abcdef1234567890abcdef90",
            "idList": "abcdef1234567890abcdef34",
            "name": "Card",
            "desc": description,
            "idLabels": [],
            "due": None,
            "dueComplete": False,
            "url": "https://trello.com/c/example",
        },
        "checklists": [],
        "actions": [],
        "attachments": [],
        "members": [],
    }


def plan_card_files(root):
    return [
        path
        for path in (root / "PLAN").glob("*.md")
        if path.name.casefold() != TEMPLATE_FILENAME.casefold()
    ]


def next_plan_card(root):
    return plan_card_files(root)[0]


class SyncOnceTests(unittest.TestCase):
    def make_config(self, root):
        return Config.from_values(
            {
                "TRELLO_API_KEY": "key",
                "TRELLO_TOKEN": "token",
                "TRELLO_LIST_ID": "abcdef1234567890abcdef34",
            },
            root,
        )

    def test_imports_a_card_into_plan(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        report = sync_once(config, api, now="2026-09-14T00:00:00Z")
        files = plan_card_files(root)
        self.assertEqual(len(files), 1)
        parsed = parse_document(files[0], files[0].read_text(encoding="utf-8"))
        self.assertEqual(parsed.metadata["trello_card_id"], api.bundle["card"]["id"])
        self.assertEqual(parsed.reference["list"]["id"], config.list_id)
        self.assertEqual(parsed.reference["board"]["id"], api.board_id)
        self.assertNotIn("trello_done_label_id", parsed.metadata)
        self.assertEqual(report["created"], 1)

    def test_remote_bundle_identity_mismatch_is_not_written(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        mismatched = json.loads(json.dumps(api.bundle))
        mismatched["card"]["id"] = "1234567890abcdef12345678"
        api.get_card_bundle = lambda card_id: mismatched

        report = sync_once(config, api, now="2026-09-14T00:00:00Z")

        self.assertEqual(report["failures"], 1)
        self.assertEqual(plan_card_files(root), [])

    def test_import_records_the_bound_list_name(self):
        root = Path(tempfile.mkdtemp())
        api = FakeApi(sample_bundle())
        sync_once(self.make_config(root), api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.metadata["trello_list_name"], "Project")

    def test_sync_keeps_template_and_creates_card_from_its_copy(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        api.cards = []
        sync_once(config, api, now="2026-09-14T00:00:00Z")

        template = root / "PLAN" / TEMPLATE_FILENAME
        self.assertTrue(template.exists())
        template_text = template.read_text(encoding="utf-8")
        new_path = root / "PLAN" / "todo-people.md"
        new_path.write_text(
            template_text.replace("# New task", "# People", 1).replace(
                "## Description\n", "## Description\nTask description.\n", 1
            ),
            encoding="utf-8",
        )

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["created"], 1)
        self.assertEqual(api.bundle["card"]["name"], "People")
        self.assertEqual(api.bundle["card"]["desc"], "Task description.\n")
        self.assertEqual(api.bundle["card"]["idList"], config.list_id)
        self.assertTrue(template.exists())
        self.assertTrue(new_path.exists())
        parsed = parse_document(new_path, new_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.metadata["role"], "card")
        self.assertEqual(parsed.metadata["trello_card_id"], api.bundle["card"]["id"])

    def test_sync_rewrites_legacy_metadata_first_document(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        legacy_metadata = dict(parsed.metadata)
        reference = legacy_metadata.pop("reference")
        token = legacy_metadata["section_token"]
        legacy = "\n".join(
            [
                METADATA_BEGIN,
                json.dumps(legacy_metadata, ensure_ascii=False, indent=2, sort_keys=True),
                METADATA_END,
                "",
                "# Card",
                "",
                _section_marker(token, "description", "begin"),
                "## Description",
                "Description",
                _section_marker(token, "description", "end"),
                "",
                _section_marker(token, "checklists", "begin"),
                "## Checklists",
                "",
                _section_marker(token, "checklists", "end"),
                "",
                _section_marker(token, "reference", "begin"),
                "## Trello reference (read-only)",
                "```json",
                json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                _section_marker(token, "reference", "end"),
                "",
            ]
        )
        path.write_text(legacy, encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        rewritten = path.read_text(encoding="utf-8")
        self.assertTrue(rewritten.startswith("# Card\n\n"))
        self.assertIn("## Synchronization data (do not edit)", rewritten)
        self.assertGreater(rewritten.index(METADATA_BEGIN), rewritten.index("# Card"))
        self.assertEqual(report["updated"], 1)

    def test_archived_list_is_a_configuration_error_before_card_processing(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        api.get_list = lambda list_id: {
            "id": api.list_id,
            "idBoard": api.board_id,
            "name": "Project",
            "closed": True,
        }
        with self.assertRaises(ConfigError):
            sync_once(config, api, now="2026-09-14T00:00:00Z")
        self.assertFalse((root / "PLAN" / "todo-card.md").exists())

    def test_archived_card_is_not_imported_from_inventory(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        api.bundle["card"]["closed"] = True

        report = sync_once(config, api, now="2026-09-14T00:00:00Z")

        self.assertEqual(report["examined"], 0)
        self.assertEqual(api.bundle_reads, 0)
        self.assertFalse(plan_card_files(root))

    def test_archived_card_fetched_after_inventory_is_not_imported(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        api.cards = [dict(api.bundle["card"])]
        api.bundle["card"]["closed"] = True

        sync_once(config, api, now="2026-09-14T00:00:00Z")

        self.assertEqual(api.bundle_reads, 1)
        self.assertFalse(plan_card_files(root))

    def test_archive_detected_before_local_push_removes_file_without_remote_update(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["description"] = "Local change"
        path.write_text(render_document(metadata), encoding="utf-8")
        original_get_bundle = api.get_card_bundle
        refresh_reads = 0

        def archive_on_refresh(card_id):
            nonlocal refresh_reads
            refresh_reads += 1
            bundle = original_get_bundle(card_id)
            if refresh_reads == 2:
                bundle["card"]["closed"] = True
            return bundle

        api.get_card_bundle = archive_on_refresh

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertEqual(report["removed"], 1)
        self.assertFalse(plan_card_files(root))
        self.assertTrue(api.bundle["card"]["closed"])
        self.assertFalse(api.updated)

    def test_archiving_removes_card_until_unarchived_with_current_data(self):
        for initial_status in ("todo", "done"):
            with self.subTest(initial_status=initial_status):
                root = Path(tempfile.mkdtemp())
                config = self.make_config(root)
                api = FakeApi(sample_bundle())
                api.bundle["card"]["dueComplete"] = initial_status == "done"
                sync_once(config, api, now="2026-09-14T00:00:00Z")
                original_path = next_plan_card(root)
                self.assertTrue(original_path.name.startswith(f"{initial_status}-"))

                api.bundle["card"]["closed"] = True
                archived_report = sync_once(config, api, now="2026-09-14T00:01:00Z")

                self.assertEqual(archived_report["removed"], 1)
                self.assertFalse(plan_card_files(root))
                recovered = list((root / "PLAN" / ".removed").glob("*.md"))
                self.assertEqual(len(recovered), 1)
                self.assertEqual(
                    json.loads(recovered[0].with_suffix(".reason.json").read_text(encoding="utf-8"))["reason"],
                    "card_archived",
                )
                self.assertTrue(api.bundle["card"]["closed"])

                repeated_report = sync_once(config, api, now="2026-09-14T00:02:00Z")
                self.assertEqual(repeated_report["removed"], 0)
                self.assertFalse(plan_card_files(root))

                restored_status = "done" if initial_status == "todo" else "todo"
                api.bundle["card"].update(
                    {
                        "closed": False,
                        "name": f"Returned {restored_status}",
                        "desc": "Latest source data",
                        "dueComplete": restored_status == "done",
                    }
                )
                restored_report = sync_once(config, api, now="2026-09-14T00:03:00Z")

                restored_path = next_plan_card(root)
                self.assertEqual(restored_report["created"], 1)
                self.assertEqual(restored_path.name, f"{restored_status}-returned-{restored_status}.md")
                restored = parse_document(restored_path, restored_path.read_text(encoding="utf-8"))
                self.assertEqual(restored.projection["description"], "Latest source data")
                self.assertFalse(api.bundle["card"]["closed"])
                self.assertFalse(api.updated)

    def test_pushes_local_edit_and_status_without_moving_card(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["title"] = "New title"
        metadata["content"]["description"] = "Local description"
        path.write_text(render_document(metadata), encoding="utf-8")
        path.rename(path.with_name("done-new-title.md"))

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(api.updated[0][1]["name"], "New title")
        self.assertEqual(api.updated[0][1]["desc"], "Local description")
        self.assertEqual(api.updated[0][1]["dueComplete"], True)
        self.assertEqual(api.updated[0][1]["due"], "2026-09-14T00:01:00Z")
        self.assertFalse(api.label_changes)
        self.assertEqual(api.bundle["card"]["idList"], config.list_id)
        self.assertEqual(report["pushed"], 1)
        self.assertGreaterEqual(report["operations"], 1)
        self.assertTrue((root / "PLAN" / f"done-{slugify_title('New title')}.md").exists())

    def test_file_changed_during_remote_write_gets_a_review_artifact(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["description"] = "Local update"
        path.write_text(render_document(metadata), encoding="utf-8")
        original_update = api.update_card

        def update_and_edit_file(card_id, fields):
            path.write_text("# External edit while request was running\n", encoding="utf-8")
            return original_update(card_id, fields)

        api.update_card = update_and_edit_file

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(encoding="utf-8"), "# External edit while request was running\n")
        self.assertTrue(list((root / "PLAN" / ".conflicts").glob("*.md")))
        self.assertEqual(report["conflicts"], 1)

    def test_rejects_unknown_label_in_local_editable_labels(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["label_ids"] = ["abcdef1234567890abcdef99"]
        path.write_text(render_document(metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertGreaterEqual(report["failures"], 1)
        self.assertFalse(api.label_changes)

    def test_done_named_label_is_editable_as_a_normal_label(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["label_ids"] = ["abcdef1234567890abcdef56"]
        path.write_text(render_document(metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["pushed"], 1)
        self.assertEqual(
            api.label_changes,
            [("add", api.bundle["card"]["id"], "abcdef1234567890abcdef56")],
        )

    def test_creates_conflict_without_updating_remote(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["description"] = "Local description"
        path.write_text(render_document(metadata), encoding="utf-8")
        api.bundle = sample_bundle("Remote description")
        api.cards = [api.bundle["card"]]

        messages = []
        report = sync_once(
            config,
            api,
            now="2026-09-14T00:01:00Z",
            progress=messages.append,
        )
        self.assertFalse(api.updated)
        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(len(list((root / "PLAN" / ".conflicts").glob("*.md"))), 1)
        conflict_message = next(message for message in messages if "CONFLICT" in message)
        self.assertIn("local=TODO", conflict_message)
        self.assertIn("Trello=TODO", conflict_message)
        self.assertIn("Nothing was sent", conflict_message)
        self.assertIn("Artifact: .conflicts", conflict_message)

    def test_recreates_a_deleted_conflict_artifact_without_overwriting_the_card(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["description"] = "local"
        path.write_text(render_document(metadata), encoding="utf-8")
        api.bundle["card"]["desc"] = "remote"
        sync_once(config, api, now="2026-09-14T00:01:00Z")
        artifact = next((root / "PLAN" / ".conflicts").glob("*.md"))
        artifact.unlink()

        report = sync_once(config, api, now="2026-09-14T00:02:00Z")
        self.assertEqual(report["conflicts"], 1)
        self.assertTrue(artifact.exists())
        self.assertFalse(api.updated)

    def test_moves_missing_card_file_to_recovery_directory(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.cards = []
        api.get_card = lambda card_id: {
            **api.bundle["card"],
            "idList": "abcdef1234567890abcdef99",
        }
        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["removed"], 1)
        self.assertEqual(len(report["recovery_paths"]), 1)
        self.assertFalse(plan_card_files(root))
        self.assertEqual(len(list((root / "PLAN" / ".removed").glob("*.md"))), 1)

    def test_missing_card_with_local_edits_is_preserved_for_review(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["description"] = "Local work that must not be discarded"
        path.write_text(render_document(metadata), encoding="utf-8")
        api.cards = []
        api.get_card = lambda card_id: {**api.bundle["card"], "idList": "abcdef1234567890abcdef99"}

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertTrue(path.exists())
        self.assertEqual(report["removed"], 0)
        self.assertTrue(list((root / "PLAN" / ".conflicts").glob("*.md")))

    def test_keeps_file_when_missing_inventory_still_reports_same_list(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.cards = []
        api.get_card = lambda card_id: {**api.bundle["card"], "idList": config.list_id}

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["removed"], 0)
        self.assertGreaterEqual(report["failures"], 1)
        self.assertEqual(len(plan_card_files(root)), 1)

    def test_missing_404_revalidates_scope_before_recovery(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.cards = []
        calls = []
        original_list = api.get_list
        original_board = api.get_board
        original_cards = api.get_board_cards

        def missing_card(card_id):
            raise RemoteError("gone", status=404)

        api.get_card = missing_card
        api.get_list = lambda list_id: (calls.append("list") or original_list(list_id))
        api.get_board = lambda board_id: (calls.append("board") or original_board(board_id))
        api.get_board_cards = lambda board_id: (calls.append("cards") or original_cards(board_id))

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertEqual(report["removed"], 1)
        self.assertGreaterEqual(calls.count("list"), 2)
        self.assertGreaterEqual(calls.count("board"), 2)

    def test_corrupt_managed_file_disables_cleanup(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        card_path = next_plan_card(root)
        (root / "PLAN" / "todo-broken.md").write_text(
            "<!-- syncassist:metadata\nnot-json\nsyncassist:end -->\n", encoding="utf-8"
        )
        api.cards = []
        api.get_card = lambda card_id: (_ for _ in ()).throw(RemoteError("gone", status=404))

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertTrue(card_path.exists())
        self.assertEqual(report["removed"], 0)
        self.assertTrue(report["cleanup_skipped"])

    def test_recreates_a_locally_deleted_file(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        next_plan_card(root).unlink()

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["created"], 1)
        self.assertFalse(api.updated)

    def test_second_unchanged_run_does_not_rewrite_or_call_mutations(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        original_text = path.read_text(encoding="utf-8")
        original_mtime = path.stat().st_mtime_ns

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["unchanged"], 1)
        self.assertEqual(report["updated"], 0)
        self.assertEqual(report["pushed"], 0)
        self.assertEqual(path.read_text(encoding="utf-8"), original_text)
        self.assertEqual(path.stat().st_mtime_ns, original_mtime)
        self.assertFalse(api.updated)
        self.assertFalse(api.label_changes)
        self.assertEqual(api.bundle_reads, 2)

    def test_progress_reports_each_phase_and_card_status(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        messages = []

        sync_once(config, api, now="2026-09-14T00:00:00Z", progress=messages.append)

        self.assertIn("Validating configuration and Trello inventory", messages[0])
        self.assertTrue(any("Inventory ready" in message for message in messages))
        self.assertTrue(any("Reading card 1/1" in message for message in messages))
        self.assertTrue(any("Syncing card 1/1" in message for message in messages))
        self.assertTrue(any("Synchronization completed in" in message for message in messages))

    def test_stale_read_only_conflict_does_not_block_remote_status(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        metadata = parsed.metadata
        metadata["sync"]["conflict"] = {
            "conflict_id": "legacy123456",
            "created_at": "2026-09-14T00:00:00Z",
            "expected_remote_hash": canonical_hash(parsed.projection),
            "reason": "local_read_only_section_changed",
        }
        metadata["sync"]["resolution"] = None
        path.write_text(render_document(metadata), encoding="utf-8")
        artifact = root / "PLAN" / ".conflicts" / f"{api.bundle['card']['id']}-legacy123456.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("legacy conflict record\n", encoding="utf-8")
        api.bundle["card"]["dueComplete"] = True
        messages = []

        report = sync_once(
            config,
            api,
            now="2026-09-14T00:01:00Z",
            progress=messages.append,
        )

        self.assertEqual(report["conflicts"], 0)
        self.assertEqual(report["renamed"], 1)
        self.assertTrue((root / "PLAN" / "done-card.md").exists())
        self.assertFalse(path.exists())
        self.assertEqual(artifact.read_text(encoding="utf-8"), "legacy conflict record\n")
        final = parse_document(
            root / "PLAN" / "done-card.md",
            (root / "PLAN" / "done-card.md").read_text(encoding="utf-8"),
        )
        self.assertIsNone(final.metadata["sync"].get("conflict"))
        self.assertTrue(any("Legacy read-only conflict cleared" in message for message in messages))

    def test_updates_existing_checklist_item_without_recreating_it(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        bundle = sample_bundle()
        checklist_id = "abcdef1234567890abcdef90"
        item_id = "abcdef1234567890abcdef91"
        bundle["checklists"] = [
            {
                "id": checklist_id,
                "name": "Checklist",
                "checkItems": [{"id": item_id, "name": "Old", "state": "incomplete"}],
            }
        ]
        api = FakeApi(bundle)
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["checklists"][0]["items"][0]["name"] = "New"
        metadata["content"]["checklists"][0]["items"][0]["state"] = "complete"
        path.write_text(render_document(metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        item = api.bundle["checklists"][0]["checkItems"][0]
        self.assertEqual(item["id"], item_id)
        self.assertEqual(item["name"], "New")
        self.assertEqual(item["state"], "complete")
        self.assertEqual(report["pushed"], 1)

    def test_missing_existing_checkitem_requires_explicit_delete_marker(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        bundle = sample_bundle()
        checklist_id = "abcdef1234567890abcdef90"
        item_id = "abcdef1234567890abcdef91"
        bundle["checklists"] = [
            {
                "id": checklist_id,
                "name": "Checklist",
                "checkItems": [{"id": item_id, "name": "Keep me", "state": "incomplete"}],
            }
        ]
        api = FakeApi(bundle)
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["checklists"][0]["items"] = []
        path.write_text(render_document(metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertGreaterEqual(report["failures"], 1)
        self.assertEqual(report["pushed"], 0)
        self.assertEqual(api.bundle["checklists"][0]["checkItems"][0]["id"], item_id)

    def test_explicit_checklist_and_item_deletes_are_reported(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        checklist_id = "abcdef1234567890abcdef90"
        item_id = "abcdef1234567890abcdef91"
        second_checklist_id = "abcdef1234567890abcdef92"
        bundle = sample_bundle()
        bundle["checklists"] = [
            {"id": checklist_id, "name": "Keep", "checkItems": [{"id": item_id, "name": "Remove", "state": "incomplete"}]},
            {"id": second_checklist_id, "name": "Delete", "checkItems": []},
        ]
        api = FakeApi(bundle)
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            f"<!-- syncassist:item={item_id} -->",
            f"<!-- syncassist:item={item_id} delete -->",
        ).replace(
            f"<!-- syncassist:checklist={second_checklist_id} -->",
            f"<!-- syncassist:checklist={second_checklist_id} delete -->",
        )
        path.write_text(text, encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertEqual(report["deleted_items"], 1)
        self.assertEqual(report["deleted_checklists"], 1)
        self.assertEqual(api.bundle["checklists"][0]["checkItems"], [])
        self.assertEqual(len(api.bundle["checklists"]), 1)

    def test_moves_an_existing_checkitem_between_checklists_by_id(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        bundle = sample_bundle()
        checklist_one = "abcdef1234567890abcdef90"
        checklist_two = "abcdef1234567890abcdef92"
        item_one = "abcdef1234567890abcdef91"
        item_two = "abcdef1234567890abcdef93"
        bundle["checklists"] = [
            {
                "id": checklist_one,
                "name": "First",
                "checkItems": [{"id": item_one, "name": "Move me", "state": "incomplete"}],
            },
            {
                "id": checklist_two,
                "name": "Second",
                "checkItems": [{"id": item_two, "name": "Stay here", "state": "incomplete"}],
            },
        ]
        api = FakeApi(bundle)
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["checklists"] = [
            {"id": checklist_one, "name": "First", "items": []},
            {
                "id": checklist_two,
                "name": "Second",
                "items": [
                    {"id": item_two, "name": "Stay here", "state": "incomplete"},
                    {"id": item_one, "name": "Move me", "state": "incomplete"},
                ],
            },
        ]
        path.write_text(render_document(metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["pushed"], 1)
        self.assertEqual(api.bundle["checklists"][0]["checkItems"], [])
        self.assertEqual(
            [item["id"] for item in api.bundle["checklists"][1]["checkItems"]], [item_two, item_one]
        )
        self.assertTrue(any(update[1] == item_one and update[2]["idChecklist"] == checklist_two for update in api.checkitem_updates))

    def test_creates_new_checklist_and_item_from_explicit_temporary_ids(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["checklists"] = [
            {
                "id": "new:acceptance",
                "name": "Acceptance",
                "items": [{"id": "new:first", "name": "Run test", "state": "incomplete"}],
            }
        ]
        path.write_text(render_document(metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(len(api.bundle["checklists"]), 1)
        self.assertEqual(api.bundle["checklists"][0]["checkItems"][0]["name"], "Run test")
        self.assertEqual(report["pushed"], 1)

    def test_applies_remote_only_change_to_the_existing_file(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.bundle["card"]["desc"] = "Remote description"

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        path = next_plan_card(root)
        parsed = parse_document(path, path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.projection["description"], "Remote description")
        self.assertEqual(report["updated"], 1)

    def test_local_read_only_edit_is_preserved_without_a_conflict(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("> **Due date:** not defined", "> **Due date:** local note"), encoding="utf-8")
        api.bundle["card"]["desc"] = "Remote description"

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertEqual(report["conflicts"], 0)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("> **Due date:** local note", path.read_text(encoding="utf-8"))
        self.assertEqual(
            parse_document(path, path.read_text(encoding="utf-8")).projection["description"],
            "Remote description",
        )

    def test_board_label_inventory_change_does_not_create_a_conflict(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.labels.append({"id": "abcdef1234567890abcdef78", "name": "Another", "color": "blue"})

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")

        self.assertEqual(report["conflicts"], 0)
        self.assertEqual(report["failures"], 0)

    def test_remote_due_complete_changes_the_filename(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.bundle["card"]["dueComplete"] = True

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["renamed"], 1)
        self.assertTrue((root / "PLAN" / "done-card.md").exists())

    def test_remote_done_label_does_not_change_the_filename(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        api.bundle["card"]["idLabels"] = ["abcdef1234567890abcdef56"]

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["renamed"], 0)
        self.assertTrue((root / "PLAN" / "todo-card.md").exists())
        parsed = parse_document(
            root / "PLAN" / "todo-card.md",
            (root / "PLAN" / "todo-card.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(parsed.projection["label_ids"], ["abcdef1234567890abcdef56"])

    def test_local_todo_unchecks_due_without_changing_the_due_date(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        bundle = sample_bundle()
        bundle["card"]["due"] = "2026-09-20T12:00:00.000Z"
        bundle["card"]["dueComplete"] = True
        api = FakeApi(bundle)
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        path.rename(root / "PLAN" / "todo-card.md")

        report = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertEqual(report["pushed"], 1)
        self.assertEqual(api.updated[0][1], {"dueComplete": False})
        self.assertEqual(api.bundle["card"]["due"], "2026-09-20T12:00:00.000Z")
        self.assertFalse(api.label_changes)

    def test_explicit_local_resolution_pushes_the_chosen_version(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["description"] = "Local description"
        path.write_text(render_document(metadata), encoding="utf-8")
        api.bundle["card"]["desc"] = "Remote description"
        sync_once(config, api, now="2026-09-14T00:01:00Z")

        conflict_metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        conflict = conflict_metadata["sync"]["conflict"]
        conflict_metadata["sync"]["resolution"] = {
            "conflict_id": conflict["conflict_id"],
            "choice": "local",
            "expected_remote_hash": conflict["expected_remote_hash"],
        }
        path.write_text(render_document(conflict_metadata), encoding="utf-8")

        report = sync_once(config, api, now="2026-09-14T00:02:00Z")
        self.assertEqual(api.bundle["card"]["desc"], "Local description")
        self.assertEqual(report["conflicts"], 0)
        self.assertEqual(report["pushed"], 1)
        artifact = next((root / "PLAN" / ".conflicts").glob("*.md"))
        self.assertIn("resolved", artifact.read_text(encoding="utf-8").lower())

    def test_ambiguous_new_card_creation_is_reconciled_without_a_duplicate(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        api.cards = []
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        template = root / "PLAN" / TEMPLATE_FILENAME
        new_path = root / "PLAN" / "todo-people.md"
        new_path.write_text(
            template.read_text(encoding="utf-8").replace("# New task", "# People", 1),
            encoding="utf-8",
        )
        original_create = api.create_card

        def create_then_lose_response(*args, **kwargs):
            original_create(*args, **kwargs)
            raise AmbiguousOperation("lost create response")

        api.create_card = create_then_lose_response
        first = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertGreaterEqual(first["failures"], 1)
        self.assertEqual(len(api.cards), 1)

        api.create_card = original_create
        second = sync_once(config, api, now="2026-09-14T00:02:00Z")

        self.assertEqual(len(api.cards), 1)
        self.assertEqual(second["conflicts"], 0)
        self.assertTrue(parse_document(new_path, new_path.read_text(encoding="utf-8")).metadata["trello_card_id"])

    def test_ambiguous_new_card_with_changed_local_intent_is_not_replayed(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        api.cards = []
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        template = root / "PLAN" / TEMPLATE_FILENAME
        new_path = root / "PLAN" / "todo-people.md"
        new_path.write_text(template.read_text(encoding="utf-8").replace("# New task", "# People", 1), encoding="utf-8")
        original_create = api.create_card

        def create_then_lose_response(*args, **kwargs):
            original_create(*args, **kwargs)
            raise AmbiguousOperation("lost create response")

        api.create_card = create_then_lose_response
        sync_once(config, api, now="2026-09-14T00:01:00Z")
        new_path.write_text(new_path.read_text(encoding="utf-8").replace("# People", "# Changed", 1), encoding="utf-8")
        api.create_card = original_create

        report = sync_once(config, api, now="2026-09-14T00:02:00Z")

        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(len(api.cards), 1)
        self.assertEqual(api.bundle["card"]["name"], "People")

    def test_import_source_survives_card_recovery(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["import_source"] = {"relative_path": "source.txt", "sha256": "a" * 64}
        path.write_text(render_document(metadata), encoding="utf-8")

        api.bundle["card"]["idList"] = "abcdef1234567890abcdef99"
        api.cards = []
        sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertFalse(path.exists())

        api.bundle["card"]["idList"] = config.list_id
        api.cards = [api.bundle["card"]]
        sync_once(config, api, now="2026-09-14T00:02:00Z")
        recovered = next_plan_card(root)
        recovered_metadata = parse_document(
            recovered, recovered.read_text(encoding="utf-8")
        ).metadata
        self.assertEqual(recovered_metadata["import_source"]["relative_path"], "source.txt")

    def test_ambiguous_operation_is_not_repeated_on_the_next_run(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["checklists"] = [
            {"id": "new:acceptance", "name": "Acceptance", "items": []}
        ]
        path.write_text(render_document(metadata), encoding="utf-8")

        def ambiguous(*args, **kwargs):
            raise AmbiguousOperation("unknown create result")

        api.create_checklist = ambiguous
        first = sync_once(config, api, now="2026-09-14T00:01:00Z")
        second = sync_once(config, api, now="2026-09-14T00:02:00Z")
        self.assertGreaterEqual(first["failures"], 1)
        self.assertEqual(second["conflicts"], 1)

    def test_applied_ambiguous_checklist_creation_is_reconciled(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        api = FakeApi(sample_bundle())
        sync_once(config, api, now="2026-09-14T00:00:00Z")
        path = next_plan_card(root)
        metadata = parse_document(path, path.read_text(encoding="utf-8")).metadata
        metadata["content"]["checklists"] = [
            {"id": "new:acceptance", "name": "Acceptance", "items": []}
        ]
        path.write_text(render_document(metadata), encoding="utf-8")
        original_create = api.create_checklist

        def create_then_lose_response(*args, **kwargs):
            original_create(*args, **kwargs)
            raise AmbiguousOperation("lost checklist response")

        api.create_checklist = create_then_lose_response
        first = sync_once(config, api, now="2026-09-14T00:01:00Z")
        self.assertGreaterEqual(first["failures"], 1)
        changed = parse_document(path, path.read_text(encoding="utf-8")).metadata
        changed["content"]["checklists"][0]["name"] = "Changed after request"
        path.write_text(render_document(changed), encoding="utf-8")

        api.create_checklist = original_create
        second = sync_once(config, api, now="2026-09-14T00:02:00Z")

        self.assertEqual(second["conflicts"], 1)
        self.assertEqual(second["pushed"], 0)
        self.assertEqual(len(api.bundle["checklists"]), 1)

    def test_lock_prevents_a_second_execution(self):
        root = Path(tempfile.mkdtemp())
        config = self.make_config(root)
        (root / "PLAN").mkdir()
        (root / "PLAN" / ".sync.lock").write_text("{}", encoding="utf-8")
        with self.assertRaises(Exception):
            sync_once(config, FakeApi(sample_bundle()), now="2026-09-14T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
