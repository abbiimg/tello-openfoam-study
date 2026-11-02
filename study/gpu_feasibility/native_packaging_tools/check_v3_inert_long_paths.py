"""Only inert work fixture + read-only source membership; never package."""
import ast, hashlib, json, pathlib, runpy, sys, uuid

proposal = pathlib.Path(r'C:\Users\abbii\Documents\Codex\2026-10-30\referenced-chatgpt-conversation-this-is-an\work\native_compact_refresh_proposal')
hash_file = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pins = {'refresh_compact_native.py': 'ed37cfd7b79417b6dc33395ee560419f51c5317912fbbd3e2bc06fab3175507b',
        'refresh_compact_native_v2.py': '8d715ae0cf688f4397a385a575528ae0ee78b3a066ad88931f0116e3428a24d0'}
for name, expected in pins.items():
    assert hash_file(proposal / name) == expected
source = proposal / 'refresh_compact_native_v3.py'
source_sha = hash_file(source)
ast.parse(source.read_text(encoding='utf-8'))
m = runpy.run_path(str(source), run_name='native_long_path_fixture_only')
m['check_runtime']()
fixture = m['WORK'] / ('inert_path_fixture_' + uuid.uuid4().hex[:12])
m['safe_path'](fixture, root=m['WORK'], missing_leaf=True); fixture.mkdir()
for index in range(3):
    fixture = fixture / ('segment_' + str(index) + '_' + 'x' * 70)
    m['safe_path'](fixture, root=m['WORK'], missing_leaf=True); fixture.mkdir()
file = fixture / 'inert_native_probe.txt'
assert len(str(file)) > 300
m['safe_path'](file, root=m['WORK'], missing_leaf=True)
payload = b'Inert native long-path fixture; no study/archive/case mutation.\n'
with file.open('xb') as stream:
    stream.write(payload)
record = m['file_record'](file)
assert record['sha256'] == hashlib.sha256(payload).hexdigest()
ordinary = pathlib.Path(str(file)[4:])
assert m['lexical'](ordinary) == file
assert m['safe_path'](ordinary, root=m['WORK']) == file
relative = file.relative_to(m['WORK']).as_posix()
assert not relative.startswith(('/', '\\')) and '\\' not in relative and ':' not in relative
# Read paths/membership only. Does NOT call inventory(), protected_snapshot(),
# create_candidate(), backup_old(), main(), or any archive publication code.
selected = m['source_files']()
assert all(not key.startswith(('/', '\\')) and '\\' not in key and ':' not in key for key in selected)
assert all(str(path).startswith('\\\\?\\') for path in selected.values())
assert m['SPUMA_DOTFILE_EXCEPTIONS'] <= set(selected)
for name, expected in pins.items():
    assert hash_file(proposal / name) == expected
assert hash_file(source) == source_sha
result = dict(mode='inert work fixture and read-only source membership only',
              native_python=sys.version, AST_passed=True, runtime_identity_passed=True,
              fixture_path=str(file), fixture_path_characters=len(str(file)), fixture_sha256=record['sha256'],
              ordinary_alias_canonicalized_to_same_bounded_extended_path=True,
              relative_inventory_names_are_posix_without_extended_prefix=True,
              source_membership_count=len(selected),
              longest_source_path_characters=max(len(str(p)) for p in selected.values()),
              exact_SPUMA_markers_selected=sorted(m['SPUMA_DOTFILE_EXCEPTIONS']),
              V1_V2_unchanged=True, V3_source_sha256=source_sha,
              archives_opened_or_created=False, study_case_output_written=False,
              backup_created=False, registry_or_profile_changed=False)
print(json.dumps(result, indent=2))
