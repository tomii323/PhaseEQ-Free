"""Read the dB capture control of an explicitly selected ALSA hardware card.

No shell commands, percent-to-dB estimates or mixer writes are used.
"""
from __future__ import annotations

import ctypes as ct
import math
import re

from .input_gain import InputGainSnapshot, _analog_gain_from_name, _model_token


def _library():
    library = ct.CDLL('libasound.so.2')
    pointer = ct.c_void_p
    signatures = {
        'snd_card_get_name': ([ct.c_int, ct.POINTER(ct.c_void_p)], ct.c_int),
        'snd_mixer_open': ([ct.POINTER(pointer), ct.c_int], ct.c_int),
        'snd_mixer_attach': ([pointer, ct.c_char_p], ct.c_int),
        'snd_mixer_selem_register': ([pointer, pointer, pointer], ct.c_int),
        'snd_mixer_load': ([pointer], ct.c_int),
        'snd_mixer_close': ([pointer], ct.c_int),
        'snd_mixer_first_elem': ([pointer], pointer),
        'snd_mixer_elem_next': ([pointer], pointer),
        'snd_mixer_selem_is_active': ([pointer], ct.c_int),
        'snd_mixer_selem_has_capture_volume': ([pointer], ct.c_int),
        'snd_mixer_selem_has_capture_channel': ([pointer, ct.c_int], ct.c_int),
        'snd_mixer_selem_has_capture_switch': ([pointer], ct.c_int),
        'snd_mixer_selem_has_capture_volume_joined': ([pointer], ct.c_int),
        'snd_mixer_selem_get_capture_switch': ([pointer, ct.c_int, ct.POINTER(ct.c_int)], ct.c_int),
        'snd_mixer_selem_get_capture_dB_range': ([pointer, ct.POINTER(ct.c_long), ct.POINTER(ct.c_long)], ct.c_int),
        'snd_mixer_selem_get_capture_dB': ([pointer, ct.c_int, ct.POINTER(ct.c_long)], ct.c_int),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
    return library


def _check(code):
    if code < 0:
        raise OSError(f'ALSA capture control failed ({code})')


def _card_name(library, card):
    name = ct.c_void_p()
    _check(library.snd_card_get_name(card, ct.byref(name)))
    try:
        if not name:
            raise ValueError('ALSA card name is unavailable')
        return ct.string_at(name).decode('utf-8')
    finally:
        free = ct.CDLL(None).free
        free.argtypes, free.restype = [ct.c_void_p], None
        free(name)


def read_alsa_input_gain(device_name: str, channels: int = 2) -> InputGainSnapshot:
    # PortAudio's ALSA hardware names contain (hw:CARD,DEVICE). Aliases can
    # introduce an additional PulseAudio/PipeWire/softvol gain we cannot track.
    match = re.search(r'\bhw:(\d+),\d+\b', device_name)
    if match is None:
        raise ValueError('Select an ALSA hardware input with (hw:CARD,DEVICE); default/PulseAudio/PipeWire aliases are unsupported')
    library = _library()
    wanted = _model_token(device_name)
    if wanted.startswith('umik') and _model_token(_card_name(library, int(match[1]))) != wanted:
        raise ValueError('ALSA card identity changed; refresh and reselect the microphone')
    handle = ct.c_void_p()
    _check(library.snd_mixer_open(ct.byref(handle), 0))
    try:
        _check(library.snd_mixer_attach(handle, f'hw:{match[1]}'.encode()))
        _check(library.snd_mixer_selem_register(handle, None, None))
        _check(library.snd_mixer_load(handle))
        controls = []
        element = library.snd_mixer_first_elem(handle)
        while element:
            if (library.snd_mixer_selem_is_active(element)
                    and library.snd_mixer_selem_has_capture_volume(element)):
                controls.append(element)
            element = library.snd_mixer_elem_next(element)
        if len(controls) != 1:
            raise ValueError('ALSA must expose exactly one active capture-volume control; missing or stacked controls cannot be calibrated')
        element = controls[0]
        minimum, maximum = ct.c_long(), ct.c_long()
        _check(library.snd_mixer_selem_get_capture_dB_range(element, ct.byref(minimum), ct.byref(maximum)))
        gains = []
        for channel in range(32):
            if not library.snd_mixer_selem_has_capture_channel(element, channel):
                continue
            if library.snd_mixer_selem_has_capture_switch(element):
                enabled = ct.c_int()
                _check(library.snd_mixer_selem_get_capture_switch(element, channel, ct.byref(enabled)))
                if not enabled.value:
                    raise ValueError('ALSA capture input is muted')
            value = ct.c_long()
            _check(library.snd_mixer_selem_get_capture_dB(element, channel, ct.byref(value)))
            gain = value.value / 100.
            if not math.isfinite(gain) or not minimum.value / 100. <= gain <= maximum.value / 100.:
                raise ValueError('ALSA capture gain is outside its dB range')
            # ALSA uses -9999999 for the special mute dB value.
            if value.value <= -9999999:
                raise ValueError('ALSA capture gain is at mute')
            gains.append(gain)
        if len(gains) == 1 and library.snd_mixer_selem_has_capture_volume_joined(element):
            gains *= max(1, int(channels))
        if not gains or len(gains) < channels:
            raise ValueError('ALSA capture gain channels are unavailable')
        return InputGainSnapshot(True, device_name=device_name, channel_gain_db=tuple(gains),
            channel_min_gain_db=(minimum.value / 100.,)*len(gains),
            channel_max_gain_db=(maximum.value / 100.,)*len(gains),
            analog_gain_db=_analog_gain_from_name(device_name), source='ALSA', writable=False)
    finally:
        library.snd_mixer_close(handle)
