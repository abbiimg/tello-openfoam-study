// SPDX-License-Identifier: GPL-3.0-or-later
// Included C29 fragments are unchanged bytes from the original Foundation14 model.
#ifndef C29HostSource_H
#define C29HostSource_H
#include <limits>
#include <type_traits>
#include "C29BackendAudit.H"
#include "C29ManagedOwnership.H"
#include "C29SourceAccounting.H"
// Preserved include fragment MUST be at translation-unit scope.
#include "C29_includes_verbatim.inc"
static_assert(std::is_same<Foam::scalar,double>::value, "C29 requires WM_DP");
namespace C29
{
inline void preMaterializeGeometry(const Foam::fvMesh& mesh)
{
    // Do not call C29 to prime it: that would change controller timing/logs.
    (void)mesh.C(); (void)mesh.V();
    (void)mesh.cellPoints(); (void)mesh.points();
    sync("C29 lazy geometry construction");
}
inline SourceObservation addHostSource
(
    const Foam::fvMesh& caseMesh,Foam::fvVectorMatrix& eqn
)
{
    using namespace Foam;
    sync("before C29 host source / matrix zero-fill");
    managedPointer(caseMesh.C().primitiveField().cdata(),caseMesh.nCells(),"C");
    managedPointer(caseMesh.V().cdata(),caseMesh.nCells(),"V");
    const auto& U = caseMesh.lookupObject<volVectorField>("U");
    managedPointer(U.primitiveField().cdata(),U.size(),"U");
    managedPointer(eqn.source().cdata(),eqn.source().size(),"source matrix");
    managedPointer(caseMesh.points().cdata(),caseMesh.nPoints(),"points");
    require(eqn.dimensions()==dimensionSet(0,4,-2,0,0,0,0),
        "C29 source matrix must have integrated kinematic momentum dimensions");
    const scalar implicitBefore=implicitMaximum(eqn);
    const scalar sourceBefore=maxMagnitude(eqn.source());
    require(implicitBefore==0&&sourceBefore==0,
        "C29 requires a fresh exactly-zero temporary matrix");
    static label auditedLastIndex=-1,auditedCalls=0;
    const label callIndex=caseMesh.time().timeIndex();
    const bool firstAuditedCall=(auditedCalls==0);
    require(callIndex!=auditedLastIndex
        &&(firstAuditedCall||callIndex==auditedLastIndex+1),
        "C29 must be evaluated exactly once per consecutive time index");
    require(auditedCalls<5,"More than five source evaluations in this protocol");
    Range range("C29_HOST_SOURCE_VERBATIM");
    auto mesh = [&caseMesh]() -> const fvMesh& { return caseMesh; };
    using Foam::sqrt; // Restore the original Foam-namespace scalar lookup.
    using Foam::min;
    using Foam::max;
    constexpr scalar small = std::numeric_limits<scalar>::epsilon();
    constexpr scalar great = scalar(1)/small;
    #include "C29_body_verbatim.inc"
    sync("after C29 host source");
    require(update&&last==callIndex,"C29 controller did not update once at this index");
    const scalar implicitAfter=implicitMaximum(eqn);
    require(implicitAfter==0,"C29 changed an implicit or boundary coefficient");
    vector sourceForce(vector::zero);
    scalar sourceWork=0;
    forAll(S,i)
    {
        sourceForce+=1.225*S[i];
        sourceWork+=(1.225*S[i])&vel[i];
    }
    const scalar forceError=mag(sourceForce-craftForce);
    const scalar workError=sourceWork+totalP;
    require(closeIdentity(forceError,mag(craftForce),forceAbs,forceRel),
        "Integrated positive source force does not match craft force");
    require(closeIdentity(workError,totalP,workAbs,workRel),
        "Positive source work must be negative air power");
    static std::vector<scalar> previousThrust;
    if (firstAuditedCall)previousThrust.assign(ctr.size(),scalar(0));
    require(previousThrust.size()==static_cast<std::size_t>(ctr.size()),
        "Changed source geometry/cache lifetime");
    forAll(ctr,r)
    {
        // Read the SAME unmodified pre-predictor vel reference and existing
        // cache immediately after C29. This is a diagnostic repetition of its
        // quadrature, not another source evaluation or independent experiment.
        scalar auditedFlux=0,auditedVolume=0;
        forAll(ids[r],j)
        {
            const label i=ids[r][j];
            auditedFlux+=-(vel[i]&axis[r])*weights[r][j]*V[i];
            auditedVolume+=weights[r][j]*V[i];
        }
        const scalar axial=auditedFlux/volumes[r];
        require(closeIdentity(auditedVolume-volumes[r],volumes[r],volumeAbs,volumeRel),
            "Cached volume does not match the existing quadrature");
        Info<<"C29_ROTOR_AUDIT "<<m.time().value()<<" "<<r
            <<" volume="<<volumes[r]<<" flux="<<auditedFlux<<" w="<<axial
            <<" previousThrust="<<previousThrust[r]<<" thrust="<<thrust[r]
            <<" index="<<callIndex<<" dt="<<m.time().deltaTValue()
            <<" controllerUpdateObserved="<<update<<endl;
        previousThrust[r]=thrust[r];
    }
    ++auditedCalls;auditedLastIndex=callIndex;
    Info<<"C29_SOURCE_AUDIT "<<m.time().value()<<" index="<<callIndex
        <<" call="<<auditedCalls<<" dimensions="<<eqn.dimensions()
        <<" implicitBefore="<<implicitBefore<<" sourceBefore="<<sourceBefore
        <<" implicitAfter="<<implicitAfter<<" craftForce="<<craftForce
        <<" integralPositiveForce="<<sourceForce<<" forceError="<<forceError
        <<" positiveSourceWork="<<sourceWork<<" airPower="<<totalP
        <<" workError="<<workError<<endl;
    return SourceObservation{craftForce,totalP};
}
inline void applyHostSource(const Foam::fvMesh& mesh,Foam::fvVectorMatrix& UEqn)
{
    using namespace Foam;
    const auto& U=mesh.lookupObject<volVectorField>("U");
    autoPtr<fvVectorMatrix> sourceOwner
    (
        new fvVectorMatrix(U,UEqn.dimensions())
    );
    fvVectorMatrix& source=sourceOwner();
    C29::managedMatrix(source,"source");
    const SourceObservation observation=addHostSource(mesh,source);
    sync("before applied-source accounting snapshot");
    managedPointer(UEqn.source().cdata(),UEqn.source().size(),"momentum source");
    // Validation overhead only. It is not a performance-optimized path.
    const std::vector<vector> before(UEqn.source().begin(),UEqn.source().end());
    UEqn-=source;
    sync("after source subtraction / before accounting and destruction");
    vector airForce(vector::zero);
    scalar airWork=0;
    forAll(UEqn.source(),i)
    {
        const vector delta=UEqn.source()[i]-before[i];
        airForce+=1.225*delta;
        airWork+=(1.225*delta)&U[i];
    }
    const scalar forceError=mag(airForce+observation.craftForce);
    const scalar workError=airWork-observation.airPower;
    require(closeIdentity(forceError,mag(observation.craftForce),forceAbs,forceRel),
        "Applied air-source delta must oppose craft force");
    require(closeIdentity(workError,observation.airPower,workAbs,workRel),
        "Applied air-source work must equal signed air power");
    Info<<"C29_APPLIED_AIR_AUDIT "<<mesh.time().value()<<" force="<<airForce
        <<" work="<<airWork<<" forceError="<<forceError
        <<" workError="<<workError<<endl;
}
}
#endif
