"""File boundary and preview diagnostics for the experimental Room EQ builder."""
import hashlib
import json

import numpy as np

from phase_fir_designer.speaker import load_speaker_response_text
from phase_fir_designer.response_support import support_for
from room_acoustics import Response, generate_correction


def builder_signature(owner, reference, seats, settings):
    digest = hashlib.sha256(json.dumps([owner, settings], sort_keys=True).encode())
    for name, data in (reference, *seats):
        digest.update(json.dumps([name, len(data)]).encode())
        digest.update(data)
    return digest.hexdigest()


def _response(item):
    name, data = item
    source = load_speaker_response_text(data.decode('utf-8-sig'))
    if len(support_for(source).intervals) != 1:
        raise ValueError('Use a continuous valid measurement range without internal gaps')
    return Response(source.frequency, source.gain_db, name=name)


def build_room_preview(reference, seats, settings):
    if not 1 <= len(seats) <= 32:
        raise ValueError('Use 1 to 32 seat measurements')
    if any(len(data) > 10*1024*1024 for _, data in (reference, *seats)):
        raise ValueError('Each measurement must be 10 MB or less')
    return generate_correction(_response(reference), [_response(item) for item in seats], **settings)


def preview_rows(result):
    frequency = result.correction.frequency
    lower, upper = result.metadata['correction_band']
    mask = (frequency >= lower) & (frequency <= upper)
    error = (result.spatial_average.aligned_gain_db
             + result.metadata['average_to_reference_offset_db'] - result.reference_gain_db)
    after = error + result.correction.gain_db
    rows = []
    for index, name in enumerate(result.spatial_average.metadata['names']):
        rows.append({'name': name,
                     'offset_db': float(result.spatial_average.level_offsets_db[index]
                                        + result.metadata['average_to_reference_offset_db']),
                     'before_db': float(np.sqrt(np.mean(error[index, mask]**2))),
                     'after_db': float(np.sqrt(np.mean(after[index, mask]**2))),
                     'worsening_db': float(np.max(np.abs(after[index, mask])-np.abs(error[index, mask])))})
    return rows


def preview_report(result):
    return {'correction': result.metadata, 'average': result.spatial_average.metadata,
            'seats': preview_rows(result)}
