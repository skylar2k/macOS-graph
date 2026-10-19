import io

import pytest

from graph_macos.cli.utils.pipe import collect_ids, emit, read_ids


def stream(text: str) -> io.StringIO:
    s = io.StringIO(text)
    s.isatty = lambda: False  # type: ignore[method-assign]
    return s


@pytest.mark.parametrize(
    "text",
    [
        '{"id":"a"}\n{"id":"b"}\n',
        '[{"id":"a"},{"id":"b"}]',
        '{\n "id": "a"\n}\n{"id":"b"}',
        "a\nb\n",
    ],
)
def test_read_ids_formats(text):
    assert list(read_ids(stream=stream(text))) == ["a", "b"]


def test_bare_ids_that_look_numeric_or_uuid_like():
    assert list(read_ids(stream=stream("1234abcd-1\nfff-2\n"))) == ["1234abcd-1", "fff-2"]


def test_missing_key_exits():
    with pytest.raises(SystemExit):
        list(read_ids(stream=stream('{"x":1}')))


def test_collect_ids_prefers_cli_and_dedupes():
    assert collect_ids(["b", "a", "b"]) == ["b", "a"]


def test_emit_uses_current_stdout(capsys):
    emit({"a": "æ"})
    assert capsys.readouterr().out == '{"a":"æ"}\n'


def test_quoted_cli_ids_from_jq_without_r_are_unwrapped():
    from graph_macos.cli.utils.pipe import clean_id

    assert collect_ids(['"abc"', ' "def"\n']) == ["abc", "def"]
    assert clean_id("abc") == "abc"
    assert clean_id('"a b"') == "a b"
    assert clean_id('"broken') == '"broken'
