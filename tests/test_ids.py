import pytest

from graph_macos.errors import GraphMacosError
from graph_macos.graph.ids import quote_id, resolve_token_id

GUID = "d8d60ec8-5697-407b-975f-62e0e87b39c6"
TOK = "52c74ba6-633e-4afd-8413-cebbbe4f4edf"


def test_quote_id_encodes_path_characters():
    assert quote_id(GUID) == GUID
    assert quote_id('a/b?c"d') == "a%2Fb%3Fc%22d"


def test_resolve_token_id():
    assert resolve_token_id(f"ECV2_{TOK}_{GUID}") == TOK
    assert resolve_token_id(GUID, TOK) == TOK
    with pytest.raises(GraphMacosError):
        resolve_token_id(GUID)
    with pytest.raises(GraphMacosError):
        resolve_token_id(f"ECV2_{TOK}_{GUID}", "other")
