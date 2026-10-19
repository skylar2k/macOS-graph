from graph_macos.graph.ids import profile_guid

GUID = "d8d60ec8-5697-407b-975f-62e0e87b39c6"


def test_composite_id_is_shortened():
    assert profile_guid(f"ECV2_52c74ba6-633e-4afd-8413-cebbbe4f4edf_{GUID}") == GUID


def test_bare_guid_unchanged():
    assert profile_guid(GUID) == GUID


def test_token_id_from_composite():
    from graph_macos.graph.ids import token_id_from_profile_id

    tok = "52c74ba6-633e-4afd-8413-cebbbe4f4edf"
    assert token_id_from_profile_id(f"ECV2_{tok}_{GUID}") == tok
    assert token_id_from_profile_id(GUID) is None


def test_quote_id_encodes_path_characters():
    from graph_macos.graph.ids import quote_id

    assert quote_id(GUID) == GUID
    assert quote_id('a/b?c"d') == "a%2Fb%3Fc%22d"
