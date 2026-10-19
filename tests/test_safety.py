import pytest

from graph_macos.cli.utils import safety
from graph_macos.errors import GraphMacosError


def test_dry_run_by_default(capsys):
    assert safety.proceed(False, 50, [{"id": "a"}], "delete") is False
    assert capsys.readouterr().out == '{"id":"a","status":"dry-run"}\n'


def test_yes_proceeds_silently(capsys):
    assert safety.proceed(True, 50, [{"id": "a"}], "delete") is True
    assert capsys.readouterr().out == ""


def test_max_items_guard():
    recs = [{"id": str(i)} for i in range(3)]
    with pytest.raises(GraphMacosError, match="refusing"):
        safety.proceed(True, 2, recs, "delete")
