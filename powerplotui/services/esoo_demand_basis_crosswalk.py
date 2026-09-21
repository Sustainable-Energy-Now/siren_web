# powerplotui/services/esoo_demand_basis_crosswalk.py
"""
FR-F07 (D13) -- Demand-definition crosswalk: derive an approximate
operational-basis annual energy figure from a published underlying-basis
one, using AEMO's own published decomposition of the two definitions.

Why "underlying - DPV" is not enough. From the 2025 WEM ESOO Data Register
(sheet 'Ch 2_F.9', Expected scenario, 2024-25, GWh):

    delivered consumption   16,326.6   (customer meters, net of DPV, excl. T&D losses)
  + DPV offset               3,826.2
  = underlying              20,152.8   <- published, exact (also exact for 2034-35)

    delivered consumption   16,326.6
  x k                        1.0665    (T&D losses + small items)
  = operational (sent-out)  17,412.2   <- published

So AEMO's underlying minus operational (2,740.6) is DPV minus network
losses, not DPV alone; and k = operational/delivered is stable (~1.0653-1.0666
in every year, 2025 vintage). The crosswalk therefore works per (vintage,
forecast_year) as:

    DPV_btm = U_expected - D_expected          (both published for that vintage)
    O_s     = (U_s - DPV_btm) * k              (s = Low / Expected / High)
    k       = O_expected / D_expected          (own vintage if it publishes operational
                                                Expected, else the latest vintage that
                                                does, for the same forecast year; a year
                                                beyond that vintage's horizon holds the
                                                last available k)

For a vintage that publishes operational Expected this reproduces it exactly
and applies AEMO's own DPV/loss adjustment to the other scenarios. Low/High
assume the Expected scenario's DPV (AEMO publishes DPV by scenario only in
rounded TWh; the spread is at most ~0.5 TWh by 2034).

Scope, per D13: energy only. AEMO has never published peak or minimum demand
on the underlying basis, so no equivalent gap exists for those metrics. This
is a narrow, explicitly-labelled exception to D3's default ("never
reconstruct operational from underlying") -- every row this module produces
is tagged extraction_method='dpv_subtraction' and carries a human-readable
reconciliation_adjustment record (FR-F04), so it is never mistaken for a
figure AEMO published directly. It never extrapolates past a vintage's
published horizon.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from siren_web.models import EsooFigure


class CrosswalkSkipped(Exception):
    """Raised (and caught by the caller) when a figure can't be crosswalked
    -- e.g. no delivered-consumption series for its vintage. Not an error:
    this is FR-F07's "without fabricating precision" in action."""


@dataclass
class LossFactor:
    value: float               # operational / delivered
    source_vintage_year: int
    source_forecast_year: int
    held: bool                 # True if source_forecast_year != the year asked for


def _forecast_key(figure: EsooFigure) -> Tuple[int, int]:
    return figure.vintage.year, figure.forecast_year


class DemandBasisCrosswalk:
    """Loads the Expected-scenario delivered/underlying/operational energy
    series once, so a whole-archive run doesn't re-query per figure."""

    def __init__(self):
        expected = (
            EsooFigure.objects
            .filter(domain='demand', metric='energy', demand_growth_scenario='expected', poe_level__isnull=True)
            .select_related('vintage')
        )
        self.delivered: Dict[Tuple[int, int], EsooFigure] = {}
        self.underlying: Dict[Tuple[int, int], EsooFigure] = {}
        self.published_operational: Dict[Tuple[int, int], EsooFigure] = {}
        for fig in expected:
            if fig.demand_basis == 'delivered':
                self.delivered[_forecast_key(fig)] = fig
            elif fig.demand_basis == 'underlying':
                self.underlying[_forecast_key(fig)] = fig
            elif fig.demand_basis == 'operational' and fig.extraction_method != 'dpv_subtraction':
                # Derived rows are excluded on purpose: k must come from figures AEMO published.
                self.published_operational[_forecast_key(fig)] = fig

        # (vintage_year, forecast_year) -> operational / delivered, wherever both are published
        self._k: Dict[Tuple[int, int], float] = {
            key: op.value / self.delivered[key].value
            for key, op in self.published_operational.items()
            if key in self.delivered and self.delivered[key].value
        }

    def loss_factor(self, vintage_year: int, forecast_year: int) -> LossFactor:
        # Same vintage first, then the most recent other vintage, for this exact forecast year.
        candidates = sorted({v for (v, fy) in self._k if fy == forecast_year}, key=lambda v: (v != vintage_year, -v))
        if candidates:
            v = candidates[0]
            return LossFactor(self._k[(v, forecast_year)], v, forecast_year, held=False)

        # No vintage publishes this year (beyond every horizon): hold the latest available year.
        earlier = [(v, fy) for (v, fy) in self._k if fy < forecast_year]
        if earlier:
            v, fy = max(earlier, key=lambda key: (key[1], key[0] == vintage_year, key[0]))
            return LossFactor(self._k[(v, fy)], v, fy, held=True)

        raise CrosswalkSkipped(
            f"No vintage publishes both operational and delivered Expected energy at or before {forecast_year}, "
            f"so the operational/delivered factor k can't be established."
        )

    def dpv_behind_the_meter(self, vintage_year: int, forecast_year: int) -> Tuple[float, EsooFigure, EsooFigure]:
        key = (vintage_year, forecast_year)
        delivered = self.delivered.get(key)
        underlying = self.underlying.get(key)
        if delivered is None or underlying is None:
            raise CrosswalkSkipped(
                f"ESOO {vintage_year} has no Expected delivered-consumption series for {forecast_year} "
                f"(run `extract_esoo_figures --year {vintage_year}`) -- DPV can't be separated from underlying."
            )
        dpv = underlying.value - delivered.value
        if not 0 < dpv < underlying.value:
            raise CrosswalkSkipped(
                f"ESOO {vintage_year} {forecast_year}: implied DPV ({dpv:,.1f} GWh) from Expected underlying "
                f"({underlying.value:,.1f}) minus delivered ({delivered.value:,.1f}) is not plausible; skipping."
            )
        return dpv, underlying, delivered


def derive_operational_energy_figure(underlying_figure: EsooFigure, crosswalk: Optional[DemandBasisCrosswalk] = None) -> dict:
    """
    Build the field values for a derived operational-basis EsooFigure row
    from one published underlying-basis energy figure.

    Raises CrosswalkSkipped where the vintage has no delivered series or no
    operational/delivered factor is available -- callers should catch this
    and move on rather than treating it as fatal.
    """
    if underlying_figure.metric != 'energy':
        raise ValueError(f"Crosswalk is energy-only (D13); got metric={underlying_figure.metric!r}")
    if underlying_figure.demand_basis != 'underlying':
        raise ValueError(f"Expected demand_basis='underlying'; got {underlying_figure.demand_basis!r}")
    if (underlying_figure.unit or '').strip().upper() != 'GWH':
        raise ValueError(
            f"Underlying figure (id={underlying_figure.idesoofigure}) has unexpected unit "
            f"'{underlying_figure.unit}'; expected GWh -- refusing to guess a conversion."
        )

    crosswalk = crosswalk or DemandBasisCrosswalk()
    vintage_year, forecast_year = underlying_figure.vintage.year, underlying_figure.forecast_year

    dpv, expected_underlying, delivered = crosswalk.dpv_behind_the_meter(vintage_year, forecast_year)
    loss = crosswalk.loss_factor(vintage_year, forecast_year)
    derived_value = (underlying_figure.value - dpv) * loss.value

    scenario_note = (
        "" if underlying_figure.demand_growth_scenario == 'expected'
        else f" {underlying_figure.demand_growth_scenario.title()} scenario assumes the Expected scenario's DPV."
    )
    held_note = (
        f" (held from forecast year {loss.source_forecast_year}: no vintage publishes k for {forecast_year})"
        if loss.held else ""
    )
    adjustment_note = (
        f"D13 crosswalk: operational energy derived as (underlying {underlying_figure.value:,.2f} GWh - DPV "
        f"behind-the-meter {dpv:,.2f} GWh) x k {loss.value:.4f} = {derived_value:,.2f} GWh. "
        f"DPV = ESOO {vintage_year} Expected underlying {expected_underlying.value:,.2f} - Expected delivered "
        f"{delivered.value:,.2f} ({delivered.table_ref}). k = operational-as-sent-out / delivered from the "
        f"published ESOO {loss.source_vintage_year} Expected figures, forecast year {loss.source_forecast_year}"
        f"{held_note}.{scenario_note} Not a figure AEMO published directly -- see extraction_method."
    )

    return {
        'vintage': underlying_figure.vintage,
        'domain': underlying_figure.domain,
        'metric': underlying_figure.metric,
        'forecast_year': forecast_year,
        'demand_growth_scenario': underlying_figure.demand_growth_scenario,
        'poe_level': underlying_figure.poe_level,
        'demand_basis': 'operational',
        'value': derived_value,
        'unit': underlying_figure.unit,
        'source_document': underlying_figure.source_document,
        'source_version': underlying_figure.source_version,
        'table_ref': underlying_figure.table_ref,
        'page_ref': underlying_figure.page_ref,
        'cell_ref': underlying_figure.cell_ref,
        'extraction_date': underlying_figure.extraction_date,
        'extraction_method': 'dpv_subtraction',
        'reconciliation_adjustment': adjustment_note,
    }
