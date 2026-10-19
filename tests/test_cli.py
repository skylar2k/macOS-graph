import json
import subprocess
import sys
from pathlib import Path

import click
from click.testing import CliRunner

from graph_macos.cli import docs
from graph_macos.cli.app import cli
from graph_macos.cli.docs import iter_commands
from graph_macos.cli.factory import build_commands
from graph_macos.errors import GraphMacosError
from graph_macos.resources.base import Resource

TOK = "52c74ba6-633e-4afd-8413-cebbbe4f4edf"
GUID = "d8d60ec8-5697-407b-975f-62e0e87b39c6"
FULL = f"ECV2_{TOK}_{GUID}"


def run(*args, input=None):
    r = CliRunner().invoke(cli, list(args), input=input)
    lines = [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")]
    return r, lines


def test_tree_has_every_resource_verb_and_custom_command():
    paths = {" ".join(p) for p, _ in iter_commands(cli)}
    assert {
        "devices list",
        "devices get",
        "devices delete",
        "users list",
        "groups get",
        "ade tokens list",
        "ade profiles update",
        "ade profiles assign",
        "ade devices list",
        "apps delete",
        "compliance-policies list",
        "configuration-profiles get",
    } <= paths
    assert "users delete" not in paths and "ade tokens update" not in paths


def test_every_write_command_is_gated_and_declares_scopes():
    for path, cmd in iter_commands(cli):
        assert cmd.scopes, path
        params = {p.name for p in cmd.params}
        if cmd.writes:
            assert {"yes", "max_items"} <= params, path
            assert all(".ReadWrite." in s for s in cmd.scopes), path
        else:
            assert "yes" not in params, path
            assert all(".Read." in s for s in cmd.scopes), path


def test_list_requests_read_scope_and_emits_ndjson(fake_graph):
    g = fake_graph(pages={"/deviceManagement/managedDevices": [{"id": "1"}, {"id": "2"}]})
    r, out = run("devices", "list", "--filter", "x eq 1")
    assert r.exit_code == 0 and out == [{"id": "1"}, {"id": "2"}]
    assert g.scopes == ("DeviceManagementManagedDevices.Read.All",)
    assert "x eq 1" in g.paged_calls[0][1]["$filter"]


def test_list_subresource_takes_ids_from_stdin(fake_graph):
    url = f"/deviceManagement/depOnboardingSettings/{TOK}/enrollmentProfiles"
    fake_graph(pages={url: [{"id": FULL}]})
    r, out = run("ade", "profiles", "list", input=f'{{"id":"{TOK}"}}\n')
    assert out == [{"id": FULL, "profileId": GUID}]


def test_list_subresource_with_no_ids_is_a_clean_error():
    r, _ = run("ade", "profiles", "list", input="")
    assert r.exit_code == 1 and "token id is required" in r.stderr


def test_quoted_jq_ids_work_as_arguments(fake_graph):
    g = fake_graph(get_result={"id": "d1"})
    r, out = run("devices", "get", '"d1"')
    assert out == [{"id": "d1"}] and g.get_calls == ["/deviceManagement/managedDevices/d1"]


def test_delete_is_dry_run_without_yes(fake_graph):
    g = fake_graph()
    r, out = run("devices", "delete", input='{"id":"a"}\n{"id":"b"}\n')
    assert r.exit_code == 0 and [o["status"] for o in out] == ["dry-run", "dry-run"]
    assert not g.batch_calls


def test_delete_with_yes_uses_write_scope_and_batches(fake_graph):
    g = fake_graph()
    r, out = run("devices", "delete", "--yes", "a", "b")
    assert out == [{"id": "a", "status": "deleted"}, {"id": "b", "status": "deleted"}]
    assert g.scopes == ("DeviceManagementManagedDevices.ReadWrite.All",)


def test_delete_exit_code_reflects_failures(fake_graph):
    fake_graph(batch_status=404)
    r, out = run("devices", "delete", "--yes", "a")
    assert r.exit_code == 1 and out[0]["status"] == "failed"


def test_delete_max_items_guard(fake_graph):
    g = fake_graph()
    r, _ = run("devices", "delete", "--yes", "--max-items", "1", "a", "b")
    assert r.exit_code == 1 and "refusing" in r.stderr and not g.batch_calls


def test_update_dry_run_masks_secrets_and_infers_token(fake_graph):
    g = fake_graph()
    r, [rec] = run(
        "ade",
        "profiles",
        "update",
        FULL,
        "--set",
        "adminAccountPassword=hunter2",
        "--set",
        "autoAdvanceSetupEnabled=true",
    )
    assert rec["patch"]["adminAccountPassword"] == "***" and "hunter2" not in r.output
    assert rec["patch"]["autoAdvanceSetupEnabled"] is True
    assert rec["patch"]["@odata.type"] == "#microsoft.graph.depMacOSEnrollmentProfile"
    assert not g.batch_calls


def test_update_with_yes_patches_the_right_url(fake_graph):
    g = fake_graph(batch_status=200)
    r, out = run("ade", "profiles", "update", "--yes", FULL, "--set", "description=hi")
    assert out == [{"id": FULL, "status": "updated"}]
    req = g.batch_calls[0][0]
    assert req["method"] == "PATCH"
    assert req["url"] == f"/deviceManagement/depOnboardingSettings/{TOK}/enrollmentProfiles/{FULL}"
    assert g.scopes == ("DeviceManagementServiceConfig.ReadWrite.All",)


def test_update_bare_id_needs_token():
    r, _ = run("ade", "profiles", "update", GUID, "--set", "a=1")
    assert r.exit_code == 1 and "--token is required" in r.stderr


def test_update_without_changes_is_a_clean_error():
    r, _ = run("ade", "profiles", "update", FULL)
    assert r.exit_code == 1 and "nothing to send" in r.stderr


def test_assign_dry_run_normalises_profile_and_infers_token(fake_graph):
    g = fake_graph()
    r, out = run("ade", "profiles", "assign", "--profile", f'"{FULL}"', "C02A", input="")
    assert out == [{"serialNumber": "C02A", "profile": GUID, "status": "dry-run"}]
    assert not g.request_calls


def test_assign_with_yes_posts_serials_from_stdin(fake_graph):
    g = fake_graph()
    r, out = run(
        "ade",
        "profiles",
        "assign",
        "--yes",
        "--profile",
        FULL,
        input='{"serialNumber":"C02A"}\n{"serialNumber":"C02B"}\n',
    )
    assert [o["status"] for o in out] == ["assigned", "assigned"]
    [(method, url, body)] = g.request_calls
    assert method == "POST" and body == {"deviceIds": ["C02A", "C02B"]}
    assert url == (
        f"/deviceManagement/depOnboardingSettings/{TOK}/enrollmentProfiles/{GUID}"
        "/updateDeviceProfileAssignment"
    )


def _widget_group():
    """A throwaway resource with every verb, to exercise verbs no real spec uses yet."""
    res = Resource(
        path=("widgets",),
        collection="/widgets",
        help="Widgets.",
        read_scopes=("W.Read.All",),
        write_scopes=("W.ReadWrite.All",),
        verbs=frozenset({"list", "get", "create", "update", "delete"}),
        odata_type="#microsoft.graph.widget",
    )
    group = click.Group("widgets")
    for command in build_commands(res):
        group.add_command(command)
    return group


def test_create_dry_run_reads_stdin_bodies_and_adds_type(fake_graph):
    g = fake_graph()
    r = CliRunner().invoke(_widget_group(), ["create"], input='{"displayName":"x"}\n')
    [rec] = [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")]
    assert rec == {
        "index": 0,
        "body": {"@odata.type": "#microsoft.graph.widget", "displayName": "x"},
        "status": "dry-run",
    }
    assert not g.batch_calls


def test_create_with_yes_posts_and_reports_new_id(fake_graph):
    g = fake_graph(batch_status=201, batch_body=lambda n: {"id": "new1"})
    r = CliRunner().invoke(_widget_group(), ["create", "--yes", "--set", "displayName=x"])
    [rec] = [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")]
    assert rec == {"index": 0, "status": "created", "id": "new1"}
    assert g.batch_calls[0][0]["url"] == "/widgets"
    assert g.batch_calls[0][0]["body"]["displayName"] == "x"
    assert g.scopes == ("W.ReadWrite.All",)


def test_create_rejects_non_object_stdin_records():
    r = CliRunner().invoke(_widget_group(), ["create"], input='"just a string"\n')
    assert r.exit_code != 0


def test_help_does_not_import_msal_or_requests():
    code = (
        "import sys, graph_macos.cli.app as a; a.cli.main(['--help'], standalone_mode=False);"
        "assert 'msal' not in sys.modules and 'requests' not in sys.modules"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_readme_command_table_is_current():
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    assert docs.render(readme, docs.command_table(cli)) == readme, (
        "run: uv run python -m graph_macos.cli.docs --write"
    )


def test_search_option_exists_only_where_supported():
    cmds = {p: c for p, c in iter_commands(cli)}
    assert "search" in {p.name for p in cmds[("users", "list")].params}
    assert "search" in {p.name for p in cmds[("groups", "list")].params}
    for path in (("devices", "list"), ("apps", "list"), ("ade", "profiles", "list")):
        assert "search" not in {p.name for p in cmds[path].params}
    for name in ("advanced", "orderby"):  # deliberately not offered
        assert all(name not in {p.name for p in c.params} for c in cmds.values())


def test_users_search_sends_advanced_request(fake_graph):
    g = fake_graph(pages={"/users": [{"id": "u1"}]})
    r, out = run("users", "list", "--search", '"displayName:Ann"')
    assert out == [{"id": "u1"}]
    assert g.paged_kw[0]["headers"] == {"ConsistencyLevel": "eventual"}
    assert g.paged_calls[0][1]["$search"] == '"displayName:Ann"'


def test_unsupported_query_error_points_to_jq(monkeypatch, fake_graph):
    g = fake_graph()

    def boom(url, **kw):
        raise GraphMacosError("400 Operator 'endsWith' ... ConsistencyLevel:eventual")
        yield  # pragma: no cover

    monkeypatch.setattr(g, "paged", boom)
    r, _ = run("users", "list", "--filter", "endsWith(mail,'@x.com')")
    assert r.exit_code == 1 and "filter client-side with jq" in r.stderr
    r, _ = run("users", "list", "--search", '"displayName:a"')
    assert r.exit_code == 1 and "hint" not in r.stderr
