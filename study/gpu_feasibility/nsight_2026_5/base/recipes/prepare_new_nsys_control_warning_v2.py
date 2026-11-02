"""Source-only warning-coverage correction; never imports/runs control helpers."""
from pathlib import Path
import ast
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
old = HERE / "nsys_2026_5_positive_control_proposal"
new = HERE / "nsys_2026_5_positive_control_proposal_v2"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
original_manifest = json.loads((old / "helper_manifest.json").read_text())
for name, pin in original_manifest["files"].items():
    assert sha(old / name) == pin, (name, "Changed V1")
original_manifest_sha = sha(old / "helper_manifest.json")
if new.exists():
    # copytree's metadata copying is unsupported on this DrvFS mount. Admit only
    # its exact, unmodified V1 scaffold; never resume over an edited proposal.
    assert {p.name for p in new.iterdir()} == {p.name for p in old.iterdir()}
    for p in old.iterdir():
        assert p.is_file() and (new / p.name).read_bytes() == p.read_bytes()
else:
    new.mkdir()
    for p in old.iterdir():
        assert p.is_file()
        with (new / p.name).open("xb") as stream:
            stream.write(p.read_bytes())
audit = new / "audit_control.py"
source = audit.read_text()
needle = " unsupported=[r for r in diagnostics if re.search(r'driver.*not supported|unsupported.*driver',r.get('text',''),re.I)];require(not unsupported,'New profiler still reports unsupported driver')\n"
replacement = """ warning_pattern=r'driver.*not supported|unsupported.*driver';unsupported=[]
 for origin,console_text in [('profile.log',text),('export.log',(e/'export.log').read_text())]:
  for line_number,line in enumerate(console_text.splitlines(),1):
   if re.search(warning_pattern,line,re.I):unsupported.append({'origin':origin,'line':line_number,'text':line})
 for index,row in enumerate(diagnostics):
  if re.search(warning_pattern,row.get('text',''),re.I):unsupported.append({'origin':'DIAGNOSTIC_EVENT','row_index':index,'row':row})
 warning_scan={'pattern':warning_pattern,'origins_scanned':['profile.log','export.log','DIAGNOSTIC_EVENT'],'matches':unsupported}
 require(not unsupported,'New profiler still reports unsupported driver: '+json.dumps(warning_scan))
"""
assert source.count(needle) == 1
source = source.replace(needle, replacement)
needle = "'diagnostic_events':diagnostics,"
assert source.count(needle) == 1
source = source.replace(needle, "'diagnostic_events':diagnostics,'unsupported_driver_warning_scan':warning_scan,")
audit.write_text(source, newline="\n")
readme = new / "README.md"
readme.write_text(readme.read_text() + "\nV2 changes only warning coverage: the identical unsupported-driver expression scans profile.log, export.log and SQLite DIAGNOSTIC_EVENT. A successful gate records all origins scanned; a rejection includes the originating console line or diagnostic row. V1 remains frozen, and the protocol, probe, launch scope, cases and all binary/library identities are unchanged.\n", newline="\n")
changed = []
diff = []
for name in original_manifest["files"]:
    if (old / name).read_bytes() != (new / name).read_bytes():
        changed.append(name)
        diff.extend(difflib.unified_diff((old/name).read_text().splitlines(True), (new/name).read_text().splitlines(True), fromfile="v1/"+name, tofile="v2/"+name))
assert changed == ["README.md", "audit_control.py"], changed
assert sha(old / "protocol.json") == sha(new / "protocol.json")
for p in new.glob("*.py"):
    ast.parse(p.read_text(), filename=str(p))
patch = new / "v2_warning_coverage.diff"
patch.write_text("".join(diff), newline="\n")
manifest = dict(original_manifest)
manifest["schema"] = "new-nsys-native-field-control-helper-freeze-v2"
manifest["files"] = {name: sha(new / name) for name in original_manifest["files"]}
manifest["previous_frozen_manifest_sha256"] = original_manifest_sha
manifest["source_only_correction"] = "Identical unsupported-driver regex also scans profile.log/export.log; origin evidence retained."
manifest["limited_diff_sha256"] = sha(patch)
manifest["generator_sha256"] = sha(Path(__file__))
(new / "helper_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", newline="\n")
for name, pin in original_manifest["files"].items():
    assert sha(old / name) == pin
assert sha(old / "helper_manifest.json") == original_manifest_sha
print(json.dumps({"directory": str(new), "protocol_sha256": sha(new/"protocol.json"), "helper_manifest_sha256": sha(new/"helper_manifest.json"), "diff_sha256": sha(patch), "changed_files": changed, "GPU_or_application_run": False}, indent=2))
