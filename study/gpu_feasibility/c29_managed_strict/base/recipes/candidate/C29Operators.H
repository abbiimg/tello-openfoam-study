// SPDX-License-Identifier: GPL-3.0-or-later
// Formulations derived from Foundation14 linearViscousStress,
// momentumTransportModel::divDevTauCorr, fvmDiv::divc and EulerDdtScheme.
// Source hashes/references: physics_review.json and candidate_manifest.json.
#ifndef C29Operators_H
#define C29Operators_H
#include <limits>
#include "C29BackendAudit.H"
namespace C29
{
inline Foam::tmp<Foam::fvVectorMatrix> momentum
(
    Foam::volVectorField& U,
    const Foam::surfaceScalarField& phi,
    const Foam::volScalarField& nuEff
)
{
    using namespace Foam;
    Range range("C29_CORE_MOMENTUM_ASSEMBLY");
    const fvMesh& mesh=U.mesh();
    surfaceScalarField nuFace("c29NuFace",fvc::interpolate(nuEff));
    surfaceVectorField devTauCorrFlux
    (
        "devTauCorrFlux",
        -nuFace*fvc::dotInterpolate(mesh.Sf(),dev2(T(fvc::grad(U))))
    );
    // Exact F14 divc identity when !fluxRequired(U). No cell-tensor shortcut.
    tmp<fvVectorMatrix> result
    (
        fvm::ddt(U) + fvm::div(phi,U)
      - fvm::laplacian(nuFace,U)
      + fvm::Su(fvc::div(devTauCorrFlux),U)
    );
    sync("momentum assembly before temporary destruction");
    return result;
}
inline Foam::tmp<Foam::surfaceScalarField> eulerPhiCorrection
(
    const Foam::volVectorField& U,
    const Foam::surfaceScalarField& phi
)
{
    using namespace Foam;
    // Only static mesh/no MRF/null Uf/constant-density Euler is supported.
    const fvMesh& mesh=U.mesh();
    surfaceScalarField dPhi
    (
        "c29EulerDeltaPhi",
        phi.oldTime()-fvc::dotInterpolate(mesh.Sf(),U.oldTime())
    );
    surfaceScalarField coupling
    (
        "c29EulerCoupling",
        scalar(1)-min
        (
            mag(dPhi)/(mag(phi.oldTime())+dimensionedScalar
            (
                "small",phi.dimensions(),std::numeric_limits<scalar>::epsilon()
            )),
            scalar(1)
        )
    );
    sync("before Euler noncoupled patch mask");
    forAll(U.boundaryField(),patchi)
    {
        if (!U.boundaryField()[patchi].coupled())
            coupling.boundaryFieldRef()[patchi] = scalar(0);
    }
    const dimensionedScalar rDeltaT=scalar(1)/mesh.time().deltaT();
    tmp<surfaceScalarField> result(coupling*rDeltaT*dPhi);
    sync("Euler correction before temporary destruction");
    return result;
}
}
#endif
