from graph_macos.cli.assign_enrollment_profile import assign
from graph_macos.graph import GraphError


class FakeGraph:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def request(self, method, url, json):
        self.calls.append((method, url, json["deviceIds"]))
        if self.fail_on and self.fail_on in json["deviceIds"]:
            raise GraphError(400, "bad serial")


def test_chunks_and_url():
    g = FakeGraph()
    out = list(assign(g, "tok", "prof", ["a", "b", "c"], 2))
    assert [c[2] for c in g.calls] == [["a", "b"], ["c"]]
    assert g.calls[0][:2] == (
        "POST",
        "/deviceManagement/depOnboardingSettings/tok/enrollmentProfiles/prof"
        "/updateDeviceProfileAssignment",
    )
    assert [r["status"] for r in out] == ["assigned"] * 3


def test_failed_chunk_does_not_stop_others():
    out = list(assign(FakeGraph(fail_on="a"), "t", "p", ["a", "b", "c"], 2))
    assert [(r["serialNumber"], r["status"]) for r in out] == [
        ("a", "failed"),
        ("b", "failed"),
        ("c", "assigned"),
    ]
    assert "bad serial" in out[0]["error"]


def test_ids_are_url_encoded():
    g = FakeGraph()
    list(assign(g, "t/../x", "p?q", ["a"], 10))
    assert g.calls[0][1] == (
        "/deviceManagement/depOnboardingSettings/t%2F..%2Fx/enrollmentProfiles/p%3Fq"
        "/updateDeviceProfileAssignment"
    )
