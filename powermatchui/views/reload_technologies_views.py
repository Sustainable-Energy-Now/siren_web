from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from siren_web.models import Technologies, ScenariosTechnologies, Scenarios
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

        if demand_year and scenario:
            scenario_obj = Scenarios.objects.get(title=scenario)
            idscenarios = scenario_obj.pk

            # Get all year 0 technologies that are not already in the merit_order
            existing_technology_names = ScenariosTechnologies.objects.filter(
                idscenarios=idscenarios
            ).values_list('idtechnologies__technology_name', flat=True)
            name_exclusion_query = ~Q(technology_name__in=existing_technology_names)
            technologies = Technologies.objects.filter(
                name_exclusion_query, year=0, 
            )
            # Create instances of ScenariosTechnologies for the remaining technologies
            for technology in technologies:
                ScenariosTechnologies.objects.create(
                    idscenarios=scenario_obj,
                    idtechnologies=technology,
                    merit_order=999  # Set merit_order to 999 for excluded resources
                )

            # Redirect back to the merit order view
            success_message = "Excluded technologies reloaded."
            context = {
                'success_message': success_message,
            }
            query_string = urlencode(context)
            redirect_url = f"{reverse('merit_order')}?{query_string}"
            return redirect(redirect_url)

    return HttpResponse("Invalid request method.")