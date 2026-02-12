from SpaceOdT.modules.normalizers import (
    CALLING_FIELDS,
    GROUP_MEMBERS_FIELDS,
    GROUPS_FIELDS,
    LICENSES_FIELDS,
    LOCATIONS_FIELDS,
    PEOPLE_FIELDS,
    normalize_calling,
    normalize_group_members,
    normalize_groups,
    normalize_licenses,
    normalize_locations,
    normalize_people,
)


def test_people_contract_and_values():
    rows = normalize_people(
        [
            {
                "id": "p1",
                "emails": ["user@example.com"],
                "displayName": "User One",
                "status": "active",
                "roles": ["role_b", "role_a"],
                "licenses": ["lic2", "lic1"],
                "locationId": "loc1",
            }
        ]
    )

    assert tuple(rows[0].keys()) == PEOPLE_FIELDS
    assert rows == [
        {
            "person_id": "p1",
            "email": "user@example.com",
            "display_name": "User One",
            "status": "active",
            "roles": "role_a,role_b",
            "licenses": "lic1,lic2",
            "location_id": "loc1",
        }
    ]


def test_groups_and_members_contract():
    group_data = [{"id": "g1", "displayName": "Sales", "members": [{"id": "p1"}, "p2"]}]

    groups = normalize_groups(group_data)
    members = normalize_group_members(group_data)

    assert tuple(groups[0].keys()) == GROUPS_FIELDS
    assert groups == [{"group_id": "g1", "name": "Sales"}]

    assert tuple(members[0].keys()) == GROUP_MEMBERS_FIELDS
    assert members == [{"group_id": "g1", "person_id": "p1"}, {"group_id": "g1", "person_id": "p2"}]


def test_locations_licenses_and_calling_contracts():
    locations = normalize_locations(
        [
            {
                "id": "loc1",
                "name": "Madrid HQ",
                "timeZone": "Europe/Madrid",
                "preferredLanguage": "es_ES",
                "address": {
                    "address1": "Calle 1",
                    "city": "Madrid",
                    "state": "Madrid",
                    "country": "ES",
                    "postalCode": "28001",
                },
            }
        ]
    )
    assert tuple(locations[0].keys()) == LOCATIONS_FIELDS

    licenses = normalize_licenses([{"id": "lic1", "sku": "WEBEX_CALLING"}])
    assert tuple(licenses[0].keys()) == LICENSES_FIELDS
    assert licenses[0]["sku_or_name"] == "WEBEX_CALLING"

    calling = normalize_calling(
        [{"id": "x1", "name": "Queue 1", "locationId": "loc1", "phoneNumber": "+341234", "detail": {"b": 2, "a": 1}}]
    )
    assert tuple(calling[0].keys()) == CALLING_FIELDS
    assert calling[0]["raw_keys"] == "a,b"
