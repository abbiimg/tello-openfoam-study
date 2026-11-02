/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website: https://openfoam.org
    \\  /    A nd           | Copyright (C) 2022-2023 OpenFOAM Foundation
     \\/     M anipulation  |
-------------------------------------------------------------------------------
License
    This file is part of OpenFOAM.

    OpenFOAM is free software: you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    OpenFOAM is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
    for more details.

    You should have received a copy of the GNU General Public License
    along with OpenFOAM. If not, see <http://www.gnu.org/licenses/>.

Application
    c29FoundationInitialPhi

Description
    SOURCE-ONLY fallback initializer, not a flow solver. The phi constructor
    follows Foundation14 incompressibleFluid.C:93-104. A separately reviewed
    FRESH seed-only mesh/U clone and explicit marker are required. No C29,
    pressure solve, time loop, BC correction or field interpolation change.
\*---------------------------------------------------------------------------*/
#include "argList.H"
#include "Time.H"
#include "fvMesh.H"
#include "volFields.H"
#include "surfaceFields.H"
#include "linear.H"
#include "IOdictionary.H"
#include "OSspecific.H"
#include "../C29ExperimentAdmission.H"
using namespace Foam;
int main(int argc,char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"
    IOdictionary admission
    (
        IOobject("c29InitialPhiControls",runTime.constant(),mesh,
            IOobject::MUST_READ,IOobject::NO_WRITE,false)
    );
    if
    (
        Pstream::parRun() || mesh.nCells()!=922576 || mesh.moving()
     || mag(runTime.value()-.6)>1e-13
     || word(admission.lookup("protocol"))!="c29-foundation14-initial-phi-only-v1"
     || !bool(Switch(admission.lookup("allowInitialPhiExperiment")))
     || readLabel(runTime.controlDict().lookup("writePrecision"))<17
     || isFile(runTime.path()/runTime.name()/"phi")
    )
        FatalErrorInFunction<<"Requires marked fresh serial922576 seed at.6,"
            <<" writePrecision>=17 and no existing phi"<<exit(FatalError);
    C29::readExperimentReceipt(admission,"foundation_initial_phi","cpu",runTime.path());
    volVectorField U
    (
        IOobject("U",runTime.name(),mesh,IOobject::MUST_READ,IOobject::NO_WRITE),
        mesh
    );
    // Original Foundation14 constructor semantics, including its interpolation.
    // No phi exists: READ_IF_PRESENT therefore selects this exact fallback.
    surfaceScalarField phi
    (
        IOobject("phi",runTime.name(),mesh,
            IOobject::READ_IF_PRESENT,IOobject::AUTO_WRITE),
        linearInterpolate(U)&mesh.Sf()
    );
    if (!phi.write())
        FatalErrorInFunction<<"Initial phi write failed; do not admit or copy it"
            <<exit(FatalError);
    Info<<"INITIAL_PHI_ONLY: no source, no timestep; hash this fresh output"
        <<" and copy the SAME bytes into both approved fresh controls"<<endl;
    return 0;
}
