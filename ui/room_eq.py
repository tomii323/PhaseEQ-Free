"""Room-target delta controls with settings-owned data and transient widgets."""
import streamlit as st

from phase_fir_designer.room_eq import load_room_eq, normalize_room_eq, room_eq_bytes
from utils.ui_localization import display_text


def restore_room_eq(state, value=None):
    room = normalize_room_eq(value)
    state["room_eq"] = room
    owner = state.get("_room_eq_upload_generation", 0)
    state.pop(f"room_eq_enabled_widget_{owner}", None)
    state.pop(f"room_eq_operation_widget_{owner}", None)
    state.pop("room_eq_enabled_widget", None)
    state.pop("room_eq_operation_widget", None)
    state.pop("_room_eq_error", None)
    state.pop("_room_eq_builder_preview", None)
    state.pop("_room_eq_builder_error", None)
    state["_room_eq_upload_generation"] = int(state.get("_room_eq_upload_generation", 0))+1


def _upload_changed(key, owner):
    if owner != st.session_state.get("_room_eq_upload_generation", 0):
        return
    uploaded = st.session_state.get(key)
    if uploaded is None:
        return
    try:
        room = load_room_eq(uploaded.getvalue(), uploaded.name)
    except (ValueError, TypeError, UnicodeError, OverflowError) as exc:
        st.session_state["_room_eq_error"] = str(exc)
        return
    restore_room_eq(st.session_state, room)


def _enabled_changed(owner):
    key = f"room_eq_enabled_widget_{owner}"
    if (owner != st.session_state.get("_room_eq_upload_generation", 0)
            or key not in st.session_state):
        return
    room = normalize_room_eq(st.session_state.get("room_eq"))
    room["enabled"] = bool(st.session_state[key])
    st.session_state["room_eq"] = normalize_room_eq(room)


def _operation_changed(owner):
    key = f"room_eq_operation_widget_{owner}"
    if (owner != st.session_state.get("_room_eq_upload_generation", 0)
            or key not in st.session_state):
        return
    room = normalize_room_eq(st.session_state.get("room_eq"))
    room["operation"] = st.session_state[key]
    st.session_state["room_eq"] = normalize_room_eq(room)


def render_room_eq(chart_renderer=None):
    room = normalize_room_eq(st.session_state.get("room_eq"))
    with st.expander(display_text("室内音響補正（ルームEQ）"), expanded=True):
        st.caption(display_text("床・壁などの反射による試聴位置の周波数特性の変化を、主ターゲットとは別の補正カーブで扱います。振幅だけに適用し、位相と時間基準は変更しません。"))
        st.caption(display_text("測定から作る場合は「作成・評価（試用）」→生成結果の読込み→「適用・保存」の順に進みます。既存の補正カーブは「適用・保存」で読み込みます。"))
        # Keep both widget trees mounted; switching tabs needs no server rerun.
        apply_tab, build_tab = st.tabs([
            display_text("適用・保存"), display_text("作成・評価（試用）")])
        with apply_tab:
            _render_room_eq_controls(room)
            with st.expander(display_text("REWで補正カーブを作る"), expanded=False):
                for step in ROOM_EQ_REW_HELP:
                    st.markdown(display_text(step))
        with build_tab:
            from ui.room_eq_builder import render_room_eq_builder
            render_room_eq_builder(restore_room_eq, chart_renderer)


def _render_room_eq_controls(room):
    st.caption(display_text("カーブを読み込み、適用方向と内容を確認してONにします。その後、EQを更新・出力して同じ席で再測定してください。"))
    owner = st.session_state.get('_room_eq_upload_generation', 0)
    key = f"room_eq_upload_{owner}"
    st.file_uploader(display_text("補正カーブを読み込む"), type=["txt", "frd", "csv", "json"],
                     key=key, on_change=_upload_changed, args=(key, owner))
    if st.session_state.get("_room_eq_error"):
        st.error(display_text("読み込めませんでした。現在の補正カーブを保持しています。"))
        st.caption(st.session_state["_room_eq_error"])
    enabled_key = f"room_eq_enabled_widget_{owner}"
    operation_key = f"room_eq_operation_widget_{owner}"
    st.session_state[enabled_key] = room["enabled"]
    st.checkbox(display_text("室内音響補正を適用"), key=enabled_key,
                disabled=room["response"] is None, on_change=_enabled_changed, args=(owner,))
    st.session_state[operation_key] = room["operation"]
    st.selectbox(display_text("補正カーブの適用方向"), ["add", "subtract"],
                 format_func=lambda x: display_text("加算" if x == "add" else "減算"),
                 key=operation_key, on_change=_operation_changed, args=(owner,),
                 disabled=room["response"] is None)
    st.caption(display_text("1mの基準を設計入力にする場合、基準−試聴位置の補正カーブは加算、試聴位置−基準の変化量は減算します。距離による音量差を除いて比較してください。"))
    st.caption(display_text("試聴位置の測定を設計入力にも使う場合は、同じルーム補正を重ねないでください。"))
    if room["response"] is not None:
        st.caption(room["name"])
        st.caption(display_text("周波数・dBの列を使用します。入力範囲外は0 dB差分とし、位相列は使用しません。"))
        st.download_button(display_text("補正カーブを保存"), data=room_eq_bytes(room),
                           file_name="room_eq.json", mime="application/json",
                           key="room_eq_download", on_click="ignore")
        st.button(display_text("補正カーブを解除"), key="room_eq_clear",
                  on_click=restore_room_eq, args=(st.session_state,))


ROOM_EQ_REW_HELP = (
    "1. クロスオーバー・EQ・時間合わせ後、室内音響補正をOFFにして基準特性を測定します。正面1m、ウーファーとツイーターの中心間の中点を測定軸とし、両ユニットを同時に鳴らします。IRで反射を確認してゲートを設定し、低域は近接測定と合成します。",
    "2. スピーカー側の設定を固定し、3〜6mの各席で着座時の耳の高さにマイクを置いて測定します。試聴位置は床反射を含めるため、基準測定と同じ短いゲートで反射を除去しません。左右のスピーカーは別々に測ります。",
    "3. REWのAll SPLで試聴位置の測定を選び、Align SPL...で信頼できる共通帯域の音量をそろえてからRMS averageで平均します。基準特性と平均特性も同じ帯域でレベルを合わせます。Vector averageによる位置間の位相相殺を避けます。",
    "4. Trace arithmeticでAを基準特性、Bを試聴位置平均としてA / Bを生成します。振幅比のdB値は「基準−試聴位置」で、加算用の補正カーブになります。A − Bは音圧の減算なので使いません。位相を使わない比較では、窓設定済みの両応答を位相列なしのテキストへ出力・再読込してから演算します。",
    "5. 1/6〜1/3オクターブの平滑化を目安に比較し、複数席に共通する傾向を残します。深く狭い谷の持上げは抑え、基準測定が信頼できない帯域は除外します。必要な上限制限と帯域端の0dBへの調整は、書き出した周波数・dBデータを編集して行います。",
    "6. Export measurement as textで補正カーブを出力し、ここで読み込んで「加算」を選びます。適用をONにした後はEQを更新・出力し、同じ席で再測定してON/OFFを比較します。EQフィルター設定のテキストとは別のファイルです。",
    "この手順はREWでカーブを作る場合に使用します。アプリ内で試す場合は「測定から補正カーブを作る（試用）」へ基準と各席のテキストを読み込みます。生成後は各席の予測を確認してから補正欄へ読み込みます。",
)
