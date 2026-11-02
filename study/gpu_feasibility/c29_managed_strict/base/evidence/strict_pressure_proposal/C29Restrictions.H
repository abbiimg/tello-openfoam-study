// SPDX-License-Identifier: GPL-3.0-or-later
// Explicit first validation scope, not a general solver/input adapter.
#ifndef C29Restrictions_H
#define C29Restrictions_H
#include "fvCFD.H"
#include "OSspecific.H"
#include "C29ExperimentAdmission.H"
#include <algorithm>
#include <cctype>
#include <limits>
#include <string>
namespace C29
{
inline void require(const bool ok, const char* reason)
{
    if (!ok) FatalErrorInFunction << reason << Foam::exit(Foam::FatalError);
}
inline bool near(const Foam::scalar a,const Foam::scalar b)
{
    return Foam::mag(a-b) <= 64*std::numeric_limits<Foam::scalar>::epsilon()
        *Foam::max(Foam::scalar(1),Foam::mag(b));
}
inline std::string tokens(const Foam::dictionary& d,const Foam::word& name)
{
    std::string s=d.lookup(name).toString();
    s.erase(std::remove_if(s.begin(),s.end(),[](unsigned char c)
        {return std::isspace(c);}),s.end());
    return s;
}
inline void allEntries(const Foam::dictionary& d,const std::string& expected)
{
    const Foam::wordList keys=d.toc();
    forAll(keys,i) require(tokens(d,keys[i])==expected,
        "Unsupported extra/changed numerical scheme entry");
}
inline void admitExperiment
(
    const Foam::dictionary& controls,const bool initialFieldsOnly,const Foam::Time& runTime
)
{
    using namespace Foam;
    require(!Pstream::parRun(),"Initial experiment is serial only");
    require(controls.getOrDefault<bool>("allowUnvalidatedBackendExperiment",false),
        "Explicit permission for an UNVALIDATED backend experiment is required");
    require(!controls.found("libraryBackendReviewed")
        &&!controls.found("sourceMemoryContractReviewed")
        &&!controls.found("sourceHostHelpersCompletionReviewed"),
        "Remove obsolete proof-like flags; permission is not acceptance");
    if (initialFieldsOnly)
        require(controls.getOrDefault<bool>("allowInitialFieldsOnlyExperiment",false),
            "Initial-field-only experimental permission is required");
    else
        require(controls.getOrDefault<bool>("allowFiveStepSourceExperiment",false),
            "Unvalidated five-step host-source experimental permission is required");
#if C29_USE_CUDA
    require(controls.get<word>("backend")=="gpu","CUDA build requires backend gpu");
#else
    require(controls.get<word>("backend")=="cpu","Non-CUDA build requires backend cpu");
#endif
    readExperimentReceipt(controls,
        initialFieldsOnly?"initial_fields_only":"five_fixed_steps",
        controls.get<word>("backend"),runTime.path());
}
inline void validate
(
    const Foam::fvMesh& mesh,const Foam::Time& runTime,
    const Foam::volVectorField& U,const Foam::volScalarField& p,
    const Foam::surfaceScalarField& phi,const Foam::dimensionedScalar& nu,
    const Foam::dictionary& controls
)
{
    using namespace Foam;
    require(!Pstream::parRun(),"Initial candidate supports serial execution only");
    require(mesh.nCells()==922576,"First protocol requires pinned 922576-cell seed");
    require(!mesh.moving()&&!mesh.topoChanging(),"Static mesh only");
    require(!mesh.foundObject<surfaceVectorField>("Uf"),"Uf unsupported");
    require(nu.dimensions()==dimViscosity&&near(nu.value(),1.5e-5),
        "Only pinned constant nu=1.5e-5 m2/s supported");
    require(U.dimensions()==dimVelocity,"U must have velocity dimensions");
    require(p.dimensions()==dimensionSet(0,2,-2,0,0,0,0),"p must be kinematic");
    require(phi.dimensions()==dimVolume/dimTime,"phi must be volumetric");
    require(!p.needReference(),"Current totalPressure anchored gauge required");
    require(controls.get<word>("protocol")=="c29-native-five-fixed-steps-strict-pressure-v1",
        "Unreviewed protocol");
    require(controls.get<string>("seedArchiveSha256")
        =="89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb",
        "Unrecognized declared seed; verify actual hashes with audit_candidate.py");
    const dictionary& time=runTime.controlDict();
    require(time.get<word>("startFrom")=="startTime","Use explicit startTime");
    require(near(runTime.value(),.6)&&near(time.get<scalar>("startTime"),.6),
        "Start must be pinned .600 s");
    require(near(runTime.deltaTValue(),1e-4)&&near(time.get<scalar>("endTime"),.6005),
        "Only five fixed 1e-4 s steps are supported");
    require(!time.getOrDefault<bool>("adjustTimeStep",false),"Adaptive dt unsupported");
    require(!time.getOrDefault<bool>("runTimeModifiable",false),"Runtime edits unsupported");
    require(!time.found("functions")||time.subDict("functions").toc().empty(),
        "Function objects unsupported in this first protocol");
    require(!time.found("libs")||wordList(time.lookup("libs")).empty(),
        "Extra runtime libraries unsupported; no second source");
    const char* blocked[]={"dynamicMeshDict","MRFProperties","fvOptions","fvConstraints"};
    for (const char* name:blocked)
        require(!isFile(runTime.constant()/name)&&!isFile(runTime.system()/name),
            "Dynamic/MRF/options/constraints input unsupported");
    forAll(U.boundaryField(),patchi)
    {
        require(!U.boundaryField()[patchi].coupled(),"Coupled patches unsupported");
        require(U.boundaryField()[patchi].type()=="pressureInletOutletVelocity"
            &&p.boundaryField()[patchi].type()=="totalPressure",
            "Only pinned farfield velocity/totalPressure boundaries supported");
    }
    const dictionary& solution=mesh.solutionDict();
    require(!solution.found("relaxationFactors"),"No relaxationFactors permitted");
    const dictionary& piso=solution.subDict("PISO");
    require(piso.get<label>("nCorrectors")==2
        &&piso.get<label>("nNonOrthogonalCorrectors")==0,
        "Only 2 PISO correctors and 0 nonorthogonal corrections supported");
    require(piso.getOrDefault<label>("nOuterCorrectors",1)==1
        &&!piso.getOrDefault<bool>("consistent",false)
        &&piso.getOrDefault<bool>("momentumPredictor",true),
        "Only one outer iteration, inconsistent PISO and momentum predictor supported");
    const word names[]={"U","UFinal","p","pFinal"};
    for (label i=0;i<4;++i)
    {
        const dictionary& s=mesh.solverDict(names[i]);
        require(s.get<word>("solver")==word(i<2?"smoothSolver":"GAMG"),
            "Changed linear solver unsupported");
        require(s.get<word>("smoother")==word(i<2?"symGaussSeidel":"GaussSeidel"),
            "Changed smoother unsupported");
        // STRICT-PRESSURE v1: only first p relTol changes; U stays .05.
        const scalar expectedRelTol=(i==0)?scalar(.05):scalar(0);
        require(near(s.get<scalar>("tolerance"),1e-7)
            &&near(s.get<scalar>("relTol"),expectedRelTol),"Changed strict solver criteria");
        if (i>=2) require(s.getOrDefault<bool>("directSolveCoarsest",false),
            "Keep pinned directSolveCoarsest true; do not silently substitute");
    }
    const dictionary& schemes=mesh.schemesDict();
    allEntries(schemes.subDict("ddtSchemes"),"Euler");
    allEntries(schemes.subDict("interpolationSchemes"),"linear");
    allEntries(schemes.subDict("laplacianSchemes"),"Gausslinearcorrected");
    allEntries(schemes.subDict("snGradSchemes"),"corrected");
    const dictionary& grad=schemes.subDict("gradSchemes");
    const wordList grads=grad.toc();
    require(tokens(grad,"grad(U)")=="cellLimitedGausslinear1","Keep limited grad(U)");
    forAll(grads,i) require(tokens(grad,grads[i])
        ==(grads[i]=="grad(U)"?"cellLimitedGausslinear1":"Gausslinear"),
        "Unsupported gradient entry");
    const dictionary& div=schemes.subDict("divSchemes");
    const wordList divs=div.toc();
    require(tokens(div,"div(phi,U)")=="GausslinearUpwindgrad(U)","Keep linearUpwind");
    forAll(divs,i)
    {
        require(divs[i]=="default"||divs[i]=="div(phi,U)"
            ||divs[i]=="div((nuEff*dev2(T(grad(U)))))","Extra divergence entry unsupported");
        const std::string expected=divs[i]=="default"?"none":
            (divs[i]=="div(phi,U)"?"GausslinearUpwindgrad(U)":"Gausslinear");
        require(tokens(div,divs[i])==expected,"Changed divergence scheme");
    }
    require(!mesh.fluxRequired("U"),"U flux correction storage is not ported");
    const word policy=controls.get<word>("initialPhiPolicy");
    const bool supplied=isFile(runTime.path()/runTime.timeName()/"phi");
    require((policy=="computeFromPinnedU"&&!supplied)
        ||(policy=="sharedPinnedPhi"&&supplied),"Initial phi policy/file mismatch");
    Info<<"C29_SCOPE static serial constant-nu Euler; hybrid host source;"
        <<" explicit UFinal; native branch identity differs from Foundation14"<<endl;
}
}
#endif
