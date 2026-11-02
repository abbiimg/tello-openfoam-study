// SPDX-License-Identifier: GPL-3.0-or-later
// Wrapper-only observations: no second C29 call, no later corrected-U sample.
#ifndef C29SourceAccounting_H
#define C29SourceAccounting_H
#include "C29Restrictions.H"
#include "C29ValidationThresholds.H"
#include <cmath>
#include <vector>
namespace C29
{
inline bool closeIdentity
(
    const Foam::scalar error,const Foam::scalar reference,
    const Foam::scalar absolute,const Foam::scalar relative
)
{
    return std::isfinite(error)&&std::isfinite(reference)
        &&Foam::mag(error)<=absolute+relative*Foam::mag(reference);
}
template<class FieldType>
inline Foam::scalar maxMagnitude(const FieldType& field)
{
    Foam::scalar maximum=0;
    managedPointer(field.cdata(),field.size(),"source accounting coefficient/data");
    forAll(field,i)
    {
        const Foam::scalar value=Foam::mag(field[i]);
        require(std::isfinite(value),"Non-finite source matrix coefficient/data");
        maximum=Foam::max(maximum,value);
    }
    return maximum;
}
inline Foam::scalar implicitMaximum(const Foam::fvVectorMatrix& eqn)
{
    Foam::scalar maximum=0;
    // Const accessors and presence checks avoid allocating absent coefficients.
    if (eqn.hasDiag())maximum=Foam::max(maximum,maxMagnitude(eqn.diag()));
    if (eqn.hasUpper())maximum=Foam::max(maximum,maxMagnitude(eqn.upper()));
    if (eqn.hasLower())maximum=Foam::max(maximum,maxMagnitude(eqn.lower()));
    forAll(eqn.internalCoeffs(),patchi)
    {
        maximum=Foam::max(maximum,maxMagnitude(eqn.internalCoeffs()[patchi]));
        maximum=Foam::max(maximum,maxMagnitude(eqn.boundaryCoeffs()[patchi]));
    }
    return maximum;
}
struct SourceObservation
{
    Foam::vector craftForce;
    Foam::scalar airPower;
};
}
#endif
