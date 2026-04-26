"""End-to-end verification of the documented `vn show search` drill-down
workflow.  Each test mirrors a command from the answer the user got and
asserts (a) it parses, (b) it hits the expected API path, (c) the
output looks right.  Tests that *would* prove a wrong claim fail loudly
so we know to update the docs.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from vn import cli


class FakeClient:
    def __init__(self, *_, **__):
        self.calls: list[tuple] = []
        self.responses: dict[tuple[str, str], Any] = {}

    def request(self, method, path, *, params=None, body=None):
        self.calls.append((method, path, params, body))
        return self.responses.get((method, path), {"ok": True})

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
    return fc


# ---------- the documented workflow ---------------------------------------

def test_step0_search_returns_id_path_title_columns(fake_client, capsys):
    fake_client.responses[("GET", "/api/search")] = [
        {"id": 42, "path": "FIT Val Weekly/FIT weekly ww17.md", "title": "ww17"},
        {"id": 58, "path": "projects/ww18/standup.md", "title": "ww18 standup"},
    ]
    rc = cli.main(["show", "search", "fit-val"])
    assert rc == 0
    out = capsys.readouterr().out
    headers = out.splitlines()[0].split()
    assert headers == ["ID", "PATH", "TITLE"]
    assert "42" in out and "ww17" in out
    # And confirm the wire call:
    method, path, params, _ = fake_client.calls[0]
    assert (method, path) == ("GET", "/api/search")
    assert params == {"q": "fit-val"}


def test_step1a_show_note_by_id(fake_client, capsys):
    fake_client.responses[("GET", "/api/notes/42")] = {
        "id": 42, "path": "x.md", "title": "T", "etag": "e1",
    }
    rc = cli.main(["show", "notes", "42"])
    assert rc == 0
    assert ("GET", "/api/notes/42") == fake_client.calls[0][:2]


def test_step1b_show_note_by_path_resolves_via_listing(fake_client, capsys):
    # Path resolution: `show note <path>` first lists, then fetches by id
    fake_client.responses[("GET", "/api/notes")] = [
        {"id": 42, "path": "FIT Val Weekly/FIT weekly ww17.md", "title": "x", "etag": "e"},
    ]
    fake_client.responses[("GET", "/api/notes/42")] = {
        "id": 42, "path": "FIT Val Weekly/FIT weekly ww17.md", "title": "x", "etag": "e",
    }
    rc = cli.main(["show", "notes", "FIT Val Weekly/FIT weekly ww17.md"])
    assert rc == 0
    paths = [c[1] for c in fake_client.calls]
    assert "/api/notes" in paths and "/api/notes/42" in paths


def test_step2_show_note_full_dumps_body(fake_client, capsys):
    fake_client.responses[("GET", "/api/notes/42")] = {
        "id": 42, "path": "x.md", "title": "T", "etag": "e",
        "body_md": "# ww17\n- task one\n- task two\n",
    }
    cli.main(["show", "notes", "42", "--full"])
    out = capsys.readouterr().out
    assert "task one" in out and "task two" in out


def test_step3_vn_list_does_NOT_have_note_flag():
    """Regression on the docs: there is no --note on vn list today."""
    p = cli.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["list", "--note", "42"])


def test_step3_workaround_filter_by_project(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks")] = {"tasks": [
        {"id": "T-1", "status": "wip", "priority": "P1", "eta": None,
         "owners": ["alice"], "title": "demo", "kind": "task"},
    ]}
    rc = cli.main(["list", "--project", "FIT Val Weekly"])
    assert rc == 0
    method, path, params, _ = fake_client.calls[0]
    assert (method, path) == ("GET", "/api/tasks")
    assert params.get("project") == "FIT Val Weekly"


def test_step4_show_task_by_ref(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks/T-ABC123")] = {
        "id": "T-ABC123", "status": "wip", "priority": "P1", "eta": None,
        "owners": ["a"], "title": "demo", "kind": "task", "note_id": 42,
    }
    rc = cli.main(["show", "task", "T-ABC123"])
    assert rc == 0
    assert ("GET", "/api/tasks/T-ABC123") == fake_client.calls[0][:2]


def test_step4_show_task_with_plus_note_id_column(fake_client, capsys):
    fake_client.responses[("GET", "/api/tasks/T-ABC123")] = {
        "id": "T-ABC123", "status": "wip", "priority": "P1", "eta": None,
        "owners": ["a"], "title": "demo", "kind": "task", "note_id": 42,
    }
    rc = cli.main(["show", "task", "T-ABC123", "--columns", "+kind,+note_id"])
    assert rc == 0
    out = capsys.readouterr().out
    headers = out.splitlines()[0].split()
    assert headers[-2:] == ["KIND", "NOTE_ID"]
    # And the value renders:
    data_row = out.splitlines()[2].split()
    assert data_row[-1] == "42"


def test_step5_show_links(fake_client, capsys):
    fake_client.responses[("GET", "/api/cards/T-ABC123/links")] = {
        "task_id": 1, "task_uuid": "u", "slug": "T-ABC123",
        "links": [{"other_slug": "T-X", "kind": "blocks", "direction": "in"}],
    }
    rc = cli.main(["show", "links", "T-ABC123"])
    assert rc == 0
    assert ("GET", "/api/cards/T-ABC123/links") == fake_client.calls[0][:2]


def test_jq_pipeline_global_json_flag(fake_client, capsys):
    """vn --json show search ... must emit a parseable JSON list."""
    fake_client.responses[("GET", "/api/search")] = [
        {"id": 1, "path": "a.md", "title": "A"},
        {"id": 2, "path": "b.md", "title": "B"},
    ]
    cli.main(["--json", "show", "search", "fit-val"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert [r["path"] for r in parsed] == ["a.md", "b.md"]
