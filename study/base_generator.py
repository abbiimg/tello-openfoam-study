"""Generate OpenFOAM Foundation 14 ideal power-controlled overlapping disks.
Run with Python 3; no external modules required. Units SI.
"""
from pathlib import Path
import argparse, json
p=argparse.ArgumentParser(); p.add_argument('--root',default=str(Path(__file__).parent/'cases')); p.add_argument('--scale',type=float,default=1); p.add_argument('--end',type=float,default=3); a=p.parse_args()
root=Path(a.root)
def header(obj,cls='dictionary'):
 return f'FoamFile {{ format ascii; class {cls}; object {obj}; }}\n'
for n in (4,8):
 c=root/f'rotors{n}';
 for d in ('0','constant','system'): (c/d).mkdir(parents=True,exist_ok=True)
 def write(f,s): (c/f).write_text(header(Path(f).name)+s)
 centers=[(-.25,-.25),(.25,-.25),(.25,.25),(-.25,.25)]
 if n==8: centers += [(0,-.25),(.25,0),(0,.25),(-.25,0)]
 (c/'geometry.json').write_text(json.dumps(dict(centers=centers,radius=.2,thickness=.06,footprint=[.9,.9],power_W=100,density=1.225),indent=2))
 nx=round(64*a.scale); nz=round(80*a.scale)
 write('system/blockMeshDict',f'''convertToMeters 1;
vertices ((-1.8 -1.8 -3) (1.8 -1.8 -3) (1.8 1.8 -3) (-1.8 1.8 -3) (-1.8 -1.8 1.8) (1.8 -1.8 1.8) (1.8 1.8 1.8) (-1.8 1.8 1.8));
blocks (hex (0 1 2 3 4 5 6 7) ({nx} {nx} {nz}) simpleGrading
(((.333333 .1875 .25) (.333334 .625 1) (.333333 .1875 4))
 ((.333333 .1875 .25) (.333334 .625 1) (.333333 .1875 4))
 ((.61875 .475 .15) (.0125 .05 1) (.36875 .475 6))));
edges (); boundary (farfield {{type patch; faces ((0 3 2 1) (4 5 6 7) (0 1 5 4) (1 2 6 5) (2 3 7 6) (3 0 4 7));}});
''')
 # Open pressure boundary permits induced inflow and downward wake outflow.
 (c/'0/U').write_text(header('U','volVectorField')+'''dimensions [0 1 -1 0 0 0 0]; internalField uniform (0 0 0);
boundaryField {farfield {type pressureInletOutletVelocity; value uniform (0 0 0);}}
''')
 (c/'0/p').write_text(header('p','volScalarField')+'''dimensions [0 2 -2 0 0 0 0]; internalField uniform 0;
boundaryField {farfield {type totalPressure; p0 uniform 0; value uniform 0;}}
''')
 write('constant/physicalProperties','viscosityModel constant; nu 1.5e-5;')
 write('constant/momentumTransport','simulationType laminar;')
 write('system/controlDict',f'''application foamRun; solver incompressibleFluid;
startFrom startTime; startTime 0; stopAt endTime; endTime {a.end}; deltaT .001;
writeControl adjustableRunTime; writeInterval .25; writeFormat ascii; writePrecision 9;
writeCompression off; timeFormat general; timePrecision 8; runTimeModifiable true;
adjustTimeStep yes; maxCo .9; maxDeltaT .004;
''')
 write('system/fvSchemes','''ddtSchemes {default Euler;}
gradSchemes {default Gauss linear; grad(U) cellLimited Gauss linear 1;}
divSchemes {default none; div(phi,U) Gauss linearUpwind grad(U); div((nuEff*dev2(T(grad(U))))) Gauss linear;}
laplacianSchemes {default Gauss linear corrected;} interpolationSchemes {default linear;}
snGradSchemes {default corrected;} wallDist {method meshWave;}
''')
 write('system/fvSolution','''solvers {
p {solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol .05;}
pFinal {$p; relTol 0;}
U {solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol .05;}
UFinal {$U; relTol 0;}}
PIMPLE {nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 0;}
''')
 write('system/decomposeParDict','numberOfSubdomains 4; method scotch;')
 cs=','.join('vector(%g,%g,0)'%xy for xy in centers)
 write('constant/fvModels','''rotors { type coded; cellZone all; field U;
codeInclude
#{
#include "PstreamReduceOps.H"
#};
codeAddSup
#{
const fvMesh& m=mesh();
const vectorField& C=m.C(); const scalarField& V=m.V();
const volVectorField& vel=m.lookupObject<volVectorField>("U");
vectorField& S=eqn.source();
const vector ctr[]={'''+cs+'''};
static scalar thrust['''+str(n)+''']={0};
static label last=-1;
const bool update=(last!=m.time().timeIndex());
scalar totalT=0,totalP=0;
for (label r=0;r<'''+str(n)+''';++r) {
 scalar volume=0,flux=0;
 forAll(C,i) {if (sqr(C[i].x()-ctr[r].x())+sqr(C[i].y()-ctr[r].y())<=.04 && mag(C[i].z())<.03) {volume+=V[i]; flux+=-vel[i].z()*V[i];}}
 reduce(volume,sumOp<scalar>()); reduce(flux,sumOp<scalar>());
 scalar w=flux/max(volume,small);
 if(update) {
 scalar target=min(15.0,(100.0/'''+str(n)+''')/max(w,1.0));
 scalar alpha=min(1.0,m.time().deltaTValue()/.15);
 if(last<0 && m.time().value()>.05) thrust[r]=target;
 thrust[r]+=(target-thrust[r])*alpha;
 }
 forAll(C,i) {if (sqr(C[i].x()-ctr[r].x())+sqr(C[i].y()-ctr[r].y())<=.04 && mag(C[i].z())<.03) S[i].z()+=thrust[r]*V[i]/(1.225*max(volume,small));}
 totalT+=thrust[r]; totalP+=thrust[r]*w;
}
if(update) {Info<<"DISK "<<m.time().value()<<" "<<totalT<<" "<<totalP<<endl; last=m.time().timeIndex();}
#};
}
''')
 (c/'Allrun').write_text('#!/bin/bash\nset -e\ncd "$(dirname "$0")"\nfoamDictionary system/controlDict -entry startFrom -set startTime > log.reset 2>&1\nfoamDictionary system/controlDict -entry stopAt -set endTime >> log.reset 2>&1\nblockMesh > log.blockMesh 2>&1\ncheckMesh > log.checkMesh 2>&1\nfoamRun > log.foamRun 2>&1\n')
 (c/'case.foam').touch()
print(root)
