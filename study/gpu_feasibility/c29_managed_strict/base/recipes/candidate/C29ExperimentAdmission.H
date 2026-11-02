// SPDX-License-Identifier: GPL-3.0-or-later
// Receipt reader only. Python performs byte auditing before a MANUAL launch.
// This is permission for an unvalidated experiment, never scientific acceptance.
#ifndef C29ExperimentAdmission_H
#define C29ExperimentAdmission_H
#include "IFstream.H"
#include "dictionary.H"
#include "Switch.H"
namespace C29
{
inline void admissionRequire(const bool ok,const char* reason)
{
    if (!ok) FatalErrorInFunction<<reason<<Foam::exit(Foam::FatalError);
}
inline void readExperimentReceipt
(
    const Foam::dictionary& controls,
    const Foam::word& phase,
    const Foam::word& backend,const Foam::fileName& actualCase
)
{
    using namespace Foam;
    const fileName receiptFile(controls.lookup("experimentReceiptFile"));
    IFstream receiptStream(receiptFile);
    admissionRequire(receiptStream.good(),"Missing/unreadable experiment receipt");
    const dictionary receipt(receiptStream);
    admissionRequire(word(receipt.lookup("schema"))
        =="c29-unvalidated-input-admission-v2","Unsupported receipt schema");
    admissionRequire(string(receipt.lookup("experimentId"))
        ==string(controls.lookup("experimentId")),"Experiment receipt ID mismatch");
    admissionRequire(word(receipt.lookup("phase"))==phase
        &&word(receipt.lookup("backend"))==backend,"Receipt phase/backend mismatch");
    admissionRequire(fileName(receipt.lookup("casePath"))==actualCase,
        "Receipt belongs to a different actual case path");
    admissionRequire(bool(Switch(receipt.lookup("inputsAudited")))
        &&!bool(Switch(receipt.lookup("runtimeValidated"))),
        "Receipt must attest input audit ONLY, with runtimeValidated false");
    Info<<"C29_EXPERIMENTAL_UNVALIDATED phase="<<phase<<" backend="<<backend
        <<" case="<<actualCase<<" id="<<string(receipt.lookup("experimentId"))
        <<" inputSnapshot="<<string(receipt.lookup("inputSnapshotSha256"))
        <<" launchReceipt="<<string(receipt.lookup("launchReceiptJsonSha256"))
        <<" candidate="<<string(receipt.lookup("candidateManifestSha256"))
        <<" binary="<<string(receipt.lookup("binarySha256"))
        <<" libraries="<<string(receipt.lookup("libraryIdentitySha256"))
        <<"; permission/input audit are NOT runtime acceptance"<<endl;
    // This reader does not hash files. Root must freeze inputs and run the
    // Python receipt recheck immediately before the exact recorded manual argv.
}
}
#endif
