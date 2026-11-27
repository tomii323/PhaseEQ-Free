"""Multiway measurement orchestration around the existing detailed capture UI."""
from datetime import datetime
from copy import deepcopy
import json
from pathlib import Path

import streamlit as st

from utils.composite_exchange import read_multiway_workspace, _atomic_json
from utils.multiway_measurement_plan import (
    accept_result, capture_binding, create_plan, measurement_widgets,
    structure_signature, validate_capture, validate_plan,
)
from utils.ui_localization import display_text as tr

PLAN = '_multiway_measurement_plan'
BINDING = '_multiway_measurement_capture'


def persist_plan():
    plan = st.session_state.get(PLAN)
    path = st.session_state.get('_multiway_measurement_plan_path')
    if plan and path:
        _atomic_json(Path(path), plan)


def render_multiway_measurement(root, db_path, *, busy=False):
    """Run before the detailed widgets; only explicit preparation projects values."""
    st.session_state['_multiway_measurement_root'] = str(root)
    st.session_state['_multiway_measurement_db'] = str(db_path)
    try:
        workspace = read_multiway_workspace(root)
    except (OSError, ValueError) as exc:
        st.warning(str(exc))
        return
    plan = st.session_state.get(PLAN)
    requested = str(st.query_params.get('measurement', '')) == 'multiway'
    with st.expander(tr('マルチウェイ構成から測定'), expanded=bool(plan) or requested):
        if not workspace or not workspace.get('channels'):
            st.info(tr('先にマルチウェイで構成を設定・保存してください。'))
            return
        requested_scope = str(st.query_params.get('measure_scope', ''))
        if requested_scope and requested_scope != structure_signature(workspace):
            st.warning(tr('起動元の構成と現在の構成が異なります。測定元のマルチウェイから開き直してください。'))
            if plan and st.button(tr('結果を保持して計画を閉じる'), disabled=busy):
                close_plan()
            return
        path = Path(root) / 'measurement_plans' / (structure_signature(workspace) + '.json')
        st.caption(tr('プロジェクト：') + str(workspace.get('system_name', '')))
        if plan is None:
            if path.exists() and st.button(tr('保存した測定計画を再開'), disabled=busy):
                try:
                    restored = json.loads(path.read_text(encoding='utf-8'))
                    validate_plan(restored, workspace)
                    st.session_state[PLAN] = restored
                    st.session_state['measure_ui_mode'] = '詳細・従来の測定'
                    st.session_state['_multiway_measurement_plan_path'] = str(path)
                    st.rerun()
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    st.error(str(exc))
            references, routes = {}, {}
            for group in dict.fromkeys(row['group'] for row in workspace['channels']):
                rows = [r for r in workspace['channels'] if r['group'] == group]
                candidates = [r for r in rows if r['way'] == 'High']
                options = [r['channel_id'] for r in rows]
                references[group] = st.selectbox(tr('基準ウェイ：') + group, options,
                    index=options.index(candidates[0]['channel_id']) if len(candidates) == 1 else None,
                    format_func=lambda value, rows=rows: next(r['name'] for r in rows if r['channel_id'] == value),
                    key='mw_measure_ref_'+group, disabled=busy)
                for row in rows:
                    routes[row['channel_id']] = st.text_input(
                        tr('実出力経路：') + row['name'], key='mw_measure_route_'+row['channel_id'],
                        placeholder=tr('例：DAC Out 3 → 左ウーファー。外部DSPで対象へ切替'), disabled=busy)
            purpose = st.selectbox(tr('測定目的'), ['correction_input', 'verification_only'],
                format_func=lambda p: tr('ユニット特性の取得' if p == 'correction_input' else '調整後の確認'),
                key='mw_measure_purpose', disabled=busy)
            directory = st.text_input(tr('FRD保存フォルダー（既存のフォルダー）'),
                                      value=str(Path(db_path).parent), key='mw_measure_directory', disabled=busy)
            prefix = st.text_input(tr('ファイル名の先頭文字列'), value='measurement',
                                   key='mw_measure_prefix', disabled=busy)
            response_kind = st.selectbox(tr('保存する応答'), ['gated', 'ungated'],
                format_func=lambda value: tr('ゲートあり（スピーカー基準）' if value == 'gated' else '反射を含む応答'),
                key='mw_measure_response_kind', disabled=busy)
            st.info(tr('基準マーカーと対象ESSは別経路で再生します。実出力との接続を確認してください。共有SUBなど共通基準を確保できない対象は、この連続測定では開始しないでください。'))
            if st.button(tr('この構成で測定計画を作成'), disabled=busy):
                try:
                    from utils.measurement_points import PointCapture
                    PointCapture(Path(directory), prefix, '基準測定', 1., response_kind).validate()
                    created = create_plan(workspace, references, routes, purpose=purpose)
                    created.update(directory=directory, prefix=prefix, response_kind=response_kind)
                    st.session_state[PLAN] = created
                    st.session_state['measure_ui_mode'] = '詳細・従来の測定'
                    st.session_state['_multiway_measurement_plan_path'] = str(path)
                    persist_plan()
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
            return
        try:
            validate_plan(plan, workspace)
        except ValueError as exc:
            st.error(str(exc))
            if st.button(tr('結果を保持して計画を閉じる'), disabled=busy):
                close_plan()
            return
        steps = plan['steps']
        notice = st.session_state.get('_multiway_measurement_notice', {})
        if notice.get('plan_id') == plan['id']:
            st.success(tr(notice['message']))
        if st.button(tr('受信状態を更新'), disabled=busy):
            st.rerun()
        from utils.multiway_measurements import read_measurement_inputs
        try:
            inputs = read_measurement_inputs(root, workspace)
        except (OSError, ValueError) as exc:
            st.error(str(exc))
            if st.button(tr('結果を保持して計画を閉じる'), disabled=busy):
                close_plan()
            return
        def assignment_status(step):
            item = inputs.get(step['channel_id'], {})
            if not step['measurement_id'] or item.get('measurement_id') != step['measurement_id']:
                return tr('未割当')
            receipt = Path(root) / 'measurement_inputs' / 'received' / (item['request_id'] + '.json')
            return tr('受信済み' if receipt.exists() else '送信済み')
        st.dataframe([{tr('対象'): f"{s['group']} / {s['name']} ({s['way']})",
            tr('状態'): tr('保存済み' if s['measurement_id'] else '未測定'), tr('実出力'): s['route'],
            tr('時間差 [ms]'): (f"{s['relative_arrival_ms']:+.3f}" if s.get('relative_arrival_ms') is not None else '—'),
            tr('割当状態'): assignment_status(s)} for s in steps], hide_index=True)
        index = st.selectbox(tr('今回の測定対象'), range(len(steps)), index=plan['current'],
            format_func=lambda i: f"{steps[i]['group']} / {steps[i]['name']}",
            key='mw_measure_step_'+plan['id'], disabled=busy)
        step = steps[index]
        reference = next(s for s in steps if s['channel_id'] == step['reference_id'])
        st.write(tr('時間基準：') + reference['name'])
        st.info(tr('同じ側の測定中はマイクを固定します。左右を切り替えるときは、測定軸・距離・高さ・向きを揃えてください。2ウェイの基準例はウーファーとツイーターの中心、前方1 mです。'))
        st.caption(tr('ゲート時間は下の詳細設定で指定します。校正・入力ゲイン・出力経路・保護条件の確認は各開始前に必要です。'))
        position = st.checkbox(tr('今回のマイク位置と実出力経路を確認した'),
            key='mw_measure_position_'+plan['id']+'_'+str(index), disabled=busy)
        if st.button(tr('今回の測定を準備'), type='primary', disabled=busy or not position):
            try:
                values = measurement_widgets(plan, index)
                plan['current'] = index
                st.session_state.update(values)
                st.session_state['_multiway_measurement_armed'] = True
                st.session_state.pop(BINDING, None)
                st.session_state['measure_ui_mode'] = '詳細・従来の測定'
                # Never carry route/protection/bypass confirmations into another capture.
                for key in ('ess_measure_confirm_external_routing', 'ess_measure_confirm_reference_protection',
                            'ess_measure_confirm_alignment_bypass'):
                    st.session_state[key] = False
                persist_plan()
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if step['measurement_id'] and index + 1 < len(steps):
            st.button(tr('次のウェイへ') if steps[index+1]['group'] == step['group'] else tr('次の側の測定へ'),
                      disabled=busy, on_click=advance_plan, args=(index + 1,))
        if all(s['measurement_id'] for s in steps):
            st.success(tr('全ウェイを保存しました。左右の時間基準は独立しています。'))
            st.caption(tr('対象を選んで割り当てます。調整後の確認測定は入力応答へ割り当てません。'))
        selected_record = step['measurement_id']
        if st.session_state.get(BINDING, {}).get('record_id') and not st.session_state[BINDING].get('saved'):
            st.warning(tr('取得済み原本があります。下の保存ボタンで再試行できます。再収録は不要です。'))
            with st.expander(tr('FRD保存先を修正')):
                plan['directory'] = st.text_input(tr('再試行の保存フォルダー'), value=plan['directory'], key='mw_measure_retry_directory')
                plan['prefix'] = st.text_input(tr('再試行の先頭文字列'), value=plan['prefix'], key='mw_measure_retry_prefix')
        if st.button(tr('選択対象の保存結果をマルチウェイへ割り当て'),
                     disabled=busy or not selected_record or plan['purpose'] != 'correction_input'):
            try:
                from utils.multiway_measurements import set_measurement_input
                from utils.speaker_db import get_measurement
                record = get_measurement(db_path, selected_record)
                if record is None:
                    raise ValueError('保存結果が見つかりません。測定ライブラリを確認してください。')
                set_measurement_input(root, workspace, step['channel_id'], record)
                st.session_state['_multiway_measurement_notice'] = dict(plan_id=plan['id'],
                    message='割当送信済みです。マルチウェイ側の受信と再計算を確認してください。')
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if st.button(tr('測定計画を閉じる（保存結果を保持）'), disabled=busy):
            close_plan()


def close_plan():
    st.session_state.pop(PLAN, None)
    st.session_state.pop(BINDING, None)
    st.session_state.pop('_multiway_measurement_armed', None)
    for key in list(st.session_state):
        if key.startswith('mw_measure_position_'):
            st.session_state.pop(key, None)
    st.rerun()


def advance_plan(index):
    plan = st.session_state[PLAN]
    plan['current'] = index
    st.session_state['mw_measure_step_'+plan['id']] = index
    st.session_state.pop('_multiway_measurement_armed', None)
    persist_plan()


def bind_capture(settings):
    if not st.session_state.get('_multiway_measurement_armed'):
        if st.session_state.get(PLAN):
            raise ValueError('測定計画で「今回の測定を準備」を押してください。')
        return
    plan = st.session_state[PLAN]
    requested_scope = str(st.query_params.get('measure_scope', ''))
    if requested_scope and requested_scope != plan['signature']:
        raise ValueError('起動元の構成と測定計画が一致しません。マルチウェイから開き直してください。')
    validate_plan(plan, read_multiway_workspace(Path(st.session_state['_multiway_measurement_root'])))
    validate_capture(plan, settings)
    st.session_state[BINDING] = capture_binding(plan)


def capture_started(snapshot):
    binding = st.session_state.get(BINDING)
    if binding:
        binding['session_id'] = snapshot.session_id


def active_capture(snapshot):
    binding = st.session_state.get(BINDING)
    return bool(binding and binding.get('session_id') == snapshot.session_id)


def result_defaults(snapshot):
    if not active_capture(snapshot):
        return
    plan = st.session_state[PLAN]
    step = plan['steps'][st.session_state[BINDING]['index']]
    st.session_state.setdefault('ess_db_name_'+snapshot.session_id,
        f"{step['group']}_{step['name']}_{datetime.now():%Y%m%d_%H%M%S}")
    st.session_state.setdefault('ess_db_channel_'+snapshot.session_id,
        {'Left': 'Left', 'Right': 'Right'}.get(step['group'], 'Mono'))
    st.session_state.setdefault('ess_db_use_'+snapshot.session_id, plan['purpose'])
    st.session_state.setdefault('ess_db_system_'+snapshot.session_id,
                                plan['workspace'].get('system_name', ''))


def result_saved(snapshot, record):
    if not active_capture(snapshot):
        return
    if record is None or snapshot.error_message:
        raise ValueError('保存原本または収録状態を確認してください。')
    plan = deepcopy(st.session_state[PLAN])
    accept_result(plan, st.session_state[BINDING], record)
    from utils.measurement_points import PointCapture, point_frd_bytes
    from utils.measurement_originals import load_measurement_original
    # Use the same attached calibration as the regular exports; never export a
    # phase-zeroed/plot-only response or recapture audio on a filesystem error.
    spec = PointCapture(Path(plan['directory']), plan['prefix'], record.name,
                        snapshot.settings.measurement_distance_m, plan['response_kind'],
                        snapshot.settings.gate_start_ms, snapshot.settings.gate_end_ms)
    completed_at = datetime.fromisoformat(snapshot.stopped_at).astimezone()
    path = spec.result_path(completed_at)
    original = load_measurement_original(
        Path(st.session_state['_multiway_measurement_db']), record.id)
    data = point_frd_bytes(original, spec, name=record.name)
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError('同名FRDがあります。別の保存先または先頭文字列を指定してください。原本は保持しています。')
    else:
        with path.open('xb') as stream:
            stream.write(data)
    plan['steps'][st.session_state[BINDING]['index']]['frd_path'] = str(path)
    st.session_state[PLAN] = plan
    persist_plan()
    st.session_state['_multiway_measurement_armed'] = False
    st.session_state[BINDING]['saved'] = True
    st.session_state['_multiway_measurement_notice'] = dict(plan_id=plan['id'],
        message='測定計画へ保存しました。外部再生を停止し、上の一覧で次のウェイを選んでください。')
    st.success(tr('測定計画へ保存しました。外部再生を停止し、上の一覧で次のウェイを選んでください。'))
