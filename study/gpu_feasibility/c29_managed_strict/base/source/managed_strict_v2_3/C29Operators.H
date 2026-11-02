// SPDX-License-Identifier: GPL-3.0-or-later
// Formulations derived from Foundation14 linearViscousStress,
// momentumTransportModel::divDevTauCorr, fvmDiv::divc and EulerDdtScheme.
// Source hashes/references: physics_review.json and candidate_manifest.json.
#ifndef C29Operators_H
#define C29Operators_H
#include <limits>
#include "C29BackendAudit.H"
#include "C29ManagedOwnership.H"
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
    autoPtr<surfaceScalarField> nuFaceOwner
    (
        new surfaceScalarField("c29NuFace",fvc::interpolate(nuEff))
    );
    surfaceScalarField& nuFace=nuFaceOwner();
    C29::managedGeometricField(nuFace,"nuFace");
    autoPtr<surfaceVectorField> devTauCorrFluxOwner
    (
        new surfaceVectorField(
        "devTauCorrFlux",
        -nuFace*fvc::dotInterpolate(mesh.Sf(),dev2(T(fvc::grad(U))))
    )
    );
    surfaceVectorField& devTauCorrFlux=devTauCorrFluxOwner();
    C29::managedGeometricField(devTauCorrFlux,"devTauCorrFlux");
    // Exact F14 divc identity when !fluxRequired(U). No cell-tensor shortcut.
    tmp<fvVectorMatrix> result
    (
        fvm::ddt(U) + fvm::div(phi,U)
      - fvm::laplacian(nuFace,U)
      + fvm::Su(fvc::div(devTauCorrFlux),U)
    );
    C29::managedMatrix(result(),"momentum_result_existing_tmp_heap");
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
    autoPtr<surfaceScalarField> dPhiOwner
    (
        new surfaceScalarField(
        "c29EulerDeltaPhi",
        phi.oldTime()-fvc::dotInterpolate(mesh.Sf(),U.oldTime())
    )
    );
    surfaceScalarField& dPhi=dPhiOwner();
    C29::managedGeometricField(dPhi,"dPhi");
    autoPtr<surfaceScalarField> couplingOwner
    (
        new surfaceScalarField(
        "c29EulerCoupling",
        scalar(1)-min
        (
            mag(dPhi)/(mag(phi.oldTime())+dimensionedScalar
            (
                "small",phi.dimensions(),std::numeric_limits<scalar>::epsilon()
            )),
            scalar(1)
        )
    )
    );
    surfaceScalarField& coupling=couplingOwner();
    C29::managedGeometricField(coupling,"coupling");
    sync("before Euler noncoupled patch mask");
    forAll(U.boundaryField(),patchi)
    {
        if (!U.boundaryField()[patchi].coupled())
            coupling.boundaryFieldRef()[patchi] = scalar(0);
    }
    const dimensionedScalar rDeltaT=scalar(1)/mesh.time().deltaT();
    tmp<surfaceScalarField> result(coupling*rDeltaT*dPhi);
    C29::managedGeometricField(result(),"Euler_result_existing_tmp_heap");
    sync("Euler correction before temporary destruction");
    return result;
}
}
#endif
