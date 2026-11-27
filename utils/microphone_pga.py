"""Internal PGA calibration policy, independent of OS volume and UI."""
from __future__ import annotations

import math


def pga_confirmation_source(profile_id, calibration_gain_db, observed_gain_db, *, confirmed=False):
    """Return provenance or reject; calibration AGain never becomes an observation."""
    if calibration_gain_db is None:
        if profile_id == "umik-2":
            raise ValueError("UMIK-2の校正ファイルにAGainがありません。対応する個体校正ファイルを登録してください。")
        return ""
    if not math.isfinite(calibration_gain_db):
        raise ValueError("校正ファイルのAGainが有限値ではありません。")
    if profile_id == "umik-2":
        if not confirmed:
            raise ValueError("UMIK-2の内部PGAが校正AGainと一致することを確認してください。")
        return "user_confirmed_calibration_gain"
    if (observed_gain_db is None or not math.isfinite(observed_gain_db)
            or abs(calibration_gain_db - observed_gain_db) > .05):
        raise ValueError("校正ファイルの内部Gainと現在の設定が一致しません。")
    return "device_name"
