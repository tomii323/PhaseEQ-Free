"""Session-only PGA acknowledgement shared by guided and detailed measurement."""
import hashlib

import streamlit as st

from utils.minidsp_calibration import minidsp_calibration_header
from utils.ui_localization import display_text as tr


def render_pga_confirmation(*, prefix, profile, unit, records, device_name, channel, disabled=False):
    records = tuple(record for record in records if record is not None)
    context = repr((getattr(profile, 'id', ''), getattr(unit, 'id', ''),
                    getattr(unit, 'serial_number', ''), device_name, channel,
                    tuple((r.id, r.raw_text) for r in records)))
    signature = hashlib.sha256(context.encode()).hexdigest()
    context_key, value_key = prefix + '_pga_context', prefix + '_pga_confirmed'
    if st.session_state.get(context_key) != signature:
        st.session_state[context_key] = signature
        st.session_state[value_key] = False
    header = minidsp_calibration_header(records[0].raw_text) if records else None
    if getattr(profile, 'id', '') != 'umik-2' or header is None or header[1] is None or not device_name:
        st.session_state[value_key] = False
        return False
    st.caption(tr('Internal PGA is separate from OS input volume. PhaseEQ cannot read the current UMIK-2 PGA. Check that it matches calibration AGain using the manufacturer tool or a known unchanged calibration setting. If unsure, leave this unchecked. Do not change PGA during capture; stop and repeat setup after any change.'))
    return st.checkbox(tr('UMIK-2 internal PGA matches calibration AGain ({gain:g} dB)').format(gain=header[1]),
                       key=value_key, disabled=disabled)
