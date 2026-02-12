from __future__ import annotations

from types import SimpleNamespace

from Space_OdT.modules.v1_manifest import (
    ArtifactSpec,
    ParamSource,
    _iter_kwargs,
    run_artifact,
)


class _FakeError(Exception):
    def __init__(self, code: int):
        super().__init__(f"error {code}")
        self.code = code


def test_iter_kwargs_filters_by_required_field() -> None:
    cache = {
        'people': [
            {'person_id': 'p1', 'location_id': 'l1'},
            {'person_id': 'p2', 'location_id': ''},
            {'person_id': 'p3'},
        ]
    }
    spec = ArtifactSpec(
        module='person_permissions_in',
        method_path='person_settings.permissions_in.read',
        static_kwargs={},
        param_sources=(ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),),
    )

    kwargs = _iter_kwargs(cache, spec)

    assert kwargs == [{'entity_id': 'p1'}]


def test_run_artifact_skips_resterror_4003() -> None:
    calls: list[str] = []

    def read(*, entity_id: str):
        calls.append(entity_id)
        if entity_id == 'bad':
            raise _FakeError(4003)
        return {'id': f'row-{entity_id}', 'name': 'ok'}

    api = SimpleNamespace(
        person_settings=SimpleNamespace(
            permissions_in=SimpleNamespace(read=read),
        )
    )
    spec = ArtifactSpec(
        module='person_permissions_in',
        method_path='person_settings.permissions_in.read',
        static_kwargs={},
        param_sources=(ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),),
    )
    cache = {
        'people': [
            {'person_id': 'good', 'location_id': 'loc'},
            {'person_id': 'bad', 'location_id': 'loc'},
        ]
    }

    result = run_artifact(api, spec, cache)

    assert calls == ['good', 'bad']
    assert result.count == 1
    assert result.rows[0]['id'] == 'row-good'
    assert result.rows[0]['source_method'] == 'person_settings.permissions_in.read'
