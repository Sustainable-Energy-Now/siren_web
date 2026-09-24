# powermatchui/utils/esoo_embedded_ev.py
"""
The EV charging load already inside an ESOO-built base scenario.

AEMO's WEM ESOO demand forecast is an *underlying* consumption forecast that
already includes EV charging (2026 ESOO: households ~1 TWh in 2035-36, fleet
~68,000 -> ~717,000). Adding a further EV layer to an ESOO base therefore
counts EV growth twice. The EV scenario builder's "net of ESOO's EV" option
removes this embedded load first, so the result is
``base - embedded EV + scenario EV`` rather than ``base + scenario EV``.

AEMO does not publish the embedded EV energy for every ESOO vintage/scenario
(the 2026 register has no EV component), so it is taken from the AEMO IASR EV
workbook's WEM region -- the CSIRO trajectories the ESOO's EV forecast is
built on -- using a *working hypothesis* for which trajectory each ESOO
scenario tracks:

    ESOO Low -> Slower Growth,  Expected -> Step Change,  High -> Accelerated Transition

Expected -> Step Change is supported by the 2026 ESOO fleet (~717,000 in
2035-36 vs 688,000 BEV+PHEV in the workbook's Step Change WEM trajectory and
1.04M in Accelerated Transition) and households' ~1 TWh vs the workbook's
~1.1 TWh residential EV energy. The Low/High mapping is not documented by
AEMO, so callers surface it as an assumption and the user can override the
energy with a figure of their own.
"""
from dataclasses import dataclass
from typing import Optional

from powermatchui.utils.iasr_ev_energy import IasrDataNotAvailableError, iasr_wem_energy_mwh

ESOO_EV_TRAJECTORY = {
    'low': 'Slower Growth',
    'expected': 'Step Change',
    'high': 'Accelerated Transition',
}


class EmbeddedEvNotAvailableError(ValueError):
    """The EV energy inside the base Demand can't be determined -- enter it by hand."""


@dataclass
class EmbeddedEv:
    energy_mwh: float
    source: str
    is_assumption: bool


def resolve_embedded_ev(base_esoo_scenario: Optional[str], forecast_year: int,
                         override_gwh: Optional[float] = None) -> EmbeddedEv:
    """
    EV energy already inside the base Demand, in MWh, for `forecast_year`.

    `override_gwh` (a user-entered figure) always wins. Otherwise the base
    must be an ESOO-built Demand (its own esoo_scenario field is set) and
    the energy comes from the IASR workbook's WEM trajectory mapped by
    ESOO_EV_TRAJECTORY.
    """
    if override_gwh is not None:
        if override_gwh < 0:
            raise EmbeddedEvNotAvailableError("The EV energy already in the base Demand can't be negative.")
        return EmbeddedEv(override_gwh * 1000.0, f"entered by hand ({override_gwh:,.1f} GWh)", is_assumption=False)

    if not base_esoo_scenario:
        raise EmbeddedEvNotAvailableError(
            "This base Demand wasn't built from an ESOO forecast, so the EV load already in it is unknown. "
            "Enter that figure (GWh) yourself, or untick 'net of ESOO's EV'."
        )
    trajectory = ESOO_EV_TRAJECTORY.get(base_esoo_scenario)
    if trajectory is None:
        raise EmbeddedEvNotAvailableError(
            f"No EV trajectory is mapped to the ESOO '{base_esoo_scenario}' scenario; enter the EV energy (GWh) by hand."
        )

    try:
        mwh, source = iasr_wem_energy_mwh(trajectory, forecast_year)
    except IasrDataNotAvailableError as e:
        raise EmbeddedEvNotAvailableError(
            f"{e} Enter the EV energy already in the base scenario (GWh) by hand."
        )
    return EmbeddedEv(
        mwh,
        f"{source}, taken as the trajectory behind ESOO {base_esoo_scenario}",
        is_assumption=True,
    )
