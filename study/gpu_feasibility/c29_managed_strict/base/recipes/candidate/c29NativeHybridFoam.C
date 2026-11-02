/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | www.openfoam.com
     \\/     M anipulation  |
-------------------------------------------------------------------------------
    Copyright (C) 2011-2016 OpenFOAM Foundation
    Copyright (C) 2019 OpenCFD Ltd.
-------------------------------------------------------------------------------
License
    This file is part of OpenFOAM.

    OpenFOAM is free software: you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    OpenFOAM is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
    for more details.

    You should have received a copy of the GNU General Public License
    along with OpenFOAM.  If not, see <http://www.gnu.org/licenses/>.

Application
    c29NativeHybridFoam

Description
    SOURCE-ONLY CANDIDATE: restricted static constant-nu laminar PISO.
    Full Foundation14 face-flux deviatoric stress, verbatim host C29 source,
    explicit UFinal, exact-epsilon Euler phi correction. Hybrid, not a claim
    of cross-branch equivalence or GPU performance. See README.md.
\*---------------------------------------------------------------------------*/
#include "fvCFD.H"
#include "pisoControl.H"
#include "C29BackendAudit.H"
#include "C29Restrictions.H"
#include "C29Operators.H"
#include "C29HostSource.H"
int main(int argc,char *argv[])
{
    argList::addNote("Restricted C29 hybrid source candidate; not validated CFD");
    argList::addBoolOption("initialFieldsOnly",
        "Write initial field audit copies and exit without source/time stepping");
    #include "setRootCaseLists.H"
    #include "createTime.H"
    IOdictionary c29Controls
    (
        IOobject("c29PortControls",runTime.constant(),runTime,
            IOobject::MUST_READ,IOobject::NO_WRITE,false)
    );
    const bool initialFieldsOnly=args.found("initialFieldsOnly");
    C29::admitExperiment(c29Controls,initialFieldsOnly,runTime);
    C29::auditDevice();
    #include "createMesh.H"
    pisoControl piso(mesh);
    #include "createC29Fields.H"
    #include "initContinuityErrs.H"
    C29::validate(mesh,runTime,U,p,phi,nu,c29Controls);
    Info.precision(17);
    Info<<"C29_LOCAL_CONSTANTS small="<<std::numeric_limits<scalar>::epsilon()
        <<" great="<<scalar(1)/std::numeric_limits<scalar>::epsilon()<<endl;
    Info<<"C29_SOURCE whole=29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd"
        <<" body=ff02e46f3857af75dfff6f69533c97a7baf2cff2478c2b7e7193d0e8aaaf64a7"<<endl;
    // Separate audit objects do not overwrite initialized U,p or supplied phi.
    // Exact initialized agreement is a future gate, not assumed here.
    C29::sync("before initial field audit");
    C29::managedPointer(U.primitiveField().cdata(),U.size(),"initial U");
    C29::managedPointer(p.primitiveField().cdata(),p.size(),"initial p");
    C29::managedPointer(phi.primitiveField().cdata(),phi.size(),"initial phi");
    {
        volVectorField initialU(IOobject("c29_initialU",runTime.timeName(),mesh,
            IOobject::NO_READ,IOobject::NO_WRITE,false),U);
        volScalarField initialP(IOobject("c29_initialP",runTime.timeName(),mesh,
            IOobject::NO_READ,IOobject::NO_WRITE,false),p);
        surfaceScalarField initialPhi(IOobject("c29_initialPhi",runTime.timeName(),mesh,
            IOobject::NO_READ,IOobject::NO_WRITE,false),phi);
        C29::sync("initial audit field copies complete");
        C29::require(initialU.write()&&initialP.write()&&initialPhi.write(),
            "Initial audit field write failed");
    }
    if (initialFieldsOnly)
    {
        Info<<"C29 initial fields only: no C29 update, no timestep"<<endl;
        return 0;
    }
    // Source-only geometry preparation is not part of the initial-only phase.
    C29::preMaterializeGeometry(mesh);
    label steps=0;
    Info<<"Starting restricted fixed-step time loop"<<endl;
    {
        C29::Range loops("C29_NATIVE_TIME_LOOPS");
        while (runTime.loop())
        {
            C29::Range step("C29_NATIVE_TIME_STEP");
            ++steps;
            C29::require(steps<=5&&C29::near(runTime.deltaTValue(),1e-4)
                &&C29::near(runTime.value(),.6+steps*1e-4),"Unexpected clock sequence");
            C29::require(!mesh.moving()&&!mesh.topoChanging(),"Mesh changed");
            Info<<"Time = "<<runTime.timeName()<<nl<<endl;
            #include "CourantNo.H"
            tmp<fvVectorMatrix> tUEqn=C29::momentum(U,phi,nuEff);
            fvVectorMatrix& UEqn=tUEqn.ref();
            C29::applyHostSource(mesh,UEqn);
            // No relaxation: the input scope forbids relaxation factors.
            {
                C29::Range predictorRange("C29_CORE_MOMENTUM_PREDICTOR_UFINAL");
                auto predictor=(UEqn == -fvc::grad(p));
                Info<<"C29_SOLVER momentum=UFinal"<<endl;
                predictor.ref().solve(mesh.solverDict("UFinal"));
                C29::sync("momentum predictor complete");
            }
            while (piso.correct())
            {
                C29::Range pressureRange("C29_CORE_PRESSURE_CORRECTOR");
                volScalarField rAU(1.0/UEqn.A());
                volVectorField HbyA(constrainHbyA(rAU*UEqn.H(),U,p));
                surfaceScalarField phiHbyA
                (
                    "phiHbyA",fvc::flux(HbyA)
                    +fvc::interpolate(rAU)*C29::eulerPhiCorrection(U,phi)
                );
                // Anchored totalPressure makes adjustPhi a no-op; both branch
                // helpers internally check p.needReference(). No forced gauge.
                adjustPhi(phiHbyA,U,p);
                constrainPressure(p,U,phiHbyA,rAU);
                while (piso.correctNonOrthogonal())
                {
                    fvScalarMatrix pEqn
                    (
                        fvm::laplacian(rAU,p)==fvc::div(phiHbyA)
                    );
                    pEqn.setReference(pRefCell,pRefValue);
                    const word selected=p.select(piso.finalInnerIter());
                    Info<<"C29_SOLVER pressure="<<selected<<endl;
                    pEqn.solve(selected);
                    if (piso.finalNonOrthogonalIter())phi=phiHbyA-pEqn.flux();
                    C29::sync("pressure solve/flux before matrix destruction");
                }
                #include "continuityErrs.H"
                // p.relax() is identity for this guarded no-factor dictionary.
                U=HbyA-rAU*fvc::grad(p);
                U.correctBoundaryConditions();
                C29::sync("PISO velocity and BC correction complete");
            }
            runTime.write();
            runTime.printExecutionTime(Info);
        }
    }
    C29::require(steps==5,"Expected exactly five completed steps");
    Info<<"End"<<endl;
    return 0;
}
// ************************************************************************* //
