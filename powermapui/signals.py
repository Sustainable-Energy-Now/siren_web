# signals.py
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.db import transaction
from siren_web.models import (
    facilities, 
    ScenariosFacilities, 
    ScenariosTechnologies, 
    Technologies, 
    Scenarios
)

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
    """
    facility = instance
    technology = facility.idtechnologies
    
    # Update capacity for this technology in all scenarios where this facility exists
    for scenario in facility.scenarios.all():
        scenario_tech = ScenariosTechnologies.objects.get(
            idscenarios=scenario,
            idtechnologies=technology
        )
        old_capacity = scenario_tech.capacity
        new_capacity = scenario_tech.update_capacity()

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
