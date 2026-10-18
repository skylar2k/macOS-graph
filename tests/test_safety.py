import argparse

import pytest

from kd_graph import safety


def parse(*argv):
    p = argparse.ArgumentParser()
    safety.add_args(p)
    return p.parse_args(argv)


def test_dry_run_by_default(capsys):
    assert safety.proceed(parse(), [{"id": "a"}], "delete") is False
    assert capsys.readouterr().out == '{"id":"a","status":"dry-run"}\n'


def test_yes_proceeds_silently(capsys):
    assert safety.proceed(parse("--yes"), [{"id": "a"}], "delete") is True
    assert capsys.readouterr().out == ""


def test_max_items_guard():
    recs = [{"id": str(i)} for i in range(3)]
    with pytest.raises(SystemExit, match="refusing"):
        safety.proceed(parse("--yes", "--max-items", "2"), recs, "delete")
