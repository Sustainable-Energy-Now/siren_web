-- SQL script to migrate RenewableEnergyTarget data to TargetScenario
-- This is a raw SQL alternative to the Django data migration

-- Insert RenewableEnergyTarget records into target_scenarios table
-- Only insert if no base_case scenario exists for that year (to avoid duplicates)
INSERT INTO target_scenarios (
    scenario_name,
    scenario_type,
    scenario_id,
    description,
    year,
    target_type,
    operational_demand,
    underlying_demand,
    storage,
    target_re_percentage,
    target_emissions_tonnes,
    wind_generation,
    solar_generation,
    dpv_generation,
    biomass_generation,
    gas_generation,
    probability_percentage,
    is_active,
    created_at,
    updated_at
)
SELECT
    -- scenario_name: constructed from year and target type
    CONCAT(ret.target_year,
           CASE
               WHEN ret.is_interim_target = 1 THEN ' Interim Target'
               ELSE ' Major Target'
           END
    ) as scenario_name,

    -- scenario_type: default to 'base_case'
    'base_case' as scenario_type,

    -- scenario_id: null (no FK to Scenarios table for migrated targets)
    NULL as scenario_id,

    -- description: copy from old table
    COALESCE(ret.description, '') as description,

    -- year: mapped from target_year
    ret.target_year as year,

    -- target_type: determined by is_interim_target flag
    CASE
        WHEN ret.is_interim_target = 1 THEN 'interim'
        ELSE 'major'
    END as target_type,

    -- operational_demand, underlying_demand, storage: NULL for migrated targets
    NULL as operational_demand,
    NULL as underlying_demand,
    NULL as storage,

    -- target_re_percentage: mapped from target_percentage
    ret.target_percentage as target_re_percentage,

    -- target_emissions_tonnes: copy from old table
    ret.target_emissions_tonnes,

    -- Generation fields: default to 0 for migrated targets
    0 as wind_generation,
    0 as solar_generation,
    0 as dpv_generation,
    0 as biomass_generation,
    0 as gas_generation,

    -- probability_percentage: NULL for targets
    NULL as probability_percentage,

    -- is_active: true by default
    1 as is_active,

    -- Timestamps
    ret.created_at,
    ret.updated_at

FROM renewable_energy_targets ret
WHERE NOT EXISTS (
    -- Don't insert if a base_case scenario already exists for this year
    SELECT 1
    FROM target_scenarios ts
    WHERE ts.scenario_type = 'base_case'
    AND ts.year = ret.target_year
);

-- Display count of migrated records
SELECT COUNT(*) as 'Migrated Records'
FROM renewable_energy_targets;

-- Display the newly migrated target scenarios
SELECT
    scenario_name,
    year,
    target_type,
    target_re_percentage,
    target_emissions_tonnes
FROM target_scenarios
WHERE target_type IN ('major', 'interim')
ORDER BY year;