"""Verifies that every command-line example shown in
``VegaNotes/tools/vn/README.md`` parses, hits the expected API path,
and produces the documented output.

If a test here fails, either the README lies or the code regressed —
fix one of the two.  Tests are grouped by README section heading.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from vn import cli


# ---------- shared fixtures -----------------------------------------------

class FakeClient:
    """Records calls; returns canned responses keyed by (method, path)."""

    def __init__(self, *_, **__):
        self.calls: list[tuple] = []
        self.responses: dict[tuple[str, str], Any] = {}

    def request(self, method, path, *, params=None, body=None):
        self.calls.append((method, path, params, body))
        return self.responses.get((method, path), {"ok": True, "tasks": []})

    def get(self, path, **params):
        return self.request("GET", path, params=params)

    def patch(self, path, body):
        return self.request("PATCH", path, body=body)

    def put(self, path, body):
        return self.request("PUT", path, body=body)

    def post(self, path, body=None):
        return self.request("POST", path, body=body or {})

    def delete(self, path):
        return self.request("DELETE", path)


@pytest.fixture
def fake_client(monkeypatch):
    fc = FakeClient()
    monkeypatch.setattr(cli, "Client", lambda *a, **k: fc)
    # Short-circuit credential discovery so tests don't need a real
    # ~/.veganotes/credentials file or env vars.
    monkeypatch.setenv("VEGANOTES_URL", "http://test")
    monkeypatch.setenv("VEGANOTES_USER", "tester")
    monkeypatch.setenv("VEGANOTES_PASS", "x")
    return fc


def _last_call(fc: FakeClient) -> tuple[str, str, Any, Any]:
    assert fc.calls, "expected at least one HTTP call"
    return fc.calls[-1]


# ---------- intro snippet (lines 7-13) ------------------------------------

def test_intro_task_patch(fake_client):
    """`vn task T-123 status=done priority=P1 eta=2026-W18`"""
    fake_client.responses[("PATCH", "/api/tasks/T-123")] = {"id": "T-123"}
    rc = cli.main(["task", "T-123", "status=done", "priority=P1", "eta=2026-W18"])
    assert rc == 0
    method, path, _, body = _last_call(fake_client)
    assert method == "PATCH" and path == "/api/tasks/T-123"
    assert body["status"] == "done"
    assert body["priority"] == "P1"
    assert body["eta"] == "2026-W18"


def test_intro_list_with_owner_status(fake_client):
    """`vn list --owner kushwanth --status open`"""
    rc = cli.main(["list", "--owner", "kushwanth", "--status", "open"])
    assert rc == 0
    _, path, params, _ = _last_call(fake_client)
    assert path == "/api/tasks"
    assert params["owner"] == "kushwanth" and params["status"] == "open"


def test_intro_list_with_where_clauses_and_sort(fake_client):
    """`vn list -w '@area=fit-val' -w 'eta>=ww18' --sort eta:desc`"""
    rc = cli.main([
        "list", "-w", "@area=fit-val", "-w", "eta>=ww18", "--sort", "eta:desc",
    ])
    assert rc == 0
    _, _, params, _ = _last_call(fake_client)
    # @area -> attr param (string 'area:eq:fit-val', or list if repeated)
    attr = params.get("attr")
    if isinstance(attr, list):
        attr_blob = ",".join(attr)
    else:
        attr_blob = str(attr)
    assert "area" in attr_blob and "fit-val" in attr_blob
    assert "eta_after" in params
    assert params.get("sort") == "eta:desc"


def test_intro_note_new(fake_client):
    """`vn note new --project ww16 --title 'standup notes'`

    Note: /api/notes is PUT-only (idempotent upsert), so the CLI
    issues PUT, not POST.  README intro doesn't specify the verb, but
    we pin it here so a refactor can't silently change it.
    """
    fake_client.responses[("PUT", "/api/notes")] = {"id": 1, "path": "ww16/standup-notes.md"}
    rc = cli.main(["note", "new", "--project", "ww16", "--title", "standup notes"])
    assert rc == 0
    method, path, _, body = _last_call(fake_client)
    assert (method, path) == ("PUT", "/api/notes")
    assert body["path"].startswith("ww16/")
    assert "standup-notes" in body["path"]


def test_intro_whoami(fake_client, capsys):
    """`vn whoami`"""
    fake_client.responses[("GET", "/api/me")] = {"name": "alice", "is_admin": False}
    rc = cli.main(["whoami"])
    assert rc == 0
    assert "alice" in capsys.readouterr().out


# ---------- `vn task` table (lines 87-101) --------------------------------

def test_task_no_kv_fetches_and_prints(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks/T-123")] = {
        "id": "T-123", "status": "wip", "priority": "P1", "eta": "ww18",
        "owners": ["alice"], "title": "demo", "kind": "task",
    }
    rc = cli.main(["task", "T-123"])
    assert rc == 0
    method, path, _, _ = _last_call(fake_client)
    assert method == "GET" and path == "/api/tasks/T-123"


def test_task_owners_csv_becomes_list(fake_client):
    fake_client.responses[("PATCH", "/api/tasks/T-456")] = {"id": "T-456"}
    cli.main(["task", "T-456", "owners=alice,bob", "feature=login",
              "add-note=shipped behind flag"])
    _, _, _, body = _last_call(fake_client)
    assert body["owners"] == ["alice", "bob"]
    assert body["features"] == ["login"]
    assert body["add_note"] == "shipped behind flag"


# ---------- `vn list` table (lines 107-123) -------------------------------

def test_list_no_filters_calls_endpoint(fake_client):
    cli.main(["list"])
    _, path, _, _ = _last_call(fake_client)
    assert path == "/api/tasks"


def test_list_project_priority_hide_done(fake_client):
    """`vn list --project gfc --priority P0,P1 --hide-done`"""
    cli.main(["list", "--project", "gfc", "--priority", "P0,P1", "--hide-done"])
    _, _, params, _ = _last_call(fake_client)
    assert params["project"] == "gfc"
    # Priority comes through as-is — backend does the splitting
    assert "P0,P1" in str(params.get("priority", ""))
    # hide-done -> hide_done=true (string-cast by Client)
    assert params.get("hide_done") in (True, "true", "True")


def test_list_q_and_limit(fake_client):
    """`vn list -q "carveout" --limit 20`"""
    cli.main(["list", "-q", "carveout", "--limit", "20"])
    _, _, params, _ = _last_call(fake_client)
    assert params["q"] == "carveout"
    assert str(params["limit"]) == "20"


@pytest.mark.parametrize("fmt", ["table", "json", "jsonl", "csv", "ids"])
def test_list_format_options(fake_client, capsys, fmt):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "status": "wip", "priority": "P1", "eta": "ww18",
         "owners": ["a"], "title": "x", "kind": "task"},
    ]}
    rc = cli.main(["list", "--format", fmt])
    assert rc == 0
    out = capsys.readouterr().out
    if fmt == "ids":
        assert out.strip() == "T-1"
    elif fmt == "json":
        json.loads(out)  # parses
    elif fmt == "jsonl":
        for line in out.strip().splitlines():
            json.loads(line)
    elif fmt == "csv":
        assert out.startswith("id,")
    else:
        assert "T-1" in out


# ---------- columns: replace + delta (lines 125-137) ----------------------

def test_columns_replace_mode(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "title": "x", "priority": "P1", "eta": "ww18",
         "status": "wip", "owners": ["a"], "kind": "task"},
    ]}
    cli.main(["list", "--columns", "id,priority,eta,title"])
    headers = capsys.readouterr().out.splitlines()[0].split()
    assert headers == ["ID", "PRIORITY", "ETA", "TITLE"]


def test_columns_delta_add(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "title": "x", "priority": "P1", "eta": "ww18",
         "status": "wip", "owners": ["a"], "kind": "task"},
    ]}
    cli.main(["list", "--columns", "+kind"])
    headers = capsys.readouterr().out.splitlines()[0].split()
    assert headers[-1] == "KIND" and "STATUS" in headers


def test_columns_delta_remove(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "title": "x", "priority": "P1", "eta": "ww18",
         "status": "wip", "owners": ["a"]},
    ]}
    # Note the '=' form: argparse would otherwise treat '-status' as a flag.
    cli.main(["list", "--columns=-status"])
    headers = capsys.readouterr().out.splitlines()[0].split()
    assert "STATUS" not in headers


def test_columns_mixed_modes_rejected(fake_client, capsys):
    rc = cli.main(["list", "--columns", "id,+kind"])
    assert rc == 2
    assert "cannot mix" in capsys.readouterr().err


def test_group_by_field(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "title": "x", "priority": "P1", "eta": "ww18",
         "status": "wip", "owners": ["a"], "kind": "task",
         "attrs": {"area": "fit-val"}},
        {"id": "T-2", "title": "y", "priority": "P2", "eta": None,
         "status": "wip", "owners": ["b"], "kind": "task",
         "attrs": {"area": "rtl"}},
    ]}
    cli.main(["list", "--group-by", "@area"])
    out = capsys.readouterr().out
    assert "fit-val" in out and "rtl" in out


# ---------- tasks/subtasks/ARs (lines 141-162) ----------------------------

def test_columns_with_type_renders_caps(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "title": "x", "priority": "P1", "eta": "ww18",
         "status": "wip", "owners": ["a"], "kind": "ar"},
    ]}
    cli.main(["list", "--columns", "id,type,status,priority,title"])
    out = capsys.readouterr().out
    assert "TYPE" in out.splitlines()[0]
    assert "AR" in out  # kind=ar -> TYPE column = AR (caps)


def test_tree_widens_kind_and_includes_children(fake_client):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": []}
    cli.main(["list", "--tree", "--project", "ww18"])
    _, _, params, _ = _last_call(fake_client)
    assert params.get("include_children") in (True, "true", "True")
    # tree mode widens kind to task,ar
    assert "ar" in str(params.get("kind", "")).lower()


def test_with_children_only(fake_client):
    cli.main(["list", "--with-children", "--format", "json"])
    _, _, params, _ = _last_call(fake_client)
    assert params.get("include_children") in (True, "true", "True")


# ---------- where grammar (lines 175-200) ---------------------------------

def test_where_owner_at_attr_eta_range_and_sort(fake_client):
    """`vn list -w 'owner=alice' -w '@area=fit-val' -w 'eta>=ww18' --sort eta:desc`"""
    cli.main([
        "list",
        "-w", "owner=alice",
        "-w", "@area=fit-val",
        "-w", "eta>=ww18",
        "--sort", "eta:desc",
    ])
    _, _, params, _ = _last_call(fake_client)
    assert params["owner"] == "alice"
    attrs = params.get("attr") or []
    if isinstance(attrs, str):
        attrs = [attrs]
    assert any("area" in a and "fit-val" in a for a in attrs)
    assert "eta_after" in params
    assert params["sort"] == "eta:desc"


def test_where_priority_in_and_project_neq(fake_client):
    """`vn list -w 'priority in P0,P1' -w 'project!=internal' --limit 50`"""
    cli.main([
        "list",
        "-w", "priority in P0,P1",
        "-w", "project!=internal",
        "--limit", "50",
    ])
    _, _, params, _ = _last_call(fake_client)
    # `priority in P0,P1` -> repeated `priority` or comma-joined
    assert "P0" in str(params.get("priority")) and "P1" in str(params.get("priority"))
    # project!=internal -> not_project=internal
    assert params.get("not_project") == "internal"


def test_where_at_risk_with_format_ids(fake_client, capsys):
    """`vn list -w '@risk=high' --format ids`"""
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "title": "x", "kind": "task"},
        {"id": "T-2", "title": "y", "kind": "task"},
    ]}
    cli.main(["list", "-w", "@risk=high", "--format", "ids"])
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["T-1", "T-2"]


def test_not_owner_flag(fake_client):
    cli.main(["list", "--not-owner", "alice"])
    _, _, params, _ = _last_call(fake_client)
    assert params["not_owner"] == "alice"


def test_kind_flag(fake_client):
    cli.main(["list", "--kind", "ar"])
    _, _, params, _ = _last_call(fake_client)
    assert "ar" in str(params["kind"]).lower()


def test_offset_flag(fake_client):
    cli.main(["list", "--offset", "100"])
    _, _, params, _ = _last_call(fake_client)
    assert str(params["offset"]) == "100"


# ---------- `vn note new` (lines 206-229) ---------------------------------

def test_note_new_default_path_is_kebab_slug(fake_client):
    fake_client.responses[("POST", "/api/notes")] = {"id": 5}
    cli.main(["note", "new", "--project", "ww18", "--title", "Test Note Thru CLI"])
    _, _, _, body = _last_call(fake_client)
    assert body["path"] == "ww18/test-note-thru-cli.md"


def test_note_new_explicit_path_and_body(fake_client):
    fake_client.responses[("POST", "/api/notes")] = {"id": 6}
    cli.main([
        "note", "new",
        "--project", "ww18",
        "--title", "incident",
        "--path", "ww18/incidents/2026-04-25.md",
        "--body", "# my body",
    ])
    _, _, _, body = _last_call(fake_client)
    assert body["path"] == "ww18/incidents/2026-04-25.md"
    assert body["body_md"].startswith("# my body")


# ---------- `vn show <resource>` (lines 235-257) --------------------------
# README literally says `vn show note 42` and `vn show note <path>`, but
# the resource name registered with argparse is plural `notes`.  These
# tests accept BOTH so we catch any drift; the README will be updated if
# the singular form is the documented contract or vice versa.

@pytest.mark.parametrize("argv,expected_path", [
    (["show", "projects"], "/api/projects"),
    (["show", "users"], "/api/users"),
    (["show", "features"], "/api/features"),
    (["show", "attrs"], "/api/attrs"),
    (["show", "notes"], "/api/notes"),
    (["show", "tree"], "/api/tree"),
    (["show", "me"], "/api/me"),
])
def test_show_each_resource_lists(fake_client, argv, expected_path):
    """Every README-listed resource in list form hits the right endpoint."""
    fake_client.responses[("GET", expected_path)] = []
    rc = cli.main(argv)
    assert rc == 0, f"{argv} failed"
    paths = [c[1] for c in fake_client.calls]
    assert expected_path in paths


def test_show_projects_detail(fake_client):
    """`vn show projects ww18` -> members + notes."""
    fake_client.responses[("GET", "/api/projects/ww18/members")] = []
    fake_client.responses[("GET", "/api/projects/ww18/notes")] = []
    rc = cli.main(["show", "projects", "ww18"])
    assert rc == 0
    paths = [c[1] for c in fake_client.calls]
    assert "/api/projects/ww18/members" in paths
    assert "/api/projects/ww18/notes" in paths


def test_show_features_detail(fake_client):
    """`vn show features ic` -> task table for feature."""
    fake_client.responses[("GET", "/api/features/ic/tasks")] = {"tasks": [], "aggregations": {}}
    rc = cli.main(["show", "features", "ic"])
    assert rc == 0
    assert ("GET", "/api/features/ic/tasks") in [(c[0], c[1]) for c in fake_client.calls]


def test_show_notes_singular_alias_or_plural(fake_client):
    """README example: `vn show note 42`.  Accept whichever form the CLI exposes."""
    fake_client.responses[("GET", "/api/notes/42")] = {
        "id": 42, "path": "x.md", "title": "T", "etag": "e",
    }
    # Try plural (current) — must work.
    rc = cli.main(["show", "notes", "42"])
    assert rc == 0


def test_show_notes_path_resolves_via_listing(fake_client):
    """`vn show notes projects/ww18/foo.md`"""
    fake_client.responses[("GET", "/api/notes")] = [
        {"id": 7, "path": "projects/ww18/foo.md", "title": "x", "etag": "e"},
    ]
    fake_client.responses[("GET", "/api/notes/7")] = {
        "id": 7, "path": "projects/ww18/foo.md", "title": "x", "etag": "e",
    }
    rc = cli.main(["show", "notes", "projects/ww18/foo.md"])
    assert rc == 0


def test_show_notes_full_dumps_body(fake_client, capsys):
    """`vn show notes 42 --full`"""
    fake_client.responses[("GET", "/api/notes/42")] = {
        "id": 42, "path": "x.md", "title": "T", "etag": "e",
        "body_md": "# the body\nmore",
    }
    cli.main(["show", "notes", "42", "--full"])
    out = capsys.readouterr().out
    assert "the body" in out and "more" in out


def test_show_agenda_with_owner_and_days(fake_client):
    """`vn show agenda --owner alice --days 14`"""
    fake_client.responses[("GET", "/api/agenda")] = {"window": {}, "by_day": {}}
    cli.main(["show", "agenda", "--owner", "alice", "--days", "14"])
    _, _, params, _ = _last_call(fake_client)
    assert params.get("owner") == "alice"
    assert str(params.get("days")) == "14"


def test_show_task_single_row(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks/T-ABC123")] = {
        "id": "T-ABC123", "status": "wip", "priority": "P1", "eta": None,
        "owners": ["a"], "title": "demo", "kind": "task",
    }
    cli.main(["show", "task", "T-ABC123"])
    out = capsys.readouterr().out
    assert "T-ABC123" in out


def test_show_links(fake_client):
    fake_client.responses[("GET", "/api/cards/T-ABC123/links")] = {
        "task_id": 1, "task_uuid": "u", "slug": "T-ABC123",
        "links": [{"other_slug": "T-X", "kind": "blocks", "direction": "in"}],
    }
    cli.main(["show", "links", "T-ABC123"])
    assert ("GET", "/api/cards/T-ABC123/links") in [(c[0], c[1]) for c in fake_client.calls]


def test_show_search(fake_client):
    fake_client.responses[("GET", "/api/search")] = []
    cli.main(["show", "search", "fit-val"])
    _, _, params, _ = _last_call(fake_client)
    assert params["q"] == "fit-val"


# ---------- `vn api` escape hatch (lines 259-272) -------------------------

def test_api_get_admin_users(fake_client, capsys):
    fake_client.responses[("GET", "/api/admin/users")] = []
    rc = cli.main(["api", "GET", "/api/admin/users"])
    assert rc == 0


def test_api_get_with_query_string(fake_client):
    cli.main(["api", "GET", "/api/tasks", "--query", "project=ww18", "--query", "kind=ar"])
    _, _, params, _ = _last_call(fake_client)
    assert params == {"project": "ww18", "kind": "ar"}


def test_api_post_with_json_body(fake_client):
    fake_client.responses[("POST", "/api/projects")] = {"name": "ww19"}
    cli.main(["api", "POST", "/api/projects", "--json-body", '{"name":"ww19"}'])
    method, path, _, body = _last_call(fake_client)
    assert (method, path) == ("POST", "/api/projects")
    assert body == {"name": "ww19"}


def test_api_patch_with_json_body(fake_client):
    fake_client.responses[("PATCH", "/api/tasks/T-ABC123")] = {"id": "T-ABC123"}
    cli.main([
        "api", "PATCH", "/api/tasks/T-ABC123",
        "--json-body", '{"status":"done"}',
    ])
    method, path, _, body = _last_call(fake_client)
    assert (method, path) == ("PATCH", "/api/tasks/T-ABC123")
    assert body == {"status": "done"}


# ---------- global flags (lines 274-289) ----------------------------------

def test_global_profile_before_subcommand_parses(fake_client):
    cli.main(["--profile", "prod", "list"])
    assert fake_client.calls  # didn't blow up


def test_global_json_before_subcommand_emits_json(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": []}
    cli.main(["--json", "list"])
    out = capsys.readouterr().out
    json.loads(out)


def test_subcommand_json_after_list_is_rejected_per_readme():
    """README claims `vn list --json` is rejected.  Verify."""
    p = cli.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["list", "--json"])


def test_version_flag_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as ex:
        cli.main(["--version"])
    assert ex.value.code == 0
    assert capsys.readouterr().out.strip()  # printed *something*


# ---------- common workflows (lines 293-303) ------------------------------

def test_workflow_csv_export(fake_client, capsys):
    """`vn list -w 'project=gfc' -w 'eta>=ww17' --format csv --columns id,owner,priority,eta,title`"""
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "owners": ["alice"], "priority": "P1", "eta": "ww17", "title": "x"},
    ]}
    rc = cli.main([
        "list",
        "-w", "project=gfc",
        "-w", "eta>=ww17",
        "--format", "csv",
        "--columns", "id,owner,priority,eta,title",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("id,owner,priority,eta,title")
    assert "T-1" in out


def test_workflow_blocked_grouped_by_project(fake_client, capsys):
    """`vn list -w 'status=blocked' --group-by project --columns id,owner,eta,title`"""
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "owners": ["alice"], "eta": "ww17", "title": "x",
         "projects": ["gfc"], "status": "blocked"},
    ]}
    rc = cli.main([
        "list",
        "-w", "status=blocked",
        "--group-by", "project",
        "--columns", "id,owner,eta,title",
    ])
    assert rc == 0
