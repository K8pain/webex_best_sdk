from SpaceOdT.config import DEFAULT_CONFIG, ENABLED_MODULES, FeatureToggles, SchemaVersions


def test_enabled_modules_contract_is_fixed():
    assert ENABLED_MODULES == ("spaces", "messages", "memberships", "attachments")


def test_default_config_contract_shape():
    data = DEFAULT_CONFIG.as_dict()
    assert data == {
        "contract_version": 1,
        "enabled_modules": ["spaces", "messages", "memberships", "attachments"],
        "toggles": {
            "group_members": True,
            "report_enabled": True,
            "cache_enabled": True,
        },
        "schema_versions": {
            "export": 1,
            "cache": 1,
        },
    }


def test_toggle_and_schema_serialization_helpers():
    toggles = FeatureToggles(group_members=False, report_enabled=True, cache_enabled=False)
    versions = SchemaVersions(export=2, cache=3)

    assert toggles.as_dict() == {
        "group_members": False,
        "report_enabled": True,
        "cache_enabled": False,
    }
    assert versions.as_dict() == {
        "export": 2,
        "cache": 3,
    }
