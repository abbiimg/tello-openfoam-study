// SPDX-License-Identifier: GPL-3.0-or-later
// Preregistered SOURCE-ACCOUNTING tolerances, not CFD uncertainty bounds.
// Full cross-branch/backend proposal is in validation_thresholds.json.
#ifndef C29ValidationThresholds_H
#define C29ValidationThresholds_H
namespace C29
{
constexpr Foam::scalar forceAbs=1e-10,forceRel=1e-10;
constexpr Foam::scalar workAbs=1e-9,workRel=1e-10;
constexpr Foam::scalar volumeAbs=1e-14,volumeRel=1e-12;
}
#endif
