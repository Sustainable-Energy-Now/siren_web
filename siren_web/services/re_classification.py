"""
Single source of truth for classifying WEM facilities into fuel-mix buckets
for the RET dashboard, aligned with AEMO's Quarterly Energy Dynamics (QED)
WEM supply-mix method (QED Q2 2026, Table 8 and footnotes 62-63):

- Renewable share is the renewable share of the *fuel mix*: grid solar +
  wind + biomass (incl. waste-to-energy) + hydro + distributed PV, over the
  whole fuel mix including distributed PV.
- Electric Storage Resources (batteries, and pumped hydro which in the SWIS
  is a storage facility) are NOT part of the fuel mix -- their discharge is
  energy already counted once when it was generated, so it is excluded from
  both numerator and denominator.
"""

# Buckets returned by fuel_bucket(). Keys match the generation dict used by
# update_ret_dashboard and the MonthlyREPerformance field stems.
WIND = 'wind'
SOLAR = 'solar_utility'
BIOMASS = 'biomass'
GAS = 'gas'
COAL = 'coal'
HYDRO_STORAGE = 'hydro'      # pumped hydro -> hydro_discharge/hydro_charge fields
STORAGE = 'storage'          # batteries    -> storage_discharge/storage_charge fields
OTHER = 'other'              # unmapped fuel type: counted in demand, not renewable

RENEWABLE_BUCKETS = frozenset({WIND, SOLAR, BIOMASS})
STORAGE_BUCKETS = frozenset({STORAGE, HYDRO_STORAGE})

_BIOMASS_FUELS = frozenset({'BIOMASS', 'LANDFILL_GAS', 'BIOGAS', 'WASTE', 'WTE'})
_GAS_FUELS = frozenset({'GAS', 'NATURAL_GAS', 'DISTILLATE'})


def fuel_bucket(fuel_type, category, technology_name) -> str:
    """Return the fuel-mix bucket for a facility's technology attributes."""
    fuel_type = (fuel_type or '').upper()
    category = (category or '').upper()
    tech_name = (technology_name or '').upper()

    if fuel_type == 'HYDRO':
        # WEM hydro is pumped storage; conventional hydro would be renewable
        # but there is none in the SWIS and no field to hold it separately.
        return HYDRO_STORAGE
    if category == 'STORAGE' or fuel_type == 'BESS' or 'BATTERY' in tech_name:
        return STORAGE
    if fuel_type == 'WIND':
        return WIND
    if fuel_type == 'SOLAR':
        return SOLAR
    if fuel_type in _BIOMASS_FUELS or 'WASTE' in tech_name:
        return BIOMASS
    if fuel_type in _GAS_FUELS:
        return GAS
    if fuel_type == 'COAL':
        return COAL
    return OTHER


def bucket_for_technology(tech) -> str:
    """fuel_bucket() for a Technologies instance (or None)."""
    if tech is None:
        return OTHER
    return fuel_bucket(tech.fuel_type, tech.category, tech.technology_name)


def is_renewable_bucket(bucket) -> bool:
    return bucket in RENEWABLE_BUCKETS


def is_storage_bucket(bucket) -> bool:
    return bucket in STORAGE_BUCKETS
