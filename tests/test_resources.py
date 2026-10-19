import pytest

from graph_macos.errors import GraphMacosError
from graph_macos.graph.ids import dep_profile_split_guid, token_id_from_dep_profile_id
from graph_macos.resources import RESOURCES, base, payload
from graph_macos.resources.ade import PROFILES
from graph_macos.resources.base import Parent, Resource
from graph_macos.resources.devices import DEVICES
from tests.fakes import FakeGraph

TOK = "52c74ba6-633e-4afd-8413-cebbbe4f4edf"
GUID = "d8d60ec8-5697-407b-975f-62e0e87b39c6"
FULL = f"ECV2_{TOK}_{GUID}"


def test_registry_is_consistent():
    paths = [r.path for r in RESOURCES]
    assert len(paths) == len(set(paths))
    for r in RESOURCES:  # constructing already validated; spot-check scope hygiene
        assert r.read_scopes and all(s.endswith(".All") for s in r.read_scopes + r.write_scopes)
        assert all(".Read." in s for s in r.read_scopes)


def test_spec_validation():
    with pytest.raises(ValueError, match="write_scopes"):
        Resource(
            path=("x",), collection="/x", help="", read_scopes=("A",), verbs=frozenset({"delete"})
        )
    with pytest.raises(ValueError, match="parent"):
        Resource(path=("x",), collection="/x/{parent}/y", help="", read_scopes=("A",))
    with pytest.raises(ValueError, match="unknown"):
        Resource(
            path=("x",), collection="/x", help="", read_scopes=("A",), verbs=frozenset({"nuke"})
        )


def test_combine_filters():
    assert base.combine_filters(None, None) is None
    assert base.combine_filters("a eq 1", None) == "a eq 1"
    assert base.combine_filters("a eq 1", "b eq 2") == "(a eq 1) and (b eq 2)"


def test_list_applies_defaults_and_options():
    g = FakeGraph(pages={"/deviceManagement/managedDevices": [{"id": "1"}, {"id": "2"}]})
    out = list(base.list_(g, DEVICES, filter="complianceState eq 'compliant'", limit=1))
    assert out == [{"id": "1"}]
    url, params = g.paged_calls[0]
    assert params["$filter"] == "(operatingSystem eq 'macOS') and (complianceState eq 'compliant')"
    assert params["$select"] == DEVICES.default_select and params["$top"] == 1


def test_list_can_drop_default_filter():
    g = FakeGraph()
    list(base.list_(g, DEVICES, default_filter=False))
    assert "$filter" not in g.paged_calls[0][1]


def test_list_subresource_iterates_parents_enriches_and_redacts():
    url = f"/deviceManagement/depOnboardingSettings/{TOK}/enrollmentProfiles"
    g = FakeGraph(pages={url: [{"id": FULL, "adminAccountPassword": "secret", "displayName": "A"}]})
    [rec] = base.list_(g, PROFILES, [TOK])
    assert rec == {"id": FULL, "displayName": "A", "profileId": GUID}


def test_list_subresource_requires_parent():
    with pytest.raises(GraphMacosError, match="token"):
        list(base.list_(FakeGraph(), PROFILES, []))


def test_parent_tag_is_added_when_configured():
    res = Resource(
        path=("c",),
        collection="/p/{parent}/c",
        help="",
        read_scopes=("A",),
        parent=Parent("p", tag="pId"),
    )
    g = FakeGraph(pages={"/p/1/c": [{"id": "x"}]})
    assert list(base.list_(g, res, ["1"])) == [{"id": "x", "pId": "1"}]


def test_item_urls_resolve_embedded_parent_and_encode():
    assert base.item_url(PROFILES, FULL) == (
        f"/deviceManagement/depOnboardingSettings/{TOK}/enrollmentProfiles/{FULL}"
    )
    assert base.item_url(PROFILES, GUID, TOK).endswith(f"/enrollmentProfiles/{GUID}")
    assert base.item_url(DEVICES, "a/b") == "/deviceManagement/managedDevices/a%2Fb"


def test_parent_resolution_errors():
    with pytest.raises(GraphMacosError, match="--token is required"):
        base.item_url(PROFILES, GUID)
    with pytest.raises(GraphMacosError, match="does not match"):
        base.item_url(PROFILES, FULL, "other")


def test_get_strips_context_and_redacts():
    g = FakeGraph(get_result={"@odata.context": "x", "id": FULL, "adminAccountPassword": "s"})
    [rec] = base.get(g, PROFILES, [FULL])
    assert rec == {"id": FULL, "profileId": GUID}


def test_delete_batches_and_reports():
    g = FakeGraph()
    out = list(base.delete(g, DEVICES, ["a", "b"]))
    assert out == [{"id": "a", "status": "deleted"}, {"id": "b", "status": "deleted"}]
    assert [r["method"] for r in g.batch_calls[0]] == ["DELETE", "DELETE"]


def test_delete_failure_carries_graph_message():
    out = list(base.delete(FakeGraph(batch_status=404), DEVICES, ["a"]))
    assert out == [{"id": "a", "status": "failed", "error": "nope"}]


def test_update_sends_patch_with_content_type_and_rejects_id():
    g = FakeGraph(batch_status=200)
    out = list(base.update(g, PROFILES, [FULL], {"description": "x"}))
    assert out == [{"id": FULL, "status": "updated"}]
    req = g.batch_calls[0][0]
    assert req["method"] == "PATCH" and req["body"] == {"description": "x"}
    assert req["headers"] == {"Content-Type": "application/json"}
    with pytest.raises(GraphMacosError, match="cannot be updated"):
        base.update(g, PROFILES, [FULL], {"id": "new"})


def test_create_posts_to_collection_and_returns_new_ids():
    g = FakeGraph(batch_status=201, batch_body=lambda n: {"id": f"new{n}"})
    out = list(base.create(g, DEVICES, [{"a": 1}, {"a": 2}]))
    assert out == [
        {"index": 0, "status": "created", "id": "new0"},
        {"index": 1, "status": "created", "id": "new1"},
    ]
    assert g.batch_calls[0][0]["url"] == "/deviceManagement/managedDevices"


def test_ids_helpers_round_trip():
    assert dep_profile_split_guid(FULL) == GUID
    assert dep_profile_split_guid(GUID) == GUID
    assert token_id_from_dep_profile_id(FULL) == TOK
    assert token_id_from_dep_profile_id(GUID) is None


def test_parse_set_types():
    got = payload.parse_set(["a=true", "b=3", 'c=["x"]', "d=hello", "e=a=b", "f="])
    assert got == {"a": True, "b": 3, "c": ["x"], "d": "hello", "e": "a=b", "f": ""}


def test_build_body_merges_with_set_winning(tmp_path):
    f = tmp_path / "p.json"
    f.write_text('{"a": 1, "b": 1}')
    body = payload.build_body(["b=2"], '{"a": 5, "c": 3}', str(f), odata_type="#t")
    assert body == {"@odata.type": "#t", "a": 5, "b": 2, "c": 3}


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"set_items": ["novalue"]}, {"patch_json": "[1]"}, {"patch_json": "{bad"}],
)
def test_build_body_rejects(kwargs):
    with pytest.raises(GraphMacosError):
        payload.build_body(**kwargs)


class _RequestGraph(FakeGraph):
    """FakeGraph whose request() fails for chunks containing `bad`, like Graph would."""

    def __init__(self, bad=None):
        super().__init__()
        self.bad = bad

    def request(self, method, url, **kw):
        super().request(method, url, **kw)
        if self.bad in kw["json"]["deviceIds"]:
            from graph_macos.graph import GraphError

            raise GraphError(400, "bad serial")


def test_assign_profile_chunks_and_builds_url():
    from graph_macos.resources.ade import assign_profile

    g = _RequestGraph()
    out = list(assign_profile(g, TOK, GUID, ["a", "b", "c"], chunk_size=2))
    assert [c[2]["deviceIds"] for c in g.request_calls] == [["a", "b"], ["c"]]
    assert g.request_calls[0][:2] == (
        "POST",
        f"/deviceManagement/depOnboardingSettings/{TOK}/enrollmentProfiles/{GUID}"
        "/updateDeviceProfileAssignment",
    )
    assert [r["status"] for r in out] == ["assigned"] * 3


def test_assign_profile_failed_chunk_does_not_stop_the_rest():
    from graph_macos.resources.ade import assign_profile

    out = list(assign_profile(_RequestGraph(bad="a"), TOK, GUID, ["a", "b", "c"], chunk_size=2))
    assert [(r["serialNumber"], r["status"]) for r in out] == [
        ("a", "failed"),
        ("b", "failed"),
        ("c", "assigned"),
    ]
    assert "bad serial" in out[0]["error"]


def test_search_sends_header_count_and_expression():
    from graph_macos.resources.directory import USERS

    g = FakeGraph(pages={"/users": [{"id": "1"}]})
    list(base.list_(g, USERS, search='"displayName:Ann"', filter="accountEnabled eq true"))
    _, params = g.paged_calls[0]
    assert params["$search"] == '"displayName:Ann"' and params["$count"] == "true"
    assert params["$filter"] == "accountEnabled eq true"
    assert g.paged_kw[0]["headers"] == {"ConsistencyLevel": "eventual"}


def test_plain_list_stays_plain():
    from graph_macos.resources.directory import USERS

    g = FakeGraph()
    list(base.list_(g, USERS, filter="accountEnabled eq false"))
    assert "$count" not in g.paged_calls[0][1] and "headers" not in g.paged_kw[0]


def test_search_rejected_for_resources_without_support():
    with pytest.raises(GraphMacosError, match="--search"):
        list(base.list_(FakeGraph(), DEVICES, search="x"))
