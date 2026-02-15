from actions._shared import MissingVariablesError, _format_path


def test_format_path_url_encodes_placeholder_values():
    path = _format_path(
        "telephony/config/workspaces/{workspace_id}/numbers",
        {"workspace_id": "Y2lzY29z/L3Vybj=="},
    )

    assert path == "telephony/config/workspaces/Y2lzY29z%2FL3Vybj%3D%3D/numbers"


def test_format_path_raises_for_missing_value():
    try:
        _format_path("workspaces/{workspace_id}", {})
    except MissingVariablesError as exc:
        assert exc.missing_keys == ["workspace_id"]
    else:
        raise AssertionError("MissingVariablesError was expected")
