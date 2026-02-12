import asyncio
from pathlib import Path

from Space_OdT.v2.engine import MissingV2InputsError, V2Runner, parse_stage_decision
from Space_OdT.v2.models import InputRecord, Stage, StageDecision

import pytest


def _record(**payload):
    return InputRecord(
        row_number=2,
        user_email='user@example.com',
        calling_license_id='lic-1',
        location_id='loc-1',
        extension='1001',
        phone_number=None,
        payload=payload,
    )


def test_build_stages_minimal_only_license() -> None:
    stages = V2Runner._build_stages(_record())
    assert stages == [Stage.ASSIGN_CALLING_LICENSE]


def test_build_stages_includes_optional_actions() -> None:
    stages = V2Runner._build_stages(
        _record(
            alternate_numbers='{}',
            cf_always_enabled=True,
            voicemail_enabled=True,
            intercept_enabled=True,
            incoming_permissions_mode='custom',
            call_queue_names='queue 1',
        )
    )
    assert stages == [
        Stage.ASSIGN_CALLING_LICENSE,
        Stage.APPLY_NUMBERS_UPDATE,
        Stage.APPLY_FORWARDING,
        Stage.APPLY_VOICEMAIL,
        Stage.APPLY_CALL_INTERCEPT,
        Stage.APPLY_PERMISSIONS,
        Stage.APPLY_CALL_QUEUE_MEMBERSHIPS,
    ]


def test_parse_stage_decision_yes_no_yesbut() -> None:
    assert parse_stage_decision('yes') == (StageDecision.YES, None)
    assert parse_stage_decision('no') == (StageDecision.NO, None)
    assert parse_stage_decision('yesbut overrides.csv') == (StageDecision.YESBUT, 'overrides.csv')


def test_v2_runner_bootstraps_missing_inputs_and_fails_guided(tmp_path: Path) -> None:
    runner = V2Runner(token='token', out_dir=tmp_path, decision_provider=lambda stage: (StageDecision.NO, None))

    with pytest.raises(MissingV2InputsError, match='Se crearon archivos plantilla requeridos para V2'):
        asyncio.run(runner.run())

    v2_dir = tmp_path / 'v2'
    assert (v2_dir / 'input_softphones.csv').exists()
    assert (v2_dir / 'static_policy.json').exists()
    assert (v2_dir / 'decisions.sample.json').exists()
