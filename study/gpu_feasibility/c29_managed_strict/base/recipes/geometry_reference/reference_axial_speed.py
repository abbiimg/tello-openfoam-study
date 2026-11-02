"""Measure rotor axial speed from a saved pre-predictor U and frozen F14 cache.

This is repeated cache accounting. It contains no thrust/controller law.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import numpy as np

WORK = Path(__file__).resolve().parent
CACHE = Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/f14_geometry_reference_20261102/cache')
EXPECTED = {
    'quadrature.csv': '5d786c48c11b80b1f4d45c989f8873d22314c9ea2118fda3bfbdaf3b44930db1',
    'rotors.csv': '41fe936fc5ad3eb63c3756c808ce9b22c67ed0c5abad17e03c130c0ac3bc75ff',
}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_velocity(path):
    text = Path(path).read_text()
    assert re.search(r'\bformat\s+ascii\s*;', text)
    match = re.search(r'\binternalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(', text)
    assert match and int(match[1]) == 922576
    closing = re.search(r'\)\s*;', text[match.end():])
    assert closing
    values = text[match.end():match.end()+closing.start()].replace('(', ' ').replace(')', ' ')
    array = np.fromstring(values, sep=' ').reshape((-1, 3))
    assert array.shape == (922576, 3) and np.isfinite(array).all()
    return array

def measure(path):
    for name, expected in EXPECTED.items(): assert sha(CACHE/name) == expected
    U = read_velocity(path)
    with (CACHE/'rotors.csv').open() as stream:
        rotors = {int(r['rotor']): r for r in csv.DictReader(stream)}
    terms = {r: [] for r in rotors}
    volume_terms = {r: [] for r in rotors}
    ids = {r: set() for r in rotors}
    with (CACHE/'quadrature.csv').open() as stream:
        for row in csv.DictReader(stream):
            r, i = int(row['rotor']), int(row['cell'])
            fraction, volume = float(row['fraction']), float(row['cell_volume_m3'])
            assert 0 <= i < len(U) and i not in ids[r]
            assert 0 < fraction <= 1 and volume > 0
            ids[r].add(i)
            n = [float(rotors[r][k]) for k in ('nx', 'ny', 'nz')]
            weight_volume = fraction*volume
            axial = -math.fsum(float(U[i, k])*n[k] for k in range(3))
            terms[r].append(axial*weight_volume)
            volume_terms[r].append(weight_volume)
    measurements = []
    for r in sorted(rotors):
        cached_volume = float(rotors[r]['volume_m3'])
        summed_volume = math.fsum(volume_terms[r])
        assert math.isclose(summed_volume, cached_volume, rel_tol=1e-12, abs_tol=1e-14)
        flux = math.fsum(terms[r])
        measurements.append({'rotor': r, 'selected_cells': len(ids[r]), 'cached_volume_m3': cached_volume,
            'summed_weighted_volume_m3': summed_volume, 'axial_flux_m4_per_s': flux,
            'mean_axial_speed_m_per_s': flux/cached_volume})
    return {'kind': 'Full-precision saved-field measurement using frozen repeated C29 geometry cache',
        'velocity_field': str(path), 'velocity_sha256': sha(path), 'numpy_version': np.__version__,
        'cache_hashes': EXPECTED, 'rotors': measurements,
        'reduction': 'Python math.fsum; no controller/thrust reconstruction',
        'meaning': 'Cache accounting, not independent geometry or source validation'}

if __name__ == '__main__':
    source = Path('/opt/openfoam-workspace/cases/native_c29_validation_20261102/foundation14_control/0.6/U')
    assert sha(source) == '40c9eb8310e2398fe348ca9d7523ca8230b2c2698707d5e8ef3a54a49f47d046'
    output = WORK/'first_source_reference.json'
    assert not output.exists()
    report = measure(source)
    report['source_sample_time_s'] = .6001
    report['pre_predictor_field_time_s'] = .6
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'rotors': report['rotors'], 'source_sample_time_s': .6001}, indent=2))
