# baseline_scenario_views.py
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
import logging
import numpy as np
import json
import time
import threading
from queue import Queue, Empty
from siren_web.database_operations import (
    fetch_analysis_scenario,
    fetch_technologies_with_multipliers, fetch_module_settings_data, 
    fetch_scenario_settings_data, update_scenario_settings_data
)
from siren_web.models import Scenarios, ScenariosTechnologies
from typing import Dict, Any
from ..forms import BaselineScenarioForm, RunPowermatchForm
from .balance_grid_load import DispatchResults
from powermatchui.views.exec_powermatch import submit_powermatch_with_progress
from .progress_handler import (
    ProgressHandler, ProgressChannel, ProgressUpdate
)

# Global storage for SSE channels and progress data
progress_channels = {}
progress_storage = {}
logger = logging.getLogger(__name__)

@login_required
def baseline_scenario(request):
    if request.user.groups.filter(name='modellers').exists():
        pass
    else:
        success_message = "Access not allowed."
        context = {
            'success_message': success_message,
        }
        return render(request, 'powermatchui_home.html', context)
    
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    
    if not demand_year:
        success_message = "Set a demand year and scenario first."
    else:
        technologies = fetch_technologies_with_multipliers(scenario)
        scenario_settings = fetch_module_settings_data('Powermatch')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
    
    baseline_form = BaselineScenarioForm(technologies=technologies)
    runpowermatch_form = RunPowermatchForm()

    if request.method == 'POST' and demand_year:
        baseline_form = BaselineScenarioForm(request.POST, technologies=technologies)
        if baseline_form.is_valid():
            cleaned_data = baseline_form.cleaned_data
            carbon_price = cleaned_data.get('carbon_price')
            discount_rate = cleaned_data.get('discount_rate')
            
            # Update carbon price if changed
            if (carbon_price != Decimal(scenario_settings['carbon_price'])):
                update_scenario_settings_data(scenario, 'Powermatch', 'carbon price', carbon_price)
                    
            # Update discount rate
            if (discount_rate != Decimal(scenario_settings['discount_rate'])):
                update_scenario_settings_data(scenario, 'Powermatch', 'discount rate', discount_rate)
            
            success_message = "No changes were made."
            
            # Update technology multipliers
            for technology in technologies:
                idtechnologies = technology.idtechnologies
                multiplier_key = f"multiplier_{idtechnologies}"
                new_multiplier = cleaned_data.get(multiplier_key)
                
                try:
                    # Get the ScenariosTechnologies instance
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios__title=scenario,
                        idtechnologies=technology
                    )
                    
                    if scenario_tech.mult != float(new_multiplier):
                        # Update the multiplier on ScenariosTechnologies
                        scenario_tech.mult = float(new_multiplier)
                        scenario_tech.save()
                        success_message = "Runtime parameters updated."
                        
                except ScenariosTechnologies.DoesNotExist:
                    # Handle case where technology is not in scenario
                    messages.warning(request, f"Technology {technology.technology_name} not found in scenario {scenario}")
                    continue
                except ValueError:
                    # Handle invalid multiplier values
                    messages.error(request, f"Invalid multiplier value for {technology.technology_name}")
                    continue
        else:
            # Handle form errors and display specific messages for multiplier fields
            for field_name, errors in baseline_form.errors.items():
                if field_name.startswith('multiplier_'):
                    tech_id = field_name.replace('multiplier_', '')
                    # Find the technology name for better error messaging
                    tech_name = "Unknown"
                    for tech in technologies:
                        if str(tech.pk) == tech_id:
                            tech_name = tech.technology_name
                            break
                    for error in errors:
                        messages.error(request, f"Multiplier error for {tech_name}: {error}")
                elif field_name in ['carbon_price', 'discount_rate']:
                    for error in errors:
                        messages.error(request, f"{field_name.replace('_', ' ').title()}: {error}")
                else:
                    # Handle any other field errors
                    for error in errors:
                        messages.error(request, f"{field_name}: {error}")
            
            # Render the form with errors
            technologies = fetch_technologies_with_multipliers(scenario)
            scenario_settings = fetch_scenario_settings_data(scenario)
            if not scenario_settings:
                scenario_settings = fetch_module_settings_data('Powermatch')

            carbon_price = scenario_settings.get('carbon_price', None)
            discount_rate = scenario_settings.get('discount_rate', None)

            context = {
                'baseline_form': baseline_form,
                'runpowermatch_form': RunPowermatchForm(),
                'technologies': technologies,
                'scenario_settings': scenario_settings,
                'demand_year': demand_year,
                'scenario': scenario,
                'config_file': config_file,
                'success_message': 'Correct errors and resubmit.',
            }
            return render(request, 'baseline_scenario.html', context)
    else:
        if demand_year:
            scenario_obj = Scenarios.objects.get(title=scenario)
            analysis_list = fetch_analysis_scenario(scenario_obj)
            if analysis_list:
                if 'proceed' in request.GET:
                    if request.GET['proceed'] == 'Yes':
                        # Proceed with the rest of the GET function
                        pass
                    else:
                        # User chose not to proceed
                        messages.warning(request, "Operation canceled.")
                        return redirect('powermatchui_home')
                else:
                    # Render a template with the warning message
                    context = {
                        'demand_year': demand_year, 
                        'scenario': scenario,
                        'config_file': config_file,
                        'success_message': success_message
                    }
                    return render(request, 'confirm_overwrite.html', context)
            
    # Prepare form data for display
    if demand_year:
        technologies = fetch_technologies_with_multipliers(scenario)
        carbon_price = scenario_settings.get('carbon_price', None)
        discount_rate = scenario_settings.get('discount_rate', None)
    else:
        technologies = {}
        carbon_price = None
        discount_rate = None
        
    baseline_form = BaselineScenarioForm(
        technologies=technologies, 
        carbon_price=carbon_price, 
        discount_rate=discount_rate
    )

    context = {
        'baseline_form': baseline_form,
        'runpowermatch_form': runpowermatch_form,
        'technologies': technologies,
        'scenario_settings': scenario_settings,
        'demand_year': demand_year, 
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
    }
    return render(request, 'baseline_scenario.html', context)

def run_baseline_progress(request):
    """Start analysis with SSE progress tracking"""
    logger.info(f"run_baseline_progress called with method: {request.method}")
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    logger.info(f"Session data - demand_year: {demand_year}, scenario: {scenario}")
    
    if request.method == 'POST':
        runpowermatch_form = RunPowermatchForm(request.POST)
        
        if not demand_year:
            return JsonResponse({
                'error': "Set the demand year and scenario first."
            }, status=400)
            
        elif runpowermatch_form.is_valid():
            level_of_detail = runpowermatch_form.cleaned_data['level_of_detail']
            save_baseline = runpowermatch_form.cleaned_data['save_baseline']
            option = level_of_detail[0]
            
            # Create unique session ID
            session_id = f"{request.session.session_key}_{int(time.time())}"
            
            # Create progress channel
            channel = ProgressChannel(session_id)
            progress_channels[session_id] = channel
            logger.info(f"Progress channel created and stored for session {session_id}")
            
            def progress_callback(progress_update: ProgressUpdate):
                """Callback function that pushes updates via SSE"""
                update_data = {
                    'type': 'progress',
                    'percentage': progress_update.percentage,
                    'message': progress_update.message,
                    'elapsed_time': progress_update.elapsed_time,
                    'estimated_remaining': progress_update.estimated_remaining
                }
                logger.debug(f"Sending progress update: {progress_update.percentage}% - {progress_update.message}")
                channel.send_update(update_data)
            
            def run_powermatch_async():
                try:
                    # Create SSE-specific callback
                    logger.info(f"Starting async PowerMatch for session {session_id}")
                    
                    # Create progress handler with SSE callback
                    progress_handler = ProgressHandler(total_steps=100, callback=progress_callback)
                    # Send initial update
                    channel.send_update({
                        'type': 'progress',
                        'percentage': 0,
                        'message': 'Starting analysis...',
                        'elapsed_time': 0,
                        'estimated_remaining': None
                    })
                                       
                    progress_handler.update(5, "Starting PowerMatch analysis...")
                    
                    dispatch_results, summary_report = submit_powermatch_with_progress(
                        demand_year, scenario, option, 1, None, save_baseline, progress_handler
                    )
                    
                    if option == 'D':
                        # For download
                        channel.send_update({
                            'type': 'completed_download',
                            'download_filename': f"{scenario}-baseline detailed results.xlsx"
                        })
                        
                        # Store results for download
                        progress_storage[session_id] = {
                            'status': 'completed_download',
                            'results': dispatch_results,
                            'download_filename': f"{scenario}-baseline detailed results.xlsx"
                        }
                    else:
                        # Process data for display
                        processed_data = process_results_for_template(
                            dispatch_results, scenario, save_baseline, 
                            demand_year, request.session.get('config_file')
                        )
 
                        # Send completion with redirect URL
                        channel.send_update({
                            'type': 'completed',
                            'redirect_url': f'/results/{session_id}/',
                            'message': 'Analysis complete! Redirecting to results...'
                        })
                        
                        # Store results for template rendering
                        progress_storage[session_id] = {
                            'status': 'completed',
                            'template_data': processed_data
                        }
                    
                    progress_handler.finish("Analysis complete!")
                    
                except Exception as e:
                    channel.send_update({
                        'type': 'error',
                        'error': str(e),
                        'message': f'Analysis failed: {str(e)}'
                    })
                finally:
                    # Close the channel
                    channel.close()
        
            # Start background thread
            logger.info("Starting background thread")
            thread = threading.Thread(target=run_powermatch_async)
            thread.daemon = True
            thread.start()
            
            # Return response with SSE URL
            response_data = {
                'session_id': session_id,
                'message': 'PowerMatch analysis started',
                'sse_url': f'/progress-stream/{session_id}/'
            }
            logger.info(f"Returning response: {response_data}")

            return JsonResponse(response_data)
        else:
            logger.error(f"Form validation failed: {runpowermatch_form.errors}")
            return JsonResponse({'error': 'Form validation failed'}, status=400)
    
    logger.warning("Invalid request method or missing data")
    return JsonResponse({'error': 'Invalid request'}, status=400)

def progress_stream(request, session_id):
    """Server-Sent Events endpoint for real-time progress updates"""
    logger.info(f"SSE connection requested for session: {session_id}")
    
    def event_stream():
        if session_id not in progress_channels:
            logger.error(f"Session {session_id} not found in progress_channels")
            yield f"data: {json.dumps({'type': 'error', 'error': 'Session not found'})}\n\n"
            return
        
        channel = progress_channels[session_id]
        logger.info(f"Found channel for session {session_id}, starting SSE stream")
        
        # Send initial connection confirmation
        initial_msg = {'type': 'connected', 'message': 'Connected to progress stream'}
        yield f"data: {json.dumps(initial_msg)}\n\n"
        logger.info(f"Sent initial connection message for session {session_id}")
        message_count = 0
        last_keepalive = time.time()
        
        try:
            while channel.active:
                try:
                    # Get update from queue (blocks until available)
                    update = channel.queue.get(timeout=5.0)
                    
                    if update is None:  # Signal to close
                        logger.info(f"Received close signal for session {session_id}")
                        break
                    
                    # Send the update
                    message_count += 1
                    logger.debug(f"Sending SSE message #{message_count} for session {session_id}: {update.get('type', 'unknown')}")
                    yield f"data: {json.dumps(update)}\n\n"
                    
                except Empty:
                    # Timeout - send keepalive
                    current_time = time.time()
                    if current_time - last_keepalive > 10:  # Every 10 seconds
                        keepalive_msg = {'type': 'keepalive', 'timestamp': current_time}
                        yield f"data: {json.dumps(keepalive_msg)}\n\n"
                        last_keepalive = current_time
                        logger.debug(f"Sent keepalive for session {session_id}")
                except Exception as e:
                    logger.error(f"Error in SSE stream for session {session_id}: {e}")
                    error_msg = {'type': 'error', 'error': str(e)}
                    yield f"data: {json.dumps(error_msg)}\n\n"
                    break
                    
        except Exception as e:
            logger.error(f"Fatal error in SSE event_stream for session {session_id}: {e}", exc_info=True)
            error_msg = {'type': 'error', 'error': f'Stream error: {str(e)}'}
            yield f"data: {json.dumps(error_msg)}\n\n"
        finally:
            # Cleanup
            logger.info(f"Cleaning up SSE stream for session {session_id}")
            if session_id in progress_channels:
                del progress_channels[session_id]
    
    response = StreamingHttpResponse(
        event_stream(), 
        content_type='text/event-stream; charset=utf-8'
    )
    # Set headers that work with Django development server
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Cache-Control'
    response['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering if deployed
    logger.info(f"Created SSE response for session {session_id}")
    return response

def get_results_page(request, session_id):
    """Render the results page after completion"""
    logger.info(f"get_results_page called for session {session_id}")
    if session_id in progress_storage:
        progress_data = progress_storage[session_id]
        logger.info(f"Found progress data with status: {progress_data['status']}")
        
        if progress_data['status'] == 'completed':
            template_data = progress_data['template_data']
            
            # Clean up progress storage
            del progress_storage[session_id]
            logger.info(f"Cleaned up progress storage for session {session_id}")
            
            # Render the display table template
            return render(request, 'display_table.html', template_data)
            
        elif progress_data['status'] == 'completed_download':
            # Handle Excel download
            logger.info(f"Handling download for session {session_id}")
            dispatch_results = progress_data['results']
            filename = progress_data['download_filename']
            
            # Clean up progress storage
            del progress_storage[session_id]
            
            # Return Excel file
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f"attachment; filename={filename}"
            return response
            
        elif progress_data['status'] == 'error':
            error_msg = progress_data.get('error', 'Unknown error occurred')
            del progress_storage[session_id]
            logger.error(f"Error status for session {session_id}: {error_msg}")
            
            # Render error page or redirect with error message
            messages.error(request, f"Analysis failed: {error_msg}")
            return redirect('baseline_scenario')
        else:
            # Still running
            logger.warning(f"Session {session_id} still running with status: {progress_data['status']}")
            messages.warning(request, "Analysis is still running. Please wait.")
            return redirect('baseline_scenario')
    else:
        logger.error(f"Session {session_id} not found in progress_storage")
        messages.error(request, "Session not found or expired.")
        return redirect('baseline_scenario')

def cancel_analysis(request, session_id):
    """Cancel a running analysis"""
    logger.info(f"cancel_analysis called for session {session_id}")
    if session_id in progress_channels:
        channel = progress_channels[session_id]
        channel.send_update({
            'type': 'error',
            'error': 'Analysis cancelled by user',
            'message': 'Analysis was cancelled'
        })
        channel.close()
        del progress_channels[session_id]
        
        if session_id in progress_storage:
            del progress_storage[session_id]
        logger.info(f"Successfully cancelled analysis for session {session_id}")   
        return JsonResponse({'message': 'Analysis cancelled'})
    else:
        logger.warning(f"Session {session_id} not found for cancellation")
        return JsonResponse({'error': 'Session not found'}, status=404)

def run_baseline(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""

    if request.method == 'POST':
        runpowermatch_form = RunPowermatchForm(request.POST)
        scenario_obj = Scenarios.objects.get(title=scenario)

        if not demand_year:
            success_message = "Set the demand year and scenario first."
        elif runpowermatch_form.is_valid():
            level_of_detail = runpowermatch_form.cleaned_data['level_of_detail']
            save_baseline = runpowermatch_form.cleaned_data['save_baseline']
            option = level_of_detail[0]

            dispatch_results, summary_report = submit_powermatch_with_progress(
                demand_year, scenario, option, 1, 
                None, save_baseline, None
                )
            if option == 'D':
                data_file = f"{scenario}-baseline detailed results"
                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f"attachment; filename={data_file}.xlsx"
                return response
            else:
                # Process data for display
                context = process_results_for_template(
                    dispatch_results, scenario, save_baseline, 
                    demand_year, request.session.get('config_file')
                )
                # Add summary report to context
                return render(request, 'display_table.html', {**context, 'summary_report': summary_report})
                
        technologies = fetch_technologies_with_multipliers(scenario)
        baseline_form = BaselineScenarioForm(technologies=technologies)

        scenario_settings = fetch_scenario_settings_data(scenario)
        context = {
            'baseline_form': baseline_form,
            'runpowermatch_form': runpowermatch_form,
            'technologies': technologies,
            'scenario_settings': scenario_settings,
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'success_message': success_message
        }
        return render(request, 'baseline_scenario.html', context)

def process_results_for_template(dispatch_results, scenario, save_baseline, demand_year, config_file):
    """Helper function to process results for template"""
    sp_output = dispatch_results.summary_data
    metadata = dispatch_results.metadata
    
    # Header mapping
    header_mapping = {
        'capacity_mw': 'Capacity',
        'generation_mwh': 'Generation',
        'to_meet_load_mwh': 'To Meet Load',
        'capacity_factor': 'CF',
        'annual_cost': 'Cost',
        'lcog_per_mwh': 'LCOG Cost',
        'lcoe_per_mwh': 'LCOE Cost',
        'emissions_tco2e': 'Emissions',
        'emissions_cost': 'Emissions Cost',
        'lcoe_with_co2_per_mwh': 'LCOE with CO2 Cost',
        'max_generation_mw': 'Max Generation',
        'max_balance': 'Max Balance',
        'capital_cost': 'Capital Cost',
        'lifetime_cost': 'Lifetime Cost',
        'lifetime_emissions': 'Lifetime Emissions',
        'lifetime_emissions_cost': 'Lifetime Emissions Cost',
        'area_km2': 'Area km²',
        'reference_lcoe': 'Reference LCOE',
        'reference_cf': 'Reference CF'
    }
    
    original_headers = list(sp_output.dtype.names)
    readable_headers = [header_mapping.get(header, header) for header in original_headers]
    
    # Convert structured array to list of lists
    sp_data_list = []
    for row in sp_output:
        row_data = []
        for field in original_headers:
            value = row[field]
            if isinstance(value, (int, float, np.number)):
                row_data.append(round(float(value), 2))
            else:
                row_data.append(value)
        sp_data_list.append(row_data)
    
    success_message = "Baseline re-established" if save_baseline else "Baseline run complete"
    
    return {
        'sp_data': sp_data_list,
        'headers': readable_headers,
        'success_message': success_message,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }

def download_results(request):
    """Download results as Excel file"""
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        
        if session_id and session_id in progress_storage:
            progress_data = progress_storage[session_id]
            
            if progress_data['status'] == 'completed' and 'template_data' in progress_data:
                # Get the results data from template_data
                template_data = progress_data['template_data']
                sp_data = template_data.get('sp_data', [])
                headers = template_data.get('headers', [])
                scenario = template_data.get('scenario', 'unknown')
                
                # Create Excel file
                from io import BytesIO
                import pandas as pd
                
                output = BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Summary sheet
                    if sp_data and headers:
                        summary_df = pd.DataFrame(sp_data, columns=headers)
                        summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Summary report sheet if available
                    if 'summary_report' in template_data:
                        summary_report = template_data['summary_report']
                        
                        # System overview sheet
                        if 'system_overview' in summary_report:
                            system_df = pd.DataFrame([summary_report['system_overview']])
                            system_df.to_excel(writer, sheet_name='System_Overview', index=False)
                        
                        # Economic summary sheet
                        if 'economic_summary' in summary_report:
                            economic_df = pd.DataFrame([summary_report['economic_summary']])
                            economic_df.to_excel(writer, sheet_name='Economics', index=False)
                        
                        # Environmental summary sheet
                        if 'environmental_summary' in summary_report:
                            env_df = pd.DataFrame([summary_report['environmental_summary']])
                            env_df.to_excel(writer, sheet_name='Environmental', index=False)
                
                output.seek(0)
                
                # Create HTTP response
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="powermatch_results_{scenario}_{session_id}.xlsx"'
                
                return response
                
            elif progress_data['status'] == 'completed_download' and 'results' in progress_data:
                # Handle detailed results (option 'D')
                dispatch_results = progress_data['results']
                filename = progress_data.get('download_filename', 'powermatch_detailed_results.xlsx')
                
                # Create detailed Excel file
                from io import BytesIO
                import pandas as pd
                
                output = BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Summary sheet
                    summary_df = pd.DataFrame(dispatch_results.summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Metadata sheet
                    metadata_df = pd.DataFrame([dispatch_results.metadata])
                    metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
                    
                    # Hourly data if available
                    if hasattr(dispatch_results, 'hourly_data') and dispatch_results.hourly_data is not None:
                        hourly_df = pd.DataFrame(dispatch_results.hourly_data)
                        hourly_df.to_excel(writer, sheet_name='Hourly_Data', index=False)
                
                output.seek(0)
                
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                return response
                
        return JsonResponse({'error': 'Results not available'}, status=404)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)