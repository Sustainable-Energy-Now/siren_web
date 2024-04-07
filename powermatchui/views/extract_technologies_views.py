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
                            create_defaults={
                                'idtechnologies': None,
                                'technology_name': technology.technology_name,
                                'technology_signature': technology.technology_signature,
                                # 'scenarios': technology.scenarios,
                                'image': technology.image,
                                'caption': technology.caption,
                                'category': technology.category,
                                'renewable': technology.renewable,
                                'dispatchable': technology.dispatchable,
                                'capex': technology.capex,
                                'fom': technology.fom,
                                'vom': technology.vom,
                                'lifetime': technology.lifetime,
                                'discount_rate': technology.discount_rate,
                                'description': technology.description,
                                'mult': technology.mult,
                                'capacity': technology.capacity,
                                'capacity_max': technology.capacity_max,
                                'capacity_min': technology.capacity_min,
                                'emissions': technology.emissions,
                                'initial': technology.initial,
                                'lcoe': technology.lcoe,
                                'lcoe_cf': technology.lcoe_cf,
                            }
                        )

                        if created:
                            # Add the scenario
                            technology_obj.scenarios.add(scenario_obj)
                            # if the created technology is a Generator also create the GeneratorAttributes
                            if technology.category == 'Generator':
                                old_genattr = Generatorattributes(
                                    idtechnologies=technology
                                )
                                new_genattr = Generatorattributes.objects.create(
                                    idtechnologies=technology_obj,
                                    year=demand_year,
                                    fuel=old_genattr.fuel
                                )
                            
                            # Update the technology foreign keys in SupplyFactors
                            supplyfactors.objects.filter(
                                idtechnologies=technology,
                                year=demand_year
                                ).update(
                                    idtechnologies=technology_obj
                                )
                            # Update/create the technology foreign keys in ScenariosTechnologies
                            ScenariosTechnologies.objects.filter(
                                idscenarios=scenario_obj,
                                idtechnologies=technology
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