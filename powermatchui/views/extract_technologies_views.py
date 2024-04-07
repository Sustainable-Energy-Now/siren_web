# extract_technologies_views.py
from django.db import transaction
from decimal import Decimal
from django.db.models import Sum
from django.contrib import messages
from django.shortcuts import render, redirect
from siren_web.database_operations import delete_analysis_scenario, fetch_analysis_scenario, \
    fetch_included_technologies_data, get_supply_unique_technology, \
    fetch_technology_by_id
from siren_web.models import Demand, Generatorattributes, Technologies, Scenarios, ScenariosSettings, \
    ScenariosTechnologies, Settings, supplyfactors
from ..forms import BaselineScenarioForm, ExtractTechnologiesForm
from powermatchui.views.exec_powermatch import submit_powermatch

def extract_technologies(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    supplyfactors_qs = {}
    extract_technologies_form = ExtractTechnologiesForm(request.POST)
    if not demand_year:
        success_message = "Set the demand year and scenario in the home page first."
    else:
        supplyfactors_qs = supplyfactors.objects.filter(
            year=demand_year
            )[:5]
        if request.method == 'POST' and demand_year:
            if demand_year:
                scenario_obj = Scenarios.objects.get(title=scenario)
                unique_technologies = \
                    get_supply_unique_technology(demand_year, scenario)

                with transaction.atomic():
                    for technology in unique_technologies:
                        technology_obj, created = Technologies.objects.update_or_create(
                            idtechnologies=technology,
                            year=demand_year,
                            defaults={
                                'capacity': capacity,
                                },
                            create_defaults={
                                'idtechnologies': None,
                                'technology_name': technologies_qs[0].technology_name,
                                'technology_signature': technologies_qs[0].technology_signature,
                                # 'scenarios': technologies_qs[0].scenarios,
                                'image': technologies_qs[0].image,
                                'caption': technologies_qs[0].caption,
                                'category': technologies_qs[0].category,
                                'renewable': technologies_qs[0].renewable,
                                'dispatchable': technologies_qs[0].dispatchable,
                                'capex': technologies_qs[0].capex,
                                'fom': technologies_qs[0].fom,
                                'vom': technologies_qs[0].vom,
                                'lifetime': technologies_qs[0].lifetime,
                                'discount_rate': technologies_qs[0].discount_rate,
                                'description': technologies_qs[0].description,
                                'mult': technologies_qs[0].mult,
                                'capacity': capacity,
                                'capacity_max': technologies_qs[0].capacity_max,
                                'capacity_min': technologies_qs[0].capacity_min,
                                'emissions': technologies_qs[0].emissions,
                                'initial': technologies_qs[0].initial,
                                'lcoe': technologies_qs[0].lcoe,
                                'lcoe_cf': technologies_qs[0].lcoe_cf,
                            }
                        )
                            
                        if created:
                            # If the object was not created, copy scenarios from the existing object
                            for scenario in technologies_qs[0].scenarios.all():
                                technology_obj.scenarios.add(scenario)
                            # if the created technology is a Generator also create the GeneratorAttributes
                            if technologies_qs[0].category == 'Generator':
                                old_genattr = Generatorattributes(
                                    idtechnologies=technologies_qs[0]
                                )
                                new_genattr = Generatorattributes.objects.create(
                                    idtechnologies=technology_obj,
                                    year=demand_year,
                                    fuel=old_genattr.fuel
                                )
                            
                            # Update the technology foreign keys in SupplyFactors
                            supplyfactors.objects.filter(
                                idtechnologies=technologies_qs[0],
                                year=demand_year
                                ).update(
                                    idtechnologies=technology_obj
                                )
                            # Update/create the technology foreign keys in ScenariosTechnologies
                            ScenariosTechnologies.objects.filter(
                                idscenarios=scenario_obj,
                                idtechnologies=technologies_qs[0]
                                ).update(
                                    idtechnologies=technology_obj
                                )
                
                delete_analysis_scenario(scenario_obj)
                technologies = {}
                technologies= fetch_included_technologies_data(scenario)

        else:
            technologies_list = fetch_analysis_scenario(demand_year)
            if technologies_list:
                success_message = "Technologies already extracted.  Proceeding will clear the baseline and all variants."

    context = {
        'extract_technologies_form': extract_technologies_form,
        'supplyfactors': supplyfactors,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
    }
    return render(request, 'extract_technologies.html', context)