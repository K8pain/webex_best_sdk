from pathlib import Path

import pytest

from Space_OdT.v2.io import load_input_records, load_stage_overrides, load_v1_maps


def test_load_input_records_validates_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / 'input_softphones.csv'
    csv_path.write_text('user_email\nuser@example.com\n', encoding='utf-8')

    with pytest.raises(ValueError, match='missing required CSV columns'):
        load_input_records(csv_path)


def test_load_input_records_parses_and_normalizes(tmp_path: Path) -> None:
    csv_path = tmp_path / 'input_softphones.csv'
    csv_path.write_text(
        'user_email,calling_license_id,location_name,extension,phone_number,cf_always_enabled\n'
        'User@Example.com,lic-1,Madrid,1001,34910000000,true\n',
        encoding='utf-8',
    )

    records = load_input_records(csv_path)

    assert len(records) == 1
    assert records[0].user_email == 'user@example.com'
    assert records[0].phone_number == '+34910000000'
    assert records[0].payload['cf_always_enabled'] is True


def test_load_stage_overrides_from_csv(tmp_path: Path) -> None:
    p = tmp_path / 'ovr.csv'
    p.write_text('user_email,cf_always_enabled\nuser@example.com,true\n', encoding='utf-8')

    data = load_stage_overrides(p)

    assert data['user@example.com']['cf_always_enabled'] == 'true'


def test_load_v1_maps_reads_csv_inventory(tmp_path: Path) -> None:
    inv = tmp_path / 'v1_inventory'
    inv.mkdir()
    (inv / 'people.csv').write_text('email,person_id\nu@example.com,p-1\n', encoding='utf-8')
    (inv / 'locations.csv').write_text('name,location_id\nMadrid,l-1\n', encoding='utf-8')
    (inv / 'call_queues.csv').write_text('name,id\nQ1,q-1\n', encoding='utf-8')

    maps = load_v1_maps(inv)

    assert maps['email_to_person_id']['u@example.com'] == 'p-1'
    assert maps['location_name_to_id']['madrid'] == 'l-1'
    assert maps['queue_name_to_id']['q1'] == 'q-1'
