from __future__ import annotations

from typing import Any, Iterable

PEOPLE_FIELDS = (
    "person_id",
    "email",
    "display_name",
    "status",
    "roles",
    "licenses",
    "location_id",
)

GROUPS_FIELDS = (
    "group_id",
    "name",
)

GROUP_MEMBERS_FIELDS = (
    "group_id",
    "person_id",
)

LOCATIONS_FIELDS = (
    "location_id",
    "name",
    "time_zone",
    "preferred_language",
    "address1",
    "address2",
    "city",
    "state",
    "country",
    "postal_code",
)

LICENSES_FIELDS = (
    "license_id",
    "sku_or_name",
)

CALLING_FIELDS = (
    "id",
    "name",
    "location_id",
    "extension",
    "phone_number",
    "raw_keys",
)


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _join_csv(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, list):
        cleaned = [str(v).strip() for v in values if v is not None and str(v).strip()]
        return ",".join(sorted(cleaned))
    text = str(values).strip()
    return text


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return str(value)


def _pick(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return ""


def normalize_people(people: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for person in people:
        rows.append(
            {
                "person_id": _string(_pick(person, "id", "personId", "person_id")),
                "email": _string(_first(_pick(person, "email", "emails"))),
                "display_name": _string(_pick(person, "displayName", "display_name", "name")),
                "status": _string(_pick(person, "status")),
                "roles": _join_csv(_pick(person, "roles")),
                "licenses": _join_csv(_pick(person, "licenses")),
                "location_id": _string(_pick(person, "locationId", "location_id")),
            }
        )
    return rows


def normalize_groups(groups: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "group_id": _string(_pick(group, "id", "groupId", "group_id")),
            "name": _string(_pick(group, "displayName", "name")),
        }
        for group in groups
    ]


def normalize_group_members(
    groups: Iterable[dict[str, Any]],
    include_members: bool = True,
) -> list[dict[str, str]]:
    if not include_members:
        return []

    rows: list[dict[str, str]] = []
    for group in groups:
        group_id = _string(_pick(group, "id", "groupId", "group_id"))
        members = group.get("members") or group.get("memberIds") or []

        for member in members:
            if isinstance(member, dict):
                person_id = _string(_pick(member, "id", "personId", "value", "person_id"))
            else:
                person_id = _string(member)
            if person_id:
                rows.append({"group_id": group_id, "person_id": person_id})
    return rows


def normalize_locations(locations: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for location in locations:
        address = location.get("address") or {}
        rows.append(
            {
                "location_id": _string(_pick(location, "id", "locationId", "location_id")),
                "name": _string(_pick(location, "name", "displayName")),
                "time_zone": _string(_pick(location, "timeZone", "timezone", "time_zone")),
                "preferred_language": _string(
                    _pick(location, "preferredLanguage", "preferred_language", "language")
                ),
                "address1": _string(_pick(address, "address1", "line1")),
                "address2": _string(_pick(address, "address2", "line2")),
                "city": _string(_pick(address, "city")),
                "state": _string(_pick(address, "state", "region")),
                "country": _string(_pick(address, "country")),
                "postal_code": _string(_pick(address, "postalCode", "zip", "postal_code")),
            }
        )
    return rows


def normalize_licenses(licenses: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for license_item in licenses:
        rows.append(
            {
                "license_id": _string(_pick(license_item, "id", "licenseId", "license_id")),
                "sku_or_name": _string(_pick(license_item, "sku", "name", "displayName", "sku_or_name")),
            }
        )
    return rows


def normalize_calling(
    items: Iterable[dict[str, Any]],
    sample_detail: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        detail = (item.get("detail") if isinstance(item.get("detail"), dict) else None) or {}
        sample = sample_detail if sample_detail is not None else detail
        raw_keys = ",".join(sorted(sample.keys())) if isinstance(sample, dict) else ""

        rows.append(
            {
                "id": _string(_pick(item, "id")),
                "name": _string(_pick(item, "name", "displayName")),
                "location_id": _string(_pick(item, "locationId", "location_id")),
                "extension": _string(
                    _pick(item, "extension")
                    or _pick(item.get("phoneNumber", {}) if isinstance(item.get("phoneNumber"), dict) else {}, "extension")
                    or _pick(detail, "extension")
                ),
                "phone_number": _string(
                    _pick(item, "phoneNumber", "number")
                    if not isinstance(item.get("phoneNumber"), dict)
                    else _pick(item.get("phoneNumber", {}), "number", "external")
                )
                or _string(_pick(detail, "phoneNumber", "number")),
                "raw_keys": raw_keys,
            }
        )
    return rows
