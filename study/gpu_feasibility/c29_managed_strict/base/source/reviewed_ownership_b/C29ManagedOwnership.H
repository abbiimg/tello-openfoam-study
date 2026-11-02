// SPDX-License-Identifier: GPL-3.0-or-later
// SOURCE-ONLY PROPOSAL: address checks, no numerical or controller operation.
#ifndef C29ManagedOwnership_H
#define C29ManagedOwnership_H
#include "C29BackendAudit.H"
#include <iostream>
#include <string>
namespace C29
{
inline void ownedAddress(const void* pointer,const Foam::label count,
    const std::string& name,const char* kind)
{
#if C29_USE_CUDA
    if (!count) return;
    cudaPointerAttributes attributes{};
    checked(cudaPointerGetAttributes(&attributes,pointer),name.c_str());
    if (attributes.type!=cudaMemoryTypeManaged)
        FatalErrorInFunction<<name.c_str()<<" "<<kind
            <<" must be CUDA-managed; observed type="<<int(attributes.type)
            <<Foam::exit(Foam::FatalError);
    std::cout<<"C29_OWNERSHIP name="<<name<<" kind="<<kind
        <<" address="<<pointer<<" type="<<int(attributes.type)<<std::endl;
#else
    (void)pointer;(void)count;(void)name;(void)kind;
#endif
}
template<class Array> inline void managedArray(const Array& array,
    const std::string& name)
{
    ownedAddress(&array,1,name,"descriptor");
    ownedAddress(array.cdata(),array.size(),name,"data");
}
template<class GeoField> inline void managedGeometricField(const GeoField& field,
    const char* name)
{
    const std::string prefix(name);
    ownedAddress(&field,1,prefix,"GeometricField_descriptor");
    managedArray(field.primitiveField(),prefix+".internal");
    const auto& boundary=field.boundaryField();
    ownedAddress(&boundary,1,prefix+".boundary","container_descriptor");
    forAll(boundary,patchi)
        managedArray(boundary[patchi],prefix+".patch"+std::to_string(patchi));
}
template<class Type> inline void managedMatrix(const Foam::fvMatrix<Type>& matrix,
    const char* name)
{
    const std::string prefix(name);
    ownedAddress(&matrix,1,prefix,"fvMatrix_descriptor");
    managedArray(matrix.source(),prefix+".source");
    managedArray(matrix.internalCoeffs(),prefix+".internalCoeffs");
    managedArray(matrix.boundaryCoeffs(),prefix+".boundaryCoeffs");
    managedArray(matrix.coeffsOffset(),prefix+".coeffsOffset");
    // Const getters are reached only for already-existing coefficient storage.
    if (matrix.hasDiag())managedArray(matrix.diag(),prefix+".diag");
    if (matrix.hasUpper())managedArray(matrix.upper(),prefix+".upper");
    if (matrix.hasLower())managedArray(matrix.lower(),prefix+".lower");
}
}
#endif
