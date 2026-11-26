"""Room-target delta controls with settings-owned data and transient widgets."""
import streamlit as st

from phase_fir_designer.room_eq import load_room_eq, normalize_room_eq, room_eq_bytes
from utils.ui_localization import display_text


def restore_room_eq(state, value=None):
    room = normalize_room_eq(value)
    state["room_eq"] = room
    state.pop("room_eq_enabled_widget", None)
    state.pop("room_eq_operation_widget", None)
    state.pop("_room_eq_error", None)
    state["_room_eq_upload_generation"] = int(state.get("_room_eq_upload_generation", 0))+1


def _upload_changed(key):
    uploaded = st.session_state.get(key)
    if uploaded is None:
        return
    try:
        room = load_room_eq(uploaded.getvalue(), uploaded.name)
    except (ValueError, TypeError, UnicodeError, OverflowError) as exc:
        st.session_state["_room_eq_error"] = str(exc)
        return
    restore_room_eq(st.session_state, room)


def _enabled_changed():
    room = normalize_room_eq(st.session_state.get("room_eq"))
    room["enabled"] = bool(st.session_state["room_eq_enabled_widget"])
    st.session_state["room_eq"] = normalize_room_eq(room)


def _operation_changed():
    room = normalize_room_eq(st.session_state.get("room_eq"))
    room["operation"] = st.session_state["room_eq_operation_widget"]
    st.session_state["room_eq"] = normalize_room_eq(room)


def render_room_eq():
    room = normalize_room_eq(st.session_state.get("room_eq"))
    with st.expander(display_text("ルームEQ差分"), expanded=True):
        st.caption(display_text("メインターゲットと別に振幅差分を管理します。位相と時間基準は変更しません。"))
        key = f"room_eq_upload_{st.session_state.get('_room_eq_upload_generation', 0)}"
        st.file_uploader(display_text("ルームEQ差分を読み込む"), type=["txt", "frd", "csv", "json"],
                         key=key, on_change=_upload_changed, args=(key,))
        if st.session_state.get("_room_eq_error"):
            st.error(display_text("読み込めませんでした。現在のルームEQ差分を保持しています。"))
            st.caption(st.session_state["_room_eq_error"])
        st.session_state["room_eq_enabled_widget"] = room["enabled"]
        st.checkbox(display_text("ルームEQ差分を目標へ反映"), key="room_eq_enabled_widget",
                    disabled=room["response"] is None, on_change=_enabled_changed)
        st.session_state["room_eq_operation_widget"] = room["operation"]
        st.selectbox(display_text("目標への適用方法"), ["add", "subtract"],
                     format_func=lambda x: display_text("加算" if x == "add" else "減算"),
                     key="room_eq_operation_widget", on_change=_operation_changed,
                     disabled=room["response"] is None)
        st.caption(display_text("1mの基準を設計入力にする場合、基準−試聴位置の補正カーブは加算、試聴位置−基準の変化量は減算します。距離による音量差を除いて比較してください。"))
        st.caption(display_text("試聴位置の測定を設計入力にも使う場合は、同じルーム補正を重ねないでください。"))
        if room["response"] is not None:
            st.caption(room["name"])
            st.caption(display_text("周波数・dBの列を使用します。入力範囲外は0 dB差分とし、位相列は使用しません。"))
            st.download_button(display_text("ルームEQ差分を保存"), data=room_eq_bytes(room),
                               file_name="room_eq.json", mime="application/json",
                               key="room_eq_download", on_click="ignore")
            st.button(display_text("ルームEQ差分を解除"), key="room_eq_clear",
                      on_click=restore_room_eq, args=(st.session_state,))
