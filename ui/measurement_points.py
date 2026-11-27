"""Guided point setup and completion UI; acquisition remains in the engine."""
from datetime import datetime
from pathlib import Path
import sqlite3

import streamlit as st

from utils.measurement_points import PointCapture, point_ready, save_point
from utils.ui_localization import display_text as tr


PREFIX = 'point_capture_'


def _choose_subdirectory():
    root = Path(st.session_state[PREFIX+'directory']).expanduser().resolve()
    st.session_state[PREFIX+'directory'] = str(root / st.session_state[PREFIX+'child'])


def render_point_setup(config):
    previous = config.get('point_capture', {})
    st.session_state.setdefault(PREFIX+'enabled', previous.get('enabled', False))
    enabled = st.checkbox(tr('測点ごとに自動保存する'), key=PREFIX+'enabled', persist_state='session')
    if not enabled:
        config['point_capture'] = {**previous, 'enabled': False}
        return None
    with st.container(border=True):
        st.caption(tr('品質条件を満たす3回を1件に統合し、収録終了後にFRDと測定ライブラリへ保存します。外部プレーヤーの再生は停止しないため、完了後に止めてからマイクを移動してください。'))
        defaults = dict(directory=str(Path.home()), prefix='measurement', label='', distance_m=1.,
                        gate_start_ms=-2., gate_end_ms=5.)
        for key, value in defaults.items():
            st.session_state.setdefault(PREFIX+key, previous.get(key, value))
        label = st.text_input(tr('測点名（例：基準1m、客席3m中央）'), key=PREFIX+'label', persist_state='session')
        distance = st.number_input(tr('測定距離 [m]'), .01, 100., step=.1, key=PREFIX+'distance_m', persist_state='session')
        directory = st.text_input(tr('保存フォルダー'), key=PREFIX+'directory', persist_state='session')
        st.caption(tr('PhaseEQを実行しているPCのフォルダーです。パスを入力するか、下の一覧で選択します。'))
        with st.expander(tr('フォルダーを選択'), expanded=False):
            try:
                folder = Path(directory).expanduser().resolve()
                children = ['..'] + sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.'))
                if st.session_state.get(PREFIX+'child') not in children:
                    st.session_state.pop(PREFIX+'child', None)
                st.selectbox(tr('移動先フォルダー'), children, key=PREFIX+'child')
                st.button(tr('選択したフォルダーへ移動'), on_click=_choose_subdirectory, key=PREFIX+'choose')
            except OSError as exc:
                st.warning(tr('フォルダーを開けません。保存先のパスを確認してください。'))
                st.caption(str(exc))
        prefix = st.text_input(tr('ファイル名の先頭文字列'), key=PREFIX+'prefix', persist_state='session')
        kinds = {'gated': 'ゲートあり（1m基準）', 'ungated': '反射を含む応答（試聴位置）'}
        # Each placement owns its choice; a seat must not inherit the 1m gate.
        kind_key = PREFIX+'response_'+str(config['position'])
        st.session_state.setdefault(kind_key, previous.get('response_by_position', {}).get(
            config['position'], 'ungated' if config['position'] == '試聴位置' else 'gated'))
        kind = st.selectbox(tr('保存する応答'), list(kinds), format_func=lambda k: tr(kinds[k]),
                            key=kind_key, persist_state='session')
        if kind == 'gated':
            st.caption(tr('IRの最初の反射を確認し、ゲートを設定してください。低域の近接合成は別途行います。'))
            st.number_input(tr('ゲート開始 [ms]'), -100., 999., step=.1, key=PREFIX+'gate_start_ms', persist_state='session')
            st.number_input(tr('ゲート終了 [ms]'), -99., 1000., step=.1, key=PREFIX+'gate_end_ms', persist_state='session')
        spec = PointCapture(Path(directory), prefix, label, distance, kind,
                            st.session_state[PREFIX+'gate_start_ms'], st.session_state[PREFIX+'gate_end_ms'])
        config['point_capture'] = dict(enabled=True, directory=directory, prefix=prefix, label=label,
            distance_m=distance, response_kind=kind, gate_start_ms=spec.gate_start_ms, gate_end_ms=spec.gate_end_ms,
            response_by_position={**previous.get('response_by_position', {}), config['position']: kind})
        st.caption(tr('ファイル名：先頭文字列_YYYYMMDD_HHMMSS.frd（測定終了日時・秒単位）。同名ファイルは上書きしません。'))
        if config['output'] == 'both':
            st.info(tr('測点保存では左または右を選択し、左右スピーカーを別々に測定してください。'))
            return False
        try:
            spec.validate()
        except ValueError as exc:
            st.info(tr(str(exc)))
            return False
        return spec


def auto_save_point(snapshot, db, selection):
    """Called on finalized capture only; retain the same path across retries."""
    options = selection.get('point_capture', {})
    if not options.get('enabled') or not point_ready(snapshot):
        return False
    capture_id = snapshot.session_id
    if st.session_state.get('_guided_saved_id') == 'guided-'+capture_id:
        return True
    spec = PointCapture(Path(options['directory']), options['prefix'], options['label'],
                        options['distance_m'], options['response_kind'],
                        options['gate_start_ms'], options['gate_end_ms'])
    error_key = '_point_save_error_'+capture_id
    if error_key in st.session_state:
        st.error(tr('ファイル保存が完了していません。測定結果を保持しています。'))
        st.caption(tr(st.session_state[error_key]))
        retry_folder = st.text_input(tr('再試行の保存フォルダー'), value=options['directory'], key=PREFIX+'retry_'+capture_id)
        if not st.button(tr('保存を再試行'), key=PREFIX+'retry_button_'+capture_id):
            return False
        options['directory'] = retry_folder
        spec = PointCapture(Path(retry_folder), spec.prefix, spec.label, spec.distance_m,
                            spec.response_kind, spec.gate_start_ms, spec.gate_end_ms)
        st.session_state.pop(error_key, None)
    try:
        time_key = '_point_completed_at_'+capture_id
        if time_key not in st.session_state:
            end = datetime.fromisoformat(snapshot.stopped_at) if snapshot.stopped_at else datetime.now().astimezone()
            st.session_state[time_key] = end.astimezone()
        path = spec.result_path(st.session_state[time_key])
        record = save_point(Path(db), snapshot, selection, spec, path)
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        st.session_state[error_key] = str(exc)
        st.error(tr('ファイル保存が完了していません。測定結果を保持しています。'))
        st.caption(tr(str(exc)))
        return False
    st.session_state['_guided_saved_id'] = record.id
    st.session_state['_guided_saved_record'] = record
    st.session_state['guide_result_name'] = record.name
    st.session_state['_point_last_path'] = str(path)
    for key in list(st.session_state):
        if key.startswith(('_point_completed_at_', '_point_save_error_')) and key != '_point_completed_at_'+capture_id:
            st.session_state.pop(key, None)
    history = st.session_state.setdefault('_point_saved_history', [])
    history.append({'name': record.name, 'point': spec.label, 'path': str(path)})
    del history[:-32]
    return True


def render_point_saved():
    path = st.session_state.get('_point_last_path')
    if path:
        st.success(tr('測点の保存が完了しました。外部プレーヤーを停止してからマイクを移動してください。'))
        st.code(path, language=None)
    with st.expander(tr('今回保存した測点（最新32件）'), expanded=False):
        for row in st.session_state.get('_point_saved_history', []):
            st.text(f"{row['point']} / {row['name']}")
