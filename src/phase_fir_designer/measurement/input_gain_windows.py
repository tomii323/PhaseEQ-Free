"""Read Windows capture endpoint dB controls using the system COM API only."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as ct
import math
from uuid import UUID

from .input_gain import InputGainSnapshot, _analog_gain_from_name, _device_token, _model_token


class _GUID(ct.Structure):
    _fields_ = [('data1', ct.c_uint32), ('data2', ct.c_uint16), ('data3', ct.c_uint16), ('data4', ct.c_ubyte*8)]

    @classmethod
    def parse(cls, text):
        return cls.from_buffer_copy(UUID(text).bytes_le)


class _PropertyKey(ct.Structure):
    _fields_ = [('fmtid', _GUID), ('pid', ct.c_uint32)]


class _Vector(ct.Structure):
    _fields_ = [('count', ct.c_uint32), ('pointer', ct.c_void_p)]


class _Value(ct.Union):
    _fields_ = [('text', ct.c_wchar_p), ('integer', ct.c_int64), ('vector', _Vector)]


class _PropVariant(ct.Structure):
    _fields_ = [('vt', ct.c_uint16), ('reserved', ct.c_uint16*3), ('value', _Value)]


def _check(result):
    if result < 0:
        raise OSError(f'Windows capture control failed (HRESULT 0x{result & 0xffffffff:08x})')


def _call(pointer, index, argument_types=(), arguments=()):
    table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    function = ct.WINFUNCTYPE(ct.c_int32, ct.c_void_p, *argument_types)(table[index])
    result = function(pointer, *arguments)
    _check(result)


class _Com:
    def __init__(self, library):
        self.library = library
        self.pointers = []

    def pointer(self):
        pointer = ct.c_void_p()
        self.pointers.append(pointer)
        return pointer

    def close(self):
        failure = None
        for pointer in reversed(self.pointers):
            if pointer:
                try:
                    _call(pointer, 2)  # IUnknown::Release
                except OSError as exc:
                    failure = exc
        if failure is not None:
            raise failure

    def name(self, device):
        store = self.pointer()
        _call(device, 4, (ct.c_uint32, ct.POINTER(ct.c_void_p)), (0, ct.byref(store)))
        key = _PropertyKey(_GUID.parse('a45c254e-df1c-4efd-8020-67d146a850e0'), 14)
        value = _PropVariant()
        try:
            _call(store, 5, (ct.POINTER(_PropertyKey), ct.POINTER(_PropVariant)), (ct.byref(key), ct.byref(value)))
            if value.vt != 31 or not value.value.text:  # VT_LPWSTR
                raise ValueError('Windows capture endpoint has no friendly name')
            return value.value.text
        finally:
            self.library.PropVariantClear(ct.byref(value))

    def volume(self, device):
        volume = self.pointer()
        iid = _GUID.parse('5cdf2c82-841e-4546-9722-0cf74078229a')
        _call(device, 3, (ct.POINTER(_GUID), ct.c_uint32, ct.c_void_p, ct.POINTER(ct.c_void_p)),
              (ct.byref(iid), 23, None, ct.byref(volume)))
        return volume


@contextmanager
def _endpoints():
    # Initialize on the calling thread, including the measurement worker.
    library = ct.WinDLL('ole32')
    library.CoInitializeEx.argtypes = [ct.c_void_p, ct.c_uint32]
    library.CoInitializeEx.restype = ct.c_int32
    library.CoUninitialize.argtypes = []
    library.CoUninitialize.restype = None
    library.PropVariantClear.argtypes = [ct.POINTER(_PropVariant)]
    library.PropVariantClear.restype = ct.c_int32
    library.CoCreateInstance.argtypes = [ct.POINTER(_GUID), ct.c_void_p, ct.c_uint32,
                                         ct.POINTER(_GUID), ct.POINTER(ct.c_void_p)]
    library.CoCreateInstance.restype = ct.c_int32
    status = library.CoInitializeEx(None, 0)
    initialized = status in (0, 1)
    if not initialized and status != -2147417850:  # RPC_E_CHANGED_MODE: existing apartment is usable
        _check(status)
    com = _Com(library)
    try:
        enumerator = com.pointer()
        clsid = _GUID.parse('bcde0395-e52f-467c-8e3d-c4579291692e')
        iid = _GUID.parse('a95664d2-9614-4f35-a746-de8db63617e6')
        _check(library.CoCreateInstance(ct.byref(clsid), None, 23, ct.byref(iid), ct.byref(enumerator)))
        collection = com.pointer()
        _call(enumerator, 3, (ct.c_int, ct.c_uint32, ct.POINTER(ct.c_void_p)),
              (1, 1, ct.byref(collection)))  # eCapture, DEVICE_STATE_ACTIVE
        count = ct.c_uint32()
        _call(collection, 3, (ct.POINTER(ct.c_uint32),), (ct.byref(count),))
        devices = []
        for index in range(count.value):
            device = com.pointer()
            _call(collection, 4, (ct.c_uint32, ct.POINTER(ct.c_void_p)), (index, ct.byref(device)))
            devices.append((com.name(device), device))
        yield com, devices
    finally:
        try:
            com.close()
        finally:
            if initialized:
                library.CoUninitialize()


def _matches(wanted, name):
    if _device_token(wanted) == _device_token(name):
        return True
    model = _model_token(wanted)
    return model.startswith('umik') and model == _model_token(name)


def _levels(volume, channels):
    hardware = ct.c_uint32()
    _call(volume, 19, (ct.POINTER(ct.c_uint32),), (ct.byref(hardware),))
    if not hardware.value & 1:  # ENDPOINT_HARDWARE_SUPPORT_VOLUME
        raise ValueError('Windows endpoint exposes only software volume; hardware capture gain cannot be verified')
    muted = ct.c_int32()
    _call(volume, 15, (ct.POINTER(ct.c_int32),), (ct.byref(muted),))
    if muted.value:
        raise ValueError('Windows capture endpoint is muted')
    count = ct.c_uint32()
    _call(volume, 5, (ct.POINTER(ct.c_uint32),), (ct.byref(count),))
    if not 1 <= count.value <= 64 or count.value < channels:
        raise ValueError('Windows capture gain channels are unavailable')
    minimum, maximum, step = ct.c_float(), ct.c_float(), ct.c_float()
    _call(volume, 20, (ct.POINTER(ct.c_float),)*3,
          (ct.byref(minimum), ct.byref(maximum), ct.byref(step)))
    if not all(math.isfinite(v) for v in (minimum.value, maximum.value, step.value)) or minimum.value > maximum.value:
        raise ValueError('Windows capture dB range is invalid')
    gains = []
    for index in range(count.value):
        level = ct.c_float()
        _call(volume, 12, (ct.c_uint32, ct.POINTER(ct.c_float)), (index, ct.byref(level)))
        if not math.isfinite(level.value) or not minimum.value <= level.value <= maximum.value:
            raise ValueError('Windows capture gain is outside its dB range')
        gains.append(float(level.value))
    return tuple(gains), (minimum.value,)*len(gains), (maximum.value,)*len(gains)


def read_windows_input_gain(device_name: str, channels: int = 2) -> InputGainSnapshot:
    with _endpoints() as (com, devices):
        exact = [(name, device) for name, device in devices if _device_token(name) == _device_token(device_name)]
        matches = exact or [(name, device) for name, device in devices if _matches(device_name, name)]
        if len(matches) != 1:
            raise ValueError('Windows capture endpoint was not uniquely identified; select a named microphone and disconnect same-model duplicates')
        name, device = matches[0]
        gains, minima, maxima = _levels(com.volume(device), channels)
        analog = _analog_gain_from_name(name)
        if analog is None:
            analog = _analog_gain_from_name(device_name)
        return InputGainSnapshot(True, device_name=device_name, channel_gain_db=gains,
            channel_min_gain_db=minima, channel_max_gain_db=maxima, analog_gain_db=analog,
            source='Windows EndpointVolume', writable=False)
