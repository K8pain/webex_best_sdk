from __future__ import annotations

from types import SimpleNamespace

import pytest

from Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from Space_OdT.v21.transformacion.ubicacion_configurar_pstn import configurar_pstn_ubicacion


class _Model:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, **kwargs):
        return dict(self._payload)


def test_configurar_pstn_ubicacion_uses_sdk_calls(monkeypatch):
    calls = []

    class Pstn:
        def read(self, location_id, org_id=None):
            calls.append(('read', location_id, org_id))
            return _Model({'id': 'rg-old'})

        def list(self, location_id, org_id=None):
            calls.append(('list', location_id, org_id))
            return [_Model({'id': 'rg-new'})]

        def configure(self, **kwargs):
            calls.append(('configure', kwargs))

    fake_api = SimpleNamespace(telephony=SimpleNamespace(pstn=Pstn()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_configurar_pstn.create_api', lambda token: fake_api)

    result = configurar_pstn_ubicacion(
        token='tkn',
        location_id='loc1',
        premise_route_type='ROUTE_GROUP',
        premise_route_id='rg-new',
        org_id='org1',
    )

    assert result['status'] == 'success'
    assert any(call[0] == 'configure' for call in calls)


def test_alta_numeraciones_desactivadas_calls_number_add(monkeypatch):
    class NumberApi:
        def __init__(self):
            self.last_kwargs = None

        def add(self, **kwargs):
            self.last_kwargs = kwargs
            return _Model({'errors': []})

    number_api = NumberApi()

    class LocationApi:
        def __init__(self):
            self.number = number_api

        def phone_numbers(self, location_id, org_id=None):
            return [_Model({'phoneNumber': '+34910000000'})]

    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=LocationApi()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas.create_api', lambda token: fake_api)

    result = alta_numeraciones_desactivadas(token='tkn', location_id='loc1', phone_numbers=['+34919999999'])

    assert result['status'] == 'success'
    assert number_api.last_kwargs['location_id'] == 'loc1'
    assert number_api.last_kwargs['phone_numbers'] == ['+34919999999']


def test_actualizar_cabecera_ubicacion_updates_calling_line(monkeypatch):
    class Settings:
        def __init__(self):
            self.calling_line_id = SimpleNamespace(phone_number='+34000000000', name='Sede')

        def model_dump(self, **kwargs):
            return {
                'callingLineId': {
                    'phoneNumber': self.calling_line_id.phone_number,
                    'name': self.calling_line_id.name,
                }
            }

    settings = Settings()

    class LocationApi:
        def details(self, location_id, org_id=None):
            return settings

        def update(self, location_id, settings, org_id=None):
            return 'batch-1'

    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=LocationApi()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera.create_api', lambda token: fake_api)

    result = actualizar_cabecera_ubicacion(
        token='tkn',
        location_id='loc1',
        phone_number='+34918887777',
        calling_line_name='Cabecera Central',
    )

    assert result['status'] == 'success'
    assert settings.calling_line_id.phone_number == '+34918887777'
    assert settings.calling_line_id.name == 'Cabecera Central'


def test_configurar_pstn_rejects_invalid_route_type():
    with pytest.raises(ValueError):
        configurar_pstn_ubicacion(
            token='tkn',
            location_id='loc1',
            premise_route_type='INVALID',
            premise_route_id='rg',
        )
