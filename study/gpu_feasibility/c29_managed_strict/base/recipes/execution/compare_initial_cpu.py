"""Exact parsed initial-field comparison; no threshold relaxation or mutation."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np

WORK = Path(__file__).resolve().parent
BASE = Path('/opt/openfoam-workspace/cases/native_c29_validation_20261102')
NUMBER = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def field_values(path):
    text = Path(path).read_text()
    assert re.search(r'\bformat\s+ascii\s*;', text)
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    result = []
    for match in re.finditer(r'\b(internalField|value)\s+(nonuniform|uniform)\s+', text):
        rest = text[match.end():]
        if match[2] == 'uniform':
            vector = re.match(r'\(\s*('+NUMBER+r')\s+('+NUMBER+r')\s+('+NUMBER+r')\s*\)\s*;', rest)
            if vector:
                array = np.array([[float(vector[i]) for i in range(1, 4)]])
            else:
                scalar = re.match(r'('+NUMBER+r')\s*;', rest)
                assert scalar, path
                array = np.array([[float(scalar[1])]])
        else:
            header = re.match(r'List<(scalar|vector)>\s+(\d+)\s*\(', rest)
            assert header, path
            body = rest[header.end():]
            closing = re.search(r'(?m)^\s*\)\s*;?\s*$', body)
            assert closing, path
            values = np.fromstring(body[:closing.start()].replace('(', ' ').replace(')', ' '), sep=' ')
            components = 3 if header[1] == 'vector' else 1
            assert values.size == int(header[2])*components
            array = values.reshape((-1, components))
        assert np.isfinite(array).all(), path
        result.append((match[1], array))
    assert result and result[0][0] == 'internalField', path
    return result

def compare(reference, candidate):
    left, right = field_values(reference), field_values(candidate)
    assert len(left) == len(right), (reference, candidate)
    blocks = []
    for i, ((left_key, a), (right_key, b)) in enumerate(zip(left, right)):
        assert left_key == right_key and a.shape[1] == b.shape[1]
        count = max(len(a), len(b))
        assert len(a) in (1, count) and len(b) in (1, count)
        a = np.broadcast_to(a, (count, a.shape[1]))
        b = np.broadcast_to(b, (count, b.shape[1]))
        blocks.append({'block_index': i, 'key': left_key, 'values': int(a.size),
            'exactly_equal': bool(np.array_equal(a, b)), 'maximum_absolute_difference': float(np.max(np.abs(a-b)))})
    return {'reference': str(reference), 'reference_sha256': sha(reference),
        'candidate': str(candidate), 'candidate_sha256': sha(candidate),
        'blocks': blocks, 'all_internal_and_boundary_value_blocks_exact': all(b['exactly_equal'] for b in blocks)}

if __name__ == '__main__':
    report = {'kind': 'Exact CPU initialized field gate before any source/timestep', 'fields': {}}
    for field, reference in [('U', BASE/'foundation14_control/0.6/U'),
                             ('P', BASE/'foundation14_control/0.6/p'),
                             ('Phi', BASE/'foundation14_phi_seed/0.6/phi')]:
        report['fields'][field] = compare(reference, BASE/'native_cpu/0.6'/('c29_initial'+field))
    report['startup_gate_passed'] = all(f['all_internal_and_boundary_value_blocks_exact'] for f in report['fields'].values())
    report['next_if_flux_differs'] = 'Use the already preregistered single F14 common-phi fallback; no acceptance by a relaxed epsilon'
    output = WORK/'initial_cpu_computed_phi_comparison.json'
    assert not output.exists()
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
