"""SOURCE-ONLY input-audit binder; no execution, receipts or source acceptance.

Root must independently audit the OpenFOAM dictionaries and issue the separate
record before any strict run. This reader binds those assertions to unchanged
bytes; it does not implement a second OpenFOAM dictionary parser.
"""
from pathlib import Path
import hashlib,json,re

HERE=Path(__file__).resolve().parent
PROTOCOL='c29-native-five-fixed-steps-strict-pressure-v1'
PROTOCOL_SHA='946e8c2a0e566cbfb5e494af2da1cf94ba3f3102567c8db36135fd1a758de8fd'
THRESHOLDS_SHA='d6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b'
ROLE_DIR={'f14':'foundation14_control','cpu':'native_cpu','gpu':'native_gpu'}
def require(ok,message):
    if not ok:raise ValueError(message)
def regular(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts,'Absolute unescaped path required')
    for q in (p,*p.parents):require(not q.is_symlink(),'Symlink/ancestor rejected: '+str(q))
    require(p.is_file(),'Missing regular file: '+str(p))
    return p
def sha(path):
    h=hashlib.sha256()
    with regular(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def pinned(record):
    require(isinstance(record,dict) and set(record)=={'path','sha256'},'Expected exact path/hash binding')
    p=regular(record['path']);require(sha(p)==record['sha256'],'Audit binding changed: '+str(p));return p
def validate_strict_audit(path,base,roles):
    require(path is not None,'Strict pressure mode requires a separate root-approved input audit')
    spec=HERE/'strict_pressure_protocol.json'
    require(sha(spec)==PROTOCOL_SHA,'Strict protocol proposal changed')
    audit=regular(path);data=json.loads(audit.read_text())
    require(data.get('schema')=='c29-strict-pressure-input-audit-v1','Unknown strict input-audit schema')
    require(data.get('protocol')==PROTOCOL and data.get('protocol_sha256')==PROTOCOL_SHA,'Wrong strict protocol')
    require(data.get('validation_thresholds_sha256')==THRESHOLDS_SHA,'Changed acceptance limits')
    require(data.get('inputs_audited') is True,'Root input audit has not been performed')
    approval_path=pinned(data['root_authorization'])
    approval=json.loads(approval_path.read_text())
    require(approval.get('protocol')==PROTOCOL and approval.get('protocol_sha256')==PROTOCOL_SHA
        and approval.get('decision')=='APPROVED_FOR_UNVALIDATED_FIVE_STEPS',
        'Distinct root authorization is required; permission is not acceptance')
    require(base.resolve()!=Path('/opt/openfoam-workspace/cases/native_c29_validation_20261102'),
        'Strict runs require a NEW fresh root; legacy failed inputs are preserved')
    expected={'p':{'tolerance':1e-7,'relTol':0},'pFinal':{'tolerance':1e-7,'relTol':0},
        'U':{'tolerance':1e-7,'relTol':.05},'UFinal':{'tolerance':1e-7,'relTol':0}}
    records=data['cases'];require(set(roles)<=set(records),'Missing strict case audit')
    for role in roles:
        record=records[role];case=base/ROLE_DIR[role]
        require(record['case']==str(case.resolve()),'Strict audit case/role mismatch')
        require(record['audited_solver_criteria']==expected,'Strict solver criteria were not audited')
        bound=pinned(record['fvSolution'])
        require(bound==case/'system/fvSolution','fvSolution bound to wrong case')
        require(not bound.with_name('fvSolution.gz').exists(),'Compressed fvSolution not supported')
        if role!='f14':
            controls=pinned(record['c29PortControls'])
            require(controls==case/'constant/c29PortControls','Controls bound to wrong case')
            require(not controls.with_name('c29PortControls.gz').exists(),'Compressed controls unsupported')
            text=re.sub(r'/\*.*?\*/|//[^\n]*','',controls.read_text(),flags=re.S)
            require('#' not in text and '$' not in text,'Unhashed controls expansion unsupported')
            ids=re.findall(r'\bprotocol\s+(\S+)\s*;',text)
            require(ids==[PROTOCOL],'Wrong declared native strict protocol')
    return {'path':str(audit),'sha256':sha(audit),'protocol':PROTOCOL,
        'protocol_sha256':PROTOCOL_SHA,'roles_checked':list(roles),
        'root_authorization_sha256':sha(approval_path),
        'meaning':'Binds a separate root dictionary audit to current bytes; external startup/launch/input/loader gates remain mandatory. No runtime acceptance inferred.'}
