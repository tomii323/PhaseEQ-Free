"""Experimental measured-response builder; explicit generation and acceptance."""
import json

import streamlit as st

from phase_fir_designer.room_eq import room_eq_bytes
from utils.room_eq_builder import builder_signature, build_room_preview, preview_rows, preview_report
from utils.ui_localization import display_text as tr


MODE_LABELS = {'power': '電力平均', 'trimmed_power': 'トリム電力平均（5測点以上）',
               'db': 'dB平均', 'amplitude': '振幅平均'}


def _accept(restore, owner, signature):
    preview = st.session_state.get('_room_eq_builder_preview')
    if (owner != str(st.session_state.get('_room_eq_upload_generation', 0))
            or not preview or preview['signature'] != signature):
        return
    restore(st.session_state, preview['result'].room_eq('generated-room-correction'))


def render_room_eq_builder(restore, chart_renderer):
    with st.expander(tr('測定から補正カーブを作る（試用）'), expanded=True):
        st.caption(tr('1m合成基準と各席の測定を読み込み、平均化・3帯域平滑化・補正制限を試します。室内音響補正（ルームEQ）と対応する再生DSPのルーム補正をOFFにし、クロス・ユニットEQ・レベル・時間合わせは固定して測ります。生成だけでは現在の補正を変更しません。'))
        owner = str(st.session_state.get('_room_eq_upload_generation', 0))
        prefix = 'room_builder_' + owner + '_'
        st.markdown(tr('**1. 測定データを読み込む**'))
        reference = st.file_uploader(tr('1m合成基準の測定'), type=['txt','frd','csv'], key=prefix+'reference')
        seats = st.file_uploader(tr('各席の測定（複数選択）'), type=['txt','frd','csv'],
                                 accept_multiple_files=True, key=prefix+'seats')
        st.caption(tr('Hz・dBの連続範囲を使用し、位相列は使いません。左右は別々に処理します。ゲート・近接合成の信頼帯域を指定してください。'))
        st.markdown(tr('**2. 平均化とレベル合わせを設定する**'))
        mode = st.selectbox(tr('空間平均の方式'), list(MODE_LABELS),
                            format_func=lambda key: tr(MODE_LABELS[key]), key=prefix+'mode')
        if mode == 'trimmed_power':
            st.caption(tr('各周波数で上下各20%（最低各1測点）を除外します。本当の位置差まで除く場合があるため、通常の電力平均とも比較してください。'))
        level_match = st.checkbox(tr('共通帯域で全体レベル差を除く'), value=True, key=prefix+'level')
        columns = st.columns(2)
        level_low = columns[0].number_input(tr('レベル合わせ下限 [Hz]'), 1., 100000., 500., key=prefix+'level_low', disabled=not level_match)
        level_high = columns[1].number_input(tr('レベル合わせ上限 [Hz]'), 1., 100000., 1500., key=prefix+'level_high', disabled=not level_match)
        with st.expander(tr('平滑化の詳細'), expanded=False):
            columns = st.columns(2)
            first = columns[0].number_input(tr('低中域の境界 [Hz]'), 1., 100000., 200., key=prefix+'first')
            second = columns[1].number_input(tr('中高域の境界 [Hz]'), 1., 100000., 2000., key=prefix+'second')
            columns = st.columns(3)
            widths = []
            options = [0., 1/24, 1/12, 1/6, 1/3, .5]
            labels = ['低域の平滑化 [oct FWHM]', '中域の平滑化 [oct FWHM]', '高域の平滑化 [oct FWHM]']
            for i, (label, index) in enumerate(zip(labels, (2,3,4))):
                widths.append(columns[i].selectbox(tr(label), options, index=index,
                    format_func=lambda value: '0' if value == 0 else f'1/{round(1/value)}', key=prefix+f'width{i}'))
        st.markdown(tr('**3. 補正する帯域と上限を設定する**'))
        columns = st.columns(2)
        low = columns[0].number_input(tr('補正下限 [Hz]'), 1., 100000., 300., key=prefix+'low')
        high = columns[1].number_input(tr('補正上限 [Hz]'), 1., 100000., 3000., key=prefix+'high')
        columns = st.columns(3)
        boost = columns[0].number_input(tr('最大ブースト [dB]'), 0., 12., 0., .5, key=prefix+'boost')
        cut = columns[1].number_input(tr('最大カット [dB]'), 0., 24., 6., .5, key=prefix+'cut')
        guard = columns[2].number_input(tr('測定席の悪化上限 [dB]'), 0., 6., 1., .5, key=prefix+'guard')
        st.caption(tr('3帯域は1/3octで滑らかに接続し、補正帯域の端を各1/3octで0dBへ戻します。悪化上限は入力サンプル上の制限で、未測定席や実際のフィルターを保証しません。'))
        settings = dict(correction_band=(low,high), level_band=(level_low,level_high) if level_match else None,
                        average_mode=mode, smoothing='three_band', max_boost_db=boost, max_cut_db=cut,
                        max_seat_worsening_db=guard, boundaries=(first,second), widths=tuple(widths))
        ref_data = (reference.name, reference.getvalue()) if reference is not None else ('',b'')
        seat_data = [(up.name, up.getvalue()) for up in seats]
        signature = builder_signature(owner, ref_data, seat_data, settings)
        preview = st.session_state.get('_room_eq_builder_preview')
        if preview and preview['signature'] != signature:
            st.session_state.pop('_room_eq_builder_preview', None)
            preview = None
        if st.button(tr('補正カーブを生成して確認'), key=prefix+'generate', disabled=reference is None or not seats):
            st.session_state.pop('_room_eq_builder_preview', None)
            try:
                result = build_room_preview(ref_data, seat_data, settings)
                preview = {'signature': signature, 'result': result}
                st.session_state['_room_eq_builder_preview'] = preview
                st.session_state.pop('_room_eq_builder_error', None)
            except (ValueError, TypeError, UnicodeError, OverflowError) as exc:
                preview = None
                st.session_state['_room_eq_builder_error'] = {'signature':signature,'message':str(exc)}
        error = st.session_state.get('_room_eq_builder_error')
        if error and error['signature'] == signature:
            st.error(tr('生成できませんでした。現在の補正カーブは変更していません。'))
            st.caption(error['message'])
        if not preview:
            return
        st.caption(tr('加算用の補正カーブを生成しました。各席の補正前後を比較し、使う場合は「生成カーブを補正欄へ読み込む」を押して「適用・保存」へ進みます。'))
        _render_preview(preview['result'], chart_renderer)
        result = preview['result']
        st.download_button(tr('生成カーブをJSONで保存'), room_eq_bytes(result.room_eq()),
                           'generated-room-correction.json', 'application/json', key=prefix+'download', on_click='ignore')
        st.download_button(tr('生成条件と各席の結果を保存'), json.dumps(preview_report(result),ensure_ascii=False,indent=2),
                           'room-correction-report.json', 'application/json', key=prefix+'report', on_click='ignore')
        st.caption(tr('読込み操作で現在の補正を置き換え、加算・OFFにします。確認後にONにし、EQを更新・出力して再測定してください。'))
        st.button(tr('生成カーブを補正欄へ読み込む'), key=prefix+'accept',
                  on_click=_accept, args=(restore,owner,signature))


def _render_preview(result, chart_renderer):
    st.markdown(tr('生成結果（未適用）'))
    offset = result.metadata['average_to_reference_offset_db']
    mean = result.spatial_average.response.gain_db + offset
    if chart_renderer is not None:
        chart_renderer({'frequency': result.correction.frequency,
                        'Room reference': result.reference_gain_db,
                        'Room spatial average': mean,
                        'Room predicted after correction': mean+result.correction.gain_db},
                       chart_key='room_builder_average_chart', series_roles={
                           'Room reference':'reference', 'Room spatial average':'input',
                           'Room predicted after correction':'result'})
        chart_renderer({'frequency':result.correction.frequency,
                        'Room correction curve':result.correction.gain_db},
                       chart_key='room_builder_correction_chart', series_roles={'Room correction curve':'correction'})
        st.markdown(tr('平均化前の各測定：入力と補正後予測'))
        names = result.spatial_average.metadata['names']
        selected = st.selectbox(tr('比較する測点'), list(range(len(names))),
                                format_func=lambda index: f'{index+1}. {names[index]}',
                                key='room_builder_preview_seat')
        seat_input = result.spatial_average.aligned_gain_db[selected] + offset
        chart_renderer({'frequency':result.correction.frequency,
                        'Room seat input':seat_input,
                        'Room seat predicted output':seat_input+result.correction.gain_db},
                       chart_key='room_builder_seat_chart',
                       series_roles={'Room seat input':'input','Room seat predicted output':'result'})
        st.caption(tr('レベル合わせ後・平均化と平滑化前の各席データへ生成カーブを加算した予測です。元ファイルは変更しません。設計済みIIR/FIRの実現応答や再測定とは区別して確認してください。'))
    rows = [{tr('測点'): row['name'], tr('レベル移動 [dB]'): row['offset_db'],
             tr('補正前RMS [dB]'): row['before_db'], tr('補正後予測RMS [dB]'): row['after_db'],
             tr('最大悪化 [dB]'):row['worsening_db']} for row in preview_rows(result)]
    st.dataframe(rows, hide_index=True)
    st.caption(tr('補正帯域内・log周波数等重みの基準との差を表示します。補正後は入力データからの予測で、実測・聴感の評価ではありません。'))
