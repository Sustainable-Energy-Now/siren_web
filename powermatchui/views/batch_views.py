#  batch_views.py
from ..database_operations import fetch_included_technologies_data, fetch_demand_data
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponse
from ..models import Analysis, Scenarios  # Import the Scenario model
from ..forms import RunBatchForm

# Process form data
@login_required
def setup_batch(request):
    load_year = request.session.get('load_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technologies= fetch_included_technologies_data(load_year)
    form = RunBatchForm(technologies=technologies)
    if request.method == 'POST':
        # Handle form submission
        form = RunBatchForm(request.POST, technologies=technologies)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            iterations = cleaned_data['iterations']
            updated_technologies = {}
            for key in cleaned_data:
                if key.startswith('capacity_'):
                    idtechnology = key.replace('capacity_', '')
                    capacity = cleaned_data[f'multiplier_{idtechnology}']
                    mult = cleaned_data[f'multiplier_{idtechnology}']
                    step = cleaned_data.get(f'step_{idtechnology}', None)
                    updated_technologies[idtechnology] = [capacity, mult, step]
            # Process technologies dictionary as needed
            run_batch(load_year, iterations)
            success_message = "Batch Parameters have been updated."
            
    context = {'form': form, 'technologies': technologies, 'load_year': load_year, 'scenario': scenario, 'success_message': success_message}
    return render(request, 'batch.html', context)

def clearScenario(id: int) -> None:
    Analysis.objects.filter(idScenarios=id).delete()
    
def insert_data(df_message, Scenario, Basis, Stage):
    for row in df_message:
        if row[0] not in [' ', 'Load Analysis', 'Total incl. Carbon Cost', \
            'RE %age', 'Load Analysis', 'Load met', 'Shortfall', \
            'Total Load', 'RE %age of Total Load', 'Surplus', 'Static Variables', \
            'Carbon Price ($/tCO2e)', 'Lifetime (years)', 'Discount Rate']:
            results = [
                ('Capacity', row[0], row[1], 'MW'),
                ('To meet Load', row[0], row[2], 'MWh'),
                ('Cost', row[0], row[5], '$/yr'),
                ('LCOE', row[0], row[7], '$/MWh'),
                ('Emissions', row[0], row[8], 'tCO2e'),
                ('Emissions Cost', row[0], row[9], '$'),
                ('LCOE incl. Carbon Cost', row[0], row[10], '$/MWh'), 
                ('Max.', row[0], row[13], 'MWh'),
                ('Capital Cost', row[0], row[13], '$'),
                ('Lifetime Cost', row[0], row[14], '$'),
                ('Lifetime Emissions', row[0], row[14], 'tCO2e'),
                ('Lifetime Emissions Cost', row[0], row[14], '$'),
            ]
            for Heading, Component, Quantity, Units in results:
                Analysis.objects.create(
                    Scenario=Scenario,
                    Heading=Heading,
                    Component=Component,
                    Basis=Basis,
                    Stage=Stage,
                    Quantity=Quantity,
                    Units=Units
                )

    # Write out Load Analysis statistics and Static Variables
    LoadAnalysis = [
        ('Load met', 'Load Analysis', df_message[14][1], '%'),
        ('Load met', 'Load Analysis', df_message[14][2], 'mWh'),
        ('Shortfall', 'Load Analysis', df_message[15][1], '%'),
        ('Shortfall', 'Load Analysis', df_message[15][2], 'mWh'),
        ('Total Load', 'Load Analysis', df_message[16][2], 'mWh'),
        ('RE %age of Total Load', 'Load Analysis', df_message[17][2], '%'),
        ('Surplus', 'Load Analysis', df_message[19][2], '%'),
        ('Surplus', 'Load Analysis', df_message[19][3], 'mWh')
    ]
    for Heading, Component, Quantity, Units in LoadAnalysis:
        Analysis.objects.create(
            Scenario=Scenario,
            Heading=Heading,
            Component=Component,
            Basis=Basis,
            Stage=Stage,
            Quantity=Quantity,
            Units=Units
        )

    # Insert Static Variables only in the first iteration (i.e., when i == 0)
    if i == 0:
        StaticVariables = [
            ('Carbon Price', 'Static Variables', df_message[22][1], '$/tCO2e'),
            ('Lifetime', 'Static Variables', df_message[23][1], 'years'), 
            ('Discount Rate', 'Static Variables', df_message[24][1], '%'),
        ]
        for Heading, Component, Quantity, Units in StaticVariables:
            Analysis.objects.create(
                Scenario=Scenario,
                Heading=Heading,
                Component=Component,
                Basis=Basis,
                Stage=Stage,
                Quantity=Quantity,
                Units=Units
            )

def run_batch(load_year, scenario, iterations) -> None:
    pmss_details, pmss_data, dispatch_order, re_order = fetch_demand_data(load_year)
    option = 'B'
    pm_data_file = 'G:/Shared drives/SEN Modelling/modelling/SWIS/Powermatch_data_actual.xlsx'
    data_file = 'Powermatch_results_actual.xlsx'
    Basis = 'Optimisation'
    clearScenario(Scenario)
    # Iterate and call doDispatch
    for i in range(iterations):
        # Call doDispatch with option 'B'
        df_message = ex.doDispatch(load_year, option, pmss_details, pmss_data, re_order, dispatch_order,
                    pm_data_file, data_file, title=None)
        # 0 Facility
        # 1 Capacity (Gen, MW Stor, MWh)  
        # 2 To meet Load (MWh)
        # 3 Subtotal (MWh)
        # 4 CF
        # 5 Cost ($/yr)
        # 6 LCOG Cost ($/MWh)
        # 7 LCOE Cost ($/MWh)
        # 8 Emissions (tCO2e)
        # 9 Emissions Cost
        # 10 LCOE incl. Carbon Cost
        # 11 Max. MWH
        # 12 Max. Balance
        # 13 Capital Cost
        # 14 Lifetime Cost
        # 15 Lifetime Emissions
        # 16 Lifetime Emissions Cost
        # 17 Reference LCOE
        # 18 Reference CF
        current_datetime = datetime.now()
        Stage = current_datetime.strftime('%m-%d %H:%M:%S')
        insert_data(df_message, Scenario, Basis, Stage)
        # Adjust capacity by step value
        for key, value in pmss_details.items():
            if key in pmss_update:
                pmss_details[key] = PM_Facility(value.name, value.name, value.capacity + pmss_update[key], 'R', value.col, value.multiplier)
