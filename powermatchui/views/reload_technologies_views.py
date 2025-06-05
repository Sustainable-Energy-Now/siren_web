from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.db import models
from siren_web.models import Technologies, ScenariosTechnologies, Scenarios, facilities
from urllib.parse import urlencode

@login_required
def reload_technologies(request):
    if request.user.groups.filter(name='modellers').exists():
        pass
    else:
        return HttpResponse("Access not allowed.")

    if request.method == 'POST':
        demand_year = request.session.get('demand_year')
        scenario = request.session.get('scenario')
        config_file = request.session.get('config_file')

        if demand_year and scenario:
            scenario_obj = Scenarios.objects.get(title=scenario)
            idscenarios = scenario_obj.pk

            with transaction.atomic():
                # Get technologies that already exist in ScenariosTechnologies
                existing_technology_ids = ScenariosTechnologies.objects.filter(
                    idscenarios=idscenarios
                ).values_list('idtechnologies__pk', flat=True)

                # Get only technologies that have associated facilities
                technologies_with_facilities = Technologies.objects.filter(
                    facilities__isnull=False
                ).exclude(
                    pk__in=existing_technology_ids
                ).distinct()

                # Get facilities associated with this scenario
                scenario_facilities = facilities.objects.filter(
                    scenarios=scenario_obj
                )

                # Get technologies from scenario-associated facilities
                scenario_technology_ids = Technologies.objects.filter(
                    facilities__in=scenario_facilities
                ).values_list('pk', flat=True)

                # Get the current highest merit_order for scenario-associated technologies
                # (excluding merit_order = 999)
                current_max_merit_order = ScenariosTechnologies.objects.filter(
                    idscenarios=idscenarios,
                    merit_order__lt=999
                ).aggregate(
                    max_order=models.Max('merit_order')
                )['max_order'] or 0

                merit_order_counter = current_max_merit_order + 1

                # Create ScenariosTechnologies instances for technologies with facilities
                created_count = 0
                for technology in technologies_with_facilities:
                    # Check if this technology has facilities associated with the scenario
                    if technology.pk in scenario_technology_ids:
                        merit_order = merit_order_counter
                        merit_order_counter += 1
                    else:
                        merit_order = 999

                    ScenariosTechnologies.objects.create(
                        idscenarios=scenario_obj,
                        idtechnologies=technology,
                        merit_order=merit_order
                    )
                    created_count += 1

            # Redirect back to the merit order view
            success_message = f"Reloaded {created_count} technologies with facilities. Technologies with scenario-associated facilities given merit order {current_max_merit_order + 1} onwards, others set to 999."
            context = {
                'success_message': success_message,
            }
            query_string = urlencode(context)
            redirect_url = f"{reverse('merit_order')}?{query_string}"
            return redirect(redirect_url)

    return HttpResponse("Invalid request method.")