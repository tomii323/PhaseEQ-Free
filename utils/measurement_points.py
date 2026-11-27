"""Point capture completion and exclusive FRD export, independent of the UI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import io
import math
import os
from pathlib import Path
import re

import numpy as np

from phase_fir_designer.measurement.models import MeasurementState
from phase_fir_designer.measurement.original import calibrated_output
from utils.guided_measurement import completed, save_guided_result
from utils.measurement_originals import load_measurement_original


@dataclass(frozen=True)
class PointCapture:
    directory: Path
    prefix: str
    label: str
    distance_m: float
    response_kind: str
    gate_start_ms: float = -2.0
    gate_end_ms: float = 5.0

    def validate(self):
        directory = self.directory.expanduser().resolve()
        if not directory.is_dir():
            raise ValueError('保存先には既存のフォルダーを選択してください。')
        prefix = self.prefix.strip()
        if (not prefix or len(prefix) > 100 or re.search(r'[<>:"/\\|?*\x00-\x1f]', prefix)
                or prefix.endswith(('.', ' ')) or prefix in {'.', '..'}):
            raise ValueError('先頭文字列は100文字以内とし、パス区切り・予約記号を除いてください。')
        # These device names stay reserved on Windows even with an extension.
        if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', prefix.split('.')[0], re.I):
            raise ValueError('先頭文字列にWindowsの予約名は使用できません。')
        if not self.label.strip() or len(self.label) > 200 or any(ord(c) < 32 for c in self.label):
            raise ValueError('測点名を改行なし・200文字以内で入力してください。')
        if not math.isfinite(self.distance_m) or not .01 <= self.distance_m <= 100:
            raise ValueError('測定距離は0.01〜100mの範囲にしてください。')
        if self.response_kind not in {'gated', 'ungated'}:
            raise ValueError('応答はゲートあり／反射を含む応答から選択してください。')
        if (not all(math.isfinite(x) for x in (self.gate_start_ms, self.gate_end_ms))
                or not -100 <= self.gate_start_ms < self.gate_end_ms <= 1000):
            raise ValueError('ゲート開始・終了の順序と範囲を確認してください。')
        return directory

    def result_path(self, completed_at: datetime):
        directory = self.validate()
        return directory / f'{self.prefix.strip()}_{completed_at:%Y%m%d_%H%M%S}.frd'


def point_ready(snapshot):
    """Wait for the finalizer; manual aborts and recoverable errors never pass."""
    return bool(snapshot.settings.guided_measurement and completed(snapshot)
                and snapshot.state == MeasurementState.STOPPED_WITH_RESULTS
                and snapshot.device_info.get('guide_finalized')
                and not snapshot.error_message)


def point_frd_bytes(original, spec: PointCapture, *, name: str):
    frequency, response, metadata = calibrated_output(original, spec.response_kind)
    low, high = metadata['valid_frequency_range_hz']
    mask = (frequency > 0) & (frequency >= low) & (frequency <= high)
    rows = np.column_stack((frequency[mask],
                            20*np.log10(np.maximum(np.abs(response[mask]), 1e-15)),
                            np.rad2deg(np.unwrap(np.angle(response)))[mask]))
    if len(rows) < 2 or not np.all(np.isfinite(rows)):
        raise ValueError('保存できる有効な周波数応答がありません。')
    output = io.StringIO()
    np.savetxt(output, rows, fmt='%.12g', comments='* ', header=(
        f'{name}\nSession: {original.metadata["session_id"]}\n'
        f'Point: {spec.label}; distance_m: {spec.distance_m:g}; response: {spec.response_kind}\n'
        f'Frequency(Hz) Gain({metadata["gain_unit"]}) Phase(deg); calibrated'))
    return output.getvalue().encode('utf-8')


def save_point(db: Path, snapshot, selection: dict, spec: PointCapture, path: Path):
    """Keep one library ID per capture and never replace an unrelated file.

    The database is durable first. If the file write fails, its one library
    record remains available and the caller retries with the same timestamp.
    """
    if not point_ready(snapshot):
        raise ValueError('品質判定後の統合完了を待ってください。')
    directory = spec.validate()
    if path.parent.resolve() != directory or path.suffix != '.frd':
        raise ValueError('保存先フォルダーとファイル形式が一致しません。')
    # Prepare before touching the database, and include the capture ID for retry identity.
    from phase_fir_designer.measurement.original import original_from_snapshot
    data = point_frd_bytes(original_from_snapshot(snapshot), spec, name=path.stem)
    if path.exists() and path.read_bytes() != data:
        raise FileExistsError('同名ファイルがあります。先頭文字列または保存先を変更してください。')
    frozen_selection = {**selection, 'point_capture': {
        'enabled': True, 'directory': str(directory), 'prefix': spec.prefix, 'label': spec.label,
        'distance_m': spec.distance_m, 'response_kind': spec.response_kind,
        'gate_start_ms': spec.gate_start_ms, 'gate_end_ms': spec.gate_end_ms,
        'file_name': path.name,
    }}
    record = save_guided_result(db, snapshot, frozen_selection, path.stem)
    # Use the library's attached calibration, also used by all other exports.
    original = load_measurement_original(db, record.id)
    data = point_frd_bytes(original, spec, name=path.stem)
    try:
        with path.open('xb') as stream:
            try:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                stream.close()
                path.unlink(missing_ok=True)
                raise
    except FileExistsError:
        if path.read_bytes() != data:
            raise FileExistsError('同名ファイルがあります。先頭文字列または保存先を変更してください。')
    return record
