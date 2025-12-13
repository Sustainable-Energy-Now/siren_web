# signals.py
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.db.models import Sum
from django.dispatch import receiver
from siren_web.models import (
    facilities, 
    FacilityStorage,
    ScenariosTechnologies, 
    Technologies, 
    Scenarios,
    FacilityWindTurbines
)

# === FACILITY STORAGE SIGNALS ===
@receiver(post_save, sender='siren_web.ScenariosFacilities')
def add_technology_to_scenario_on_facility_add(sender, instance, created, **kwargs):
    """
    When a facility is added to a scenario, ensure the facility's technology 
    is also added to that scenario (if not already present).
    Deletions are handled by MariaDB CASCADE constraints.
    """
    if not created:
        # Only handle new relationships, not updates
        return
    
    facility = instance.idfacilities
    scenario = instance.idscenarios
    technology = facility.idtechnologies
    
    # Set merit_order based on technology name
    merit_order = 0 if technology.technology_name == 'Load' else 999
    
    # Check if this technology is already in the scenario
    scenario_tech, tech_created = ScenariosTechnologies.objects.get_or_create(
        idscenarios=scenario,
        idtechnologies=technology,
        defaults={'merit_order': merit_order, 'capacity': 0.0}
    )
    
    # Update the capacity for this technology in this scenario
    scenario_tech.update_capacity()

@receiver(post_save, sender='siren_web.facilities')
def update_capacity_on_facility_change(sender, instance, **kwargs):
    """
    When a facility's capacity changes, update all related ScenariosTechnologies capacities.
    Also handle wind farm capacity updates when wind turbines are associated.
    """
    facility = instance
    technology = facility.idtechnologies
    
    # If this is a wind facility, calculate total capacity from wind turbines
    if facility.is_wind_farm:
        wind_capacity = facility.get_total_wind_capacity()
        if wind_capacity and wind_capacity != facility.capacity:
            # Update facility capacity to match wind turbine total
            facility.capacity = wind_capacity
            facility.save(update_fields=['capacity'])
    
    # Update capacity for this technology in all scenarios where this facility exists
    for scenario in facility.scenarios.all():
        try:
            scenario_tech = ScenariosTechnologies.objects.get(
                idscenarios=scenario,
                idtechnologies=technology
            )
            scenario_tech.update_capacity()
        except ScenariosTechnologies.DoesNotExist:
            # If scenario technology doesn't exist, create it
            merit_order = 0 if technology.technology_name == 'Load' else 999
            scenario_tech = ScenariosTechnologies.objects.create(
                idscenarios=scenario,
                idtechnologies=technology,
                merit_order=merit_order,
                capacity=0.0
            )
            scenario_tech.update_capacity()

# This is the key signal for M2M changes through the admin or ORM
@receiver(m2m_changed, sender='siren_web.ScenariosFacilities')
def handle_facility_scenario_m2m_changes(sender, instance, action, pk_set, **kwargs):
    """
    Handle changes to the many-to-many relationship between facilities and scenarios.
    Only handles additions - deletions are managed by MariaDB CASCADE constraints.
    """
    if action != 'post_add':
        return
    
    facility = instance
    technology = facility.idtechnologies
    
    # Set merit_order based on technology name
    merit_order = 0 if technology.technology_name == 'Load' else 999
    
    # Facilities were added to scenarios
    for scenario_id in pk_set:
        scenario = Scenarios.objects.get(pk=scenario_id)
        
        # Ensure technology is in scenario
        scenario_tech, created = ScenariosTechnologies.objects.get_or_create(
            idscenarios=scenario,
            idtechnologies=technology,
            defaults={'merit_order': merit_order, 'capacity': 0.0}
        )
        
        # Update capacity
        scenario_tech.update_capacity()

# Additional signal to handle edge cases
@receiver(post_save, sender='siren_web.facilities')
def ensure_technology_scenario_consistency(sender, instance, created, **kwargs):
    """
    Ensure that whenever a facility is created/updated, its technology exists 
    in all scenarios the facility belongs to.
    """
    if not created:
        return  # Only handle new facilities
    
    facility = instance
    technology = facility.idtechnologies
    
    # Set merit_order based on technology name
    merit_order = 0 if technology.technology_name == 'Load' else 999
    
    # For each scenario this facility belongs to, ensure the technology is also there
    for scenario in facility.scenarios.all():
        scenario_tech, tech_created = ScenariosTechnologies.objects.get_or_create(
            idscenarios=scenario,
            idtechnologies=technology,
            defaults={'merit_order': merit_order, 'capacity': 0.0}
        )
        
        # Update capacity
        scenario_tech.update_capacity()

# === WIND TURBINE SIGNALS ===

@receiver(post_save, sender='siren_web.FacilityWindTurbines')
def update_facility_capacity_on_turbine_change(sender, instance, created, **kwargs):
    """
    When wind turbines are added/updated at a facility, recalculate the facility's total capacity.
    This ensures the facility capacity reflects the sum of all wind turbine capacities.
    """
    facility = instance.idfacilities
    
    # Only update if this is a wind technology facility
    if facility.idtechnologies.technology_name.lower() in ['onshore wind', 'offshore wind', 'offshore wind floating']:
        # Calculate total wind capacity
        total_wind_capacity = facility.get_total_wind_capacity()
        
        if total_wind_capacity != facility.capacity:
            # Update facility capacity
            old_capacity = facility.capacity
            facility.capacity = total_wind_capacity
            facility.save(update_fields=['capacity'])
            
            # Update all related scenario technologies
            for scenario in facility.scenarios.all():
                try:
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios=scenario,
                        idtechnologies=facility.idtechnologies
                    )
                    scenario_tech.update_capacity()
                except ScenariosTechnologies.DoesNotExist:
                    pass

@receiver(post_delete, sender='siren_web.FacilityWindTurbines')
def update_facility_capacity_on_turbine_removal(sender, instance, **kwargs):
    """
    When wind turbines are removed from a facility, recalculate the facility's total capacity.
    """
    facility = instance.idfacilities
    
    # Only update if this is a wind technology facility
    if facility.idtechnologies.technology_name.lower() in ['wind', 'wind onshore', 'wind offshore']:
        # Calculate remaining wind capacity
        total_wind_capacity = facility.get_total_wind_capacity()
        
        # Update facility capacity
        facility.capacity = total_wind_capacity
        facility.save(update_fields=['capacity'])
        
        # Update all related scenario technologies
        for scenario in facility.scenarios.all():
            try:
                scenario_tech = ScenariosTechnologies.objects.get(
                    idscenarios=scenario,
                    idtechnologies=facility.idtechnologies
                )
                scenario_tech.update_capacity()
            except ScenariosTechnologies.DoesNotExist:
                pass

@receiver(post_save, sender='siren_web.WindTurbines')
def update_facilities_on_turbine_model_change(sender, instance, **kwargs):
    """
    When a wind turbine model's specifications change (especially rated_power),
    update all facilities using this turbine model.
    """
    wind_turbine = instance
    
    # Find all facility installations using this turbine model
    installations = FacilityWindTurbines.objects.filter(
        idwindturbines=wind_turbine,
        is_active=True
    ).select_related('idfacilities')
    
    # Update capacity for each affected facility
    for installation in installations:
        facility = installation.idfacilities
        
        # Only update if this is a wind technology facility
        if facility.idtechnologies.technology_name.lower() in ['wind', 'wind onshore', 'wind offshore']:
            # Recalculate total wind capacity
            total_wind_capacity = facility.get_total_wind_capacity()
            
            if total_wind_capacity != facility.capacity:
                facility.capacity = total_wind_capacity
                facility.save(update_fields=['capacity'])
                
                # Update all related scenario technologies
                for scenario in facility.scenarios.all():
                    try:
                        scenario_tech = ScenariosTechnologies.objects.get(
                            idscenarios=scenario,
                            idtechnologies=facility.idtechnologies
                        )
                        scenario_tech.update_capacity()
                    except ScenariosTechnologies.DoesNotExist:
                        pass

@receiver(m2m_changed, sender=facilities.wind_turbines.through)
def handle_facility_wind_turbine_m2m_changes(sender, instance, action, pk_set, **kwargs):
    """
    Handle changes to the many-to-many relationship between facilities and wind turbines.
    This catches changes made through the admin interface or direct ORM manipulation.
    """
    if action not in ['post_add', 'post_remove', 'post_clear']:
        return
    
    facility = instance
    
    # Only handle wind technology facilities
    if facility.idtechnologies.technology_name.lower() in ['wind', 'wind onshore', 'wind offshore']:
        # Recalculate total wind capacity
        total_wind_capacity = facility.get_total_wind_capacity()
        
        if total_wind_capacity != facility.capacity:
            facility.capacity = total_wind_capacity
            facility.save(update_fields=['capacity'])
            
            # Update all related scenario technologies
            for scenario in facility.scenarios.all():
                try:
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios=scenario,
                        idtechnologies=facility.idtechnologies
                    )
                    scenario_tech.update_capacity()
                except ScenariosTechnologies.DoesNotExist:
                    pass

@receiver(post_save, sender='siren_web.FacilityStorage')
def update_facility_capacity_on_storage_change(sender, instance, created, **kwargs):
    """
    When storage installations are added/updated at a facility, recalculate 
    the facility's total capacity. This ensures the facility capacity reflects 
    the sum of all storage installation power capacities.
    """
    facility = instance.idfacilities
    technology = instance.idtechnologies
    
    # Only update if this is a storage technology facility
    if technology.category == 'Storage':
        # Calculate total storage power capacity at this facility for this technology
        total_storage_capacity = FacilityStorage.objects.filter(
            idfacilities=facility,
            idtechnologies=technology,
            is_active=True
        ).aggregate(
            total=Sum('power_capacity')
        )['total'] or 0
        
        if total_storage_capacity != facility.capacity:
            # Update facility capacity
            facility.capacity = total_storage_capacity
            facility.save(update_fields=['capacity'])
            
            # Update all related scenario technologies
            for scenario in facility.scenarios.all():
                try:
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios=scenario,
                        idtechnologies=technology
                    )
                    scenario_tech.update_capacity()
                except ScenariosTechnologies.DoesNotExist:
                    pass

@receiver(post_delete, sender='siren_web.FacilityStorage')
def update_facility_capacity_on_storage_removal(sender, instance, **kwargs):
    """
    When storage installations are removed from a facility, recalculate 
    the facility's total capacity.
    """
    facility = instance.idfacilities
    technology = instance.idtechnologies
    
    # Only update if this is a storage technology
    if technology.category == 'Storage':
        # Calculate remaining storage capacity
        total_storage_capacity = FacilityStorage.objects.filter(
            idfacilities=facility,
            idtechnologies=technology,
            is_active=True
        ).aggregate(
            total=models.Sum('power_capacity')
        )['total'] or 0
        
        # Update facility capacity
        facility.capacity = total_storage_capacity
        facility.save(update_fields=['capacity'])
        
        # Update all related scenario technologies
        for scenario in facility.scenarios.all():
            try:
                scenario_tech = ScenariosTechnologies.objects.get(
                    idscenarios=scenario,
                    idtechnologies=technology
                )
                scenario_tech.update_capacity()
            except ScenariosTechnologies.DoesNotExist:
                pass

# Utility function for bulk operations
def sync_scenario_technologies_for_scenario(scenario):
    """
    Utility function to sync all technologies for a specific scenario.
    Useful for data migrations or cleanup operations.
    MariaDB CASCADE will handle deletions automatically.
    """
    
    # Get all unique technologies from facilities in this scenario
    facility_technologies = facilities.objects.filter(
        scenarios=scenario
    ).values_list('idtechnologies', flat=True).distinct()
    
    # Get existing ScenariosTechnologies for this scenario
    existing_scenario_techs = set(
        ScenariosTechnologies.objects.filter(
            idscenarios=scenario
        ).values_list('idtechnologies', flat=True)
    )
    
    # Add missing technologies (deletions handled by MariaDB CASCADE)
    for tech_id in facility_technologies:
        if tech_id not in existing_scenario_techs:
            technology = Technologies.objects.get(pk=tech_id)
            
            # Set merit_order based on technology name
            merit_order = 0 if technology.technology_name == 'Load' else 999
            
            scenario_tech = ScenariosTechnologies.objects.create(
                idscenarios=scenario,
                idtechnologies=technology,
                merit_order=merit_order,
                capacity=0.0
            )
            scenario_tech.update_capacity()

    # Update capacities for all technologies (no manual deletion needed)
    for scenario_tech in ScenariosTechnologies.objects.filter(idscenarios=scenario):
        scenario_tech.update_capacity()

def sync_wind_facility_capacities():
    """
    Utility function to sync all wind facility capacities with their wind turbine totals.
    Useful for data migrations or fixing inconsistencies.
    """
    wind_facilities = facilities.objects.filter(
        idtechnologies__technology_name__icontains='wind'
    ).prefetch_related('facilitywindturbines_set__idwindturbines')
    
    updated_count = 0
    for facility in wind_facilities:
        total_wind_capacity = facility.get_total_wind_capacity()
        
        if total_wind_capacity != facility.capacity:
            facility.capacity = total_wind_capacity
            facility.save(update_fields=['capacity'])
            updated_count += 1
            
            # Update related scenario technologies
            for scenario in facility.scenarios.all():
                try:
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios=scenario,
                        idtechnologies=facility.idtechnologies
                    )
                    scenario_tech.update_capacity()
                except ScenariosTechnologies.DoesNotExist:
                    pass
    
    return updated_count

# Utility function for bulk operations
def sync_storage_facility_capacities():
    """
    Utility function to sync all storage facility capacities with their 
    FacilityStorage installation totals. Useful for data migrations or 
    fixing inconsistencies.
    """
    storage_facilities = facilities.objects.filter(
        idtechnologies__category='Storage'
    ).prefetch_related('storage_installations')
    
    updated_count = 0
    for facility in storage_facilities:
        # Get the technology for this facility
        technology = facility.idtechnologies
        
        # Calculate total storage power capacity
        total_storage_capacity = FacilityStorage.objects.filter(
            idfacilities=facility,
            idtechnologies=technology,
            is_active=True
        ).aggregate(
            total=models.Sum('power_capacity')
        )['total'] or 0
        
        if total_storage_capacity != facility.capacity:
            facility.capacity = total_storage_capacity
            facility.save(update_fields=['capacity'])
            updated_count += 1
            
            # Update related scenario technologies
            for scenario in facility.scenarios.all():
                try:
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios=scenario,
                        idtechnologies=technology
                    )
                    scenario_tech.update_capacity()
                except ScenariosTechnologies.DoesNotExist:
                    pass
    
    return updated_count

def get_storage_summary_for_scenario(scenario):
    """
    Get a summary of all storage installations in a scenario.
    Returns dict with technology names as keys and aggregated storage data as values.
    """
    from django.db.models import Sum, Count
    
    storage_summary = {}
    
    # Get all storage technologies in this scenario
    storage_techs = ScenariosTechnologies.objects.filter(
        idscenarios=scenario,
        idtechnologies__category='Storage'
    ).select_related('idtechnologies')
    
    for scenario_tech in storage_techs:
        technology = scenario_tech.idtechnologies
        tech_name = technology.technology_name
        
        # Get all FacilityStorage installations for this technology in this scenario
        installations = FacilityStorage.objects.filter(
            idtechnologies=technology,
            idfacilities__scenarios=scenario,
            is_active=True
        ).aggregate(
            total_power_capacity=Sum('power_capacity'),
            total_energy_capacity=Sum('energy_capacity'),
            num_installations=Count('idfacilitystorage')
        )
        
        # Calculate average duration if we have both power and energy
        avg_duration = None
        if installations['total_power_capacity'] and installations['total_energy_capacity']:
            avg_duration = installations['total_energy_capacity'] / installations['total_power_capacity']
        
        storage_summary[tech_name] = {
            'power_capacity_mw': installations['total_power_capacity'] or 0,
            'energy_capacity_mwh': installations['total_energy_capacity'] or 0,
            'duration_hours': avg_duration,
            'num_installations': installations['num_installations'] or 0,
            'scenario_capacity': scenario_tech.capacity  # From facilities table
        }
    
    return storage_summary
