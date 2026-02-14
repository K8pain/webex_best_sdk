from __future__ import annotations

from Space_OdT.v21.transformacion.generar_csv_candidatos_desde_artifacts import build_parameter_row


def test_build_parameter_row_outputs_columns_as_parameters(tmp_path):
    exports = tmp_path / 'exports'
    exports.mkdir()
    (exports / 'locations.csv').write_text('location_id,org_id\nloc-1,org-1\n', encoding='utf-8')
    (exports / 'people.csv').write_text('person_id,email,licenses,location_id\nperson-1,a@example.com,lic-1;lic-2,loc-1\n', encoding='utf-8')
    (exports / 'workspaces.csv').write_text('workspace_id,name\nws-1,WS Alpha\n', encoding='utf-8')
    (exports / 'licenses.csv').write_text('license_id\nlic-1\nlic-2\n', encoding='utf-8')
    (exports / 'person_numbers.csv').write_text('id,name\n+34910000001,5301\n', encoding='utf-8')
    (exports / 'person_transfer_numbers.csv').write_text('id\n+34910000002\n', encoding='utf-8')
    (exports / 'location_pstn_connection.csv').write_text('id\nrg-1\n', encoding='utf-8')

    columns, row = build_parameter_row(exports)

    assert columns
    assert 'location_id' in columns
    assert 'phone_numbers' in columns
    assert set(row.keys()) == set(columns)
    assert row['location_id'] == 'loc-1'
    assert row['phone_number'] == '+34910000002'
    assert row['licenses'] == ['lic-1', 'lic-2']


def test_build_parameter_row_uses_empty_like_values_for_unavailable_params(tmp_path):
    exports = tmp_path / 'exports'
    exports.mkdir()
    (exports / 'locations.csv').write_text('location_id,org_id\nloc-1,org-1\n', encoding='utf-8')

    _, row = build_parameter_row(exports)

    assert row['first_name'] is None
    assert row['premise_route_type'] is None
