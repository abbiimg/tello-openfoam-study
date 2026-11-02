// SPDX-License-Identifier: GPL-3.0-or-later
// Derived from pinned native createFields.H; original hash is in manifest.
Info<< "Reading transportProperties\n" << endl;

IOdictionary transportProperties
(
    IOobject
    (
        "transportProperties",
        runTime.constant(),
        mesh,
        IOobject::MUST_READ_IF_MODIFIED,
        IOobject::NO_WRITE
    )
);

dimensionedScalar nu
(
    "nu",
    dimViscosity,
    transportProperties
);

Info<< "Reading field p\n" << endl;
autoPtr<volScalarField> pOwner
(
    new volScalarField(
    IOobject
    (
        "p",
        runTime.timeName(),
        mesh,
        IOobject::MUST_READ,
        IOobject::AUTO_WRITE
    ),
    mesh
)
);
volScalarField& p=pOwner();
C29::managedGeometricField(p,"p");


Info<< "Reading field U\n" << endl;
autoPtr<volVectorField> UOwner
(
    new volVectorField(
    IOobject
    (
        "U",
        runTime.timeName(),
        mesh,
        IOobject::MUST_READ,
        IOobject::AUTO_WRITE
    ),
    mesh
)
);
volVectorField& U=UOwner();
C29::managedGeometricField(U,"U");


#include "createC29ManagedPhi.H"


label pRefCell = 0;
scalar pRefValue = 0.0;
setRefCell(p, mesh.solutionDict().subDict("PISO"), pRefCell, pRefValue);
mesh.setFluxRequired(p.name());

// Constant laminar nuEff. Incompressible alpha/rho model multipliers are one.
autoPtr<volScalarField> nuEffOwner
(
    new volScalarField(
    IOobject("nuEff",runTime.constant(),mesh,IOobject::NO_READ,IOobject::NO_WRITE,false),
    mesh,nu
)
);
volScalarField& nuEff=nuEffOwner();
C29::managedGeometricField(nuEff,"nuEff");
