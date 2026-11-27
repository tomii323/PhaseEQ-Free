"""Measurement planning; no UI, acquisition or implicit hardware routing."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import uuid


def structure_signature(workspace):
    value = {key: workspace.get(key) for key in
             ('system_id', 'sample_rate_hz', 'channel_ids', 'channels')}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def create_plan(workspace, references, routes, *, purpose='correction_input'):
    rows = workspace.get('channels', [])
    if not workspace.get('system_id') or not rows:
        raise ValueError('マルチウェイ構成を保存してから測定を開始してください。')
    if purpose not in {'correction_input', 'verification_only'}:
        raise ValueError('測定目的が不正です。')
    ids = [row['channel_id'] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(workspace['channel_ids']):
        raise ValueError('測定対象と構成のチャンネルが一致しません。')
    groups = list(dict.fromkeys(row['group'] for row in rows))
    groups.sort(key=lambda g: (0 if g == 'Left' else 1 if g == 'Right' else 2))
    steps = []
    for group in groups:
        members = [row for row in rows if row['group'] == group]
        reference = references.get(group)
        if reference not in {row['channel_id'] for row in members}:
            raise ValueError(f'{group}の基準ウェイを選択してください。')
        session = uuid.uuid4().hex
        for row in sorted(members, key=lambda r: r['channel_id'] != reference):
            route = str(routes.get(row['channel_id'], '')).strip()
            if not route:
                raise ValueError(f"{row['name']}の実出力経路を入力してください。")
            steps.append({**deepcopy(row), 'reference_id': reference,
                          'timing_session_id': session, 'route': route,
                          'measurement_id': ''})
    return dict(version=1, id=uuid.uuid4().hex, workspace=deepcopy(workspace),
                signature=structure_signature(workspace), steps=steps,
                purpose=purpose, current=0)


def validate_plan(plan, workspace):
    if (not isinstance(plan, dict) or plan.get('version') != 1
            or not isinstance(plan.get('steps'), list) or not plan['steps']
            or not isinstance(plan.get('current'), int)
            or not 0 <= plan['current'] < len(plan['steps'])):
        raise ValueError('測定計画の形式が不正です。原本を保持して計画を作り直してください。')
    if not workspace or plan['signature'] != structure_signature(workspace):
        raise ValueError('構成が変わりました。取得済み結果を保持しています。測定計画を作り直してください。')
    ids = set(workspace['channel_ids'])
    if (len(plan['steps']) != len(ids)
            or {s.get('channel_id') for s in plan['steps']} != ids
            or any(s.get('reference_id') not in ids for s in plan['steps'])):
        raise ValueError('測定計画の対象チャンネルが一致しません。')


def reference_record_id(plan, step):
    return next(row['measurement_id'] for row in plan['steps']
                if row['channel_id'] == step['reference_id'])


def measurement_widgets(plan, index):
    step = plan['steps'][index]
    reference = step['channel_id'] == step['reference_id']
    record_id = reference_record_id(plan, step)
    if not reference and not record_id:
        raise ValueError('先に同じ側の基準ツイーターを測定・保存してください。')
    return {
        'ess_measure_reference_mode': 'Tweeter reference — external ESS',
        'ess_measure_timing_role': 'Reference Tweeter' if reference else 'Target Speaker',
        'ess_measure_timing_session_id': step['timing_session_id'],
        'ess_measure_reference_tweeter_channel': step['reference_id'],
        'ess_measure_reference_measurement_id': '' if reference else record_id,
    }


def result_identity(plan, index):
    """Project the frozen target; editable legacy fields never own its identity."""
    step = plan['steps'][index]
    return dict(measurement_scope='system_channel',
                system_name=plan['workspace'].get('system_name', ''),
                channel={'Left': 'Left', 'Right': 'Right'}.get(step['group'], 'Mono'),
                intended_use=plan['purpose'])


def validate_capture(plan, settings):
    step = plan['steps'][plan['current']]
    expected = 'reference_tweeter' if step['channel_id'] == step['reference_id'] else 'target_speaker'
    if (settings.timing_reference_kind != 'phaseeq_tweeter_reference'
            or settings.timing_reference_session_id != step['timing_session_id']
            or settings.reference_tweeter_channel_id != step['reference_id']
            or settings.timing_reference_role != expected
            or (expected == 'target_speaker' and
                settings.reference_measurement_id != reference_record_id(plan, step))):
        raise ValueError('測定計画と時間基準が一致しません。「今回の測定を準備」を押して設定を確認してください。')


def accept_result(plan, capture, record):
    """Bind only a frozen capture; replacing a reference invalidates dependants."""
    from utils.measurement_payloads import timing_provenance_from_measurement_payload
    from timing_provenance import normalize_timing_provenance
    if capture['plan_id'] != plan['id'] or capture['signature'] != plan['signature']:
        raise ValueError('別の測定計画の結果です。原本を測定ライブラリで確認してください。')
    step = plan['steps'][capture['index']]
    timing = normalize_timing_provenance(timing_provenance_from_measurement_payload(record.response_payload))
    expected_reference = record.id if step['channel_id'] == step['reference_id'] else reference_record_id(plan, step)
    if (timing is None or not timing.trusted
            or timing.source_measurement_id != record.id
            or timing.timing_reference_session_id != step['timing_session_id']
            or timing.reference_tweeter_channel_id != step['reference_id']
            or timing.reference_measurement_id != expected_reference):
        raise ValueError('時間基準が成立していません。測定原本は保持しました。条件を確認して測り直してください。')
    if step['channel_id'] == step['reference_id']:
        for row in plan['steps']:
            if row['reference_id'] == step['reference_id']:
                row['measurement_id'] = ''
    step['measurement_id'] = record.id
    step['relative_arrival_ms'] = timing.relative_arrival_ms


def capture_binding(plan):
    return dict(plan_id=plan['id'], signature=plan['signature'], index=plan['current'])
