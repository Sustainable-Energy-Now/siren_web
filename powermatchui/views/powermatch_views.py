# powermatch_views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import FormView
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from siren_web.siren.powermatch.logic.logic import Constraint, Facility, PM_Facility, Optimisation
from .powerMatchweb import powerMatchWEB
import openpyxl as oxl
import os
from powermatchui.forms import PowermatchForm
from siren_web.database_operations import (
    fetch_all_config_data, fetch_all_settings_data,
    fetch_config_path,
    fetch_included_technologies_data, fetch_supplyfactors_data
)
from siren_web.models import Analysis, Generatorattributes, Scenarios, ScenariosSettings, ScenariosTechnologies, Storageattributes

class PowermatchView(FormView):
    template_name = 'powermatch_input.html'
    form_class = PowermatchForm
    success_url = reverse_lazy('powermatch_success')

    def get_server_files(self):
        """Get list of files from server directory"""
        server_dir = './siren_web/siren_files/SWIS/'
        try:
            return [f for f in os.listdir(server_dir) 
                   if os.path.isfile(os.path.join(server_dir, f)) 
                   and f.endswith(('.xlsx', '.xls'))]  # Add allowed extensions
        except Exception as e:
            messages.error(self.request, f"Error reading server files: {e}")
            return []

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['server_files'] = self.get_server_files()
        kwargs['config_data'] = fetch_all_config_data(self.request)
        return kwargs

    def form_valid(self, form):
        action = self.request.POST.get('action', 'Save')
        if action in ['Summary', 'Detail', 'Batch', 'Transition']:
            return self.run_powermatch(action, form.cleaned_data)
        else:
            try:
                # Call the appropriate handler method based on the action
                handler_method = getattr(self, f'handle_{action}', None)
                if handler_method:
                    return handler_method(form)
                else:
                    messages.error(self.request, f"Unknown action: {action}")
                    return self.form_invalid(form)
            except Exception as e:
                messages.error(self.request, f"Error processing {action}: {str(e)}")
                return self.form_invalid(form)
        
    def run_powermatch(self, action, cleaned_data):
        """Process PowerMatch calculations and return template response"""
        # try:
        config = fetch_all_config_data(self.request)
        folder_path = './siren_web/siren_files/SWIS/'
        
        # Update file paths with folder path
        file_fields = ['constraints_file', 'generators_file', 'optimisation_file', 
                        'data_file', 'results_file', 'batch_file']
        for field in file_fields:
            cleaned_data[field] = os.path.join(folder_path, cleaned_data[field])

        # Handle load year
        if cleaned_data['load_year'] == 'n/a':
            parts = cleaned_data['data_file'].replace('-', '_').split('_')
            for part in parts:
                if part.isdigit() and len(part) == 4:
                    cleaned_data['load_year'] = part
                    break

        # Run PowerMatch calculations
        web = powerMatchWEB(config, cleaned_data)
        sp_output, headers, sp_pts = web.pmClicked(action)
        if action == 'Detail':
            return HttpResponseRedirect(self.get_success_url())
        # Format the output data
        sp_data = []
        for row in sp_output:
            formatted_row = []
            for item in row:
                if isinstance(item, float):
                    formatted_row.append('{:,.2f}'.format(item))
                else:
                    formatted_row.append(item)
            sp_data.append(formatted_row)

        # Prepare context for template
        context = {
            'sp_data': sp_data,
            'headers': headers,
            'sp_pts': sp_pts,
            'success_message': "Processing complete",
            'demand_year': cleaned_data.get('load_year', 'N/A'),
            'scenario': cleaned_data.get('scenario', 'N/A'),
            'config_file': self.request.session.get('config_file'),
            'form': self.get_form()  # Include form in context for potential reuse
        }

        # Override template for this response
        return self.response_class(
            request=self.request,
            template=['display_table.html'],
            context=context,
            using=self.template_engine
        )

        # except Exception as e:
        #     messages.error(self.request, f"Error running PowerMatch: {str(e)}")
        #     return self.form_invalid(self.get_form())

    def handle_save(self, form):
        """Process the form when Save button is clicked"""
        try:
            config_file_path = fetch_config_path(self.request)
            form.save_to_config(config_file_path)
            messages.success(self.request, "Settings saved successfully!")
        except Exception as e:
            messages.error(self.request, f"Error saving settings: {str(e)}")
        return HttpResponseRedirect(self.get_success_url())

    def handle_optimise(self, form):
        """Run optimisation"""
        optimisation_results = self.run_optimisation(form)
        return self.render_to_response(self.get_context_data(
            form=form,
            results=optimisation_results
        ))

    def handle_help(self, form):
        """Display help information"""
        return self.render_to_response(self.get_context_data(
            form=form,
            template_name='powermatch_help.html'
        ))

    def run_optimisation(self, form):
        """Run optimisation process"""
        # Implement your optimisation logic here
        return {
            'status': 'Optimisation complete',
            # Add optimisation results
        }

@require_POST
def upload_file(request):
    """Handle file uploads and return updated file list"""
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    uploaded_file = request.FILES['file']
    server_dir = './siren_web/siren_files/SWIS/'
    
    try:
        # Save file to server directory
        file_path = os.path.join(server_dir, uploaded_file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # Get updated file list
        files = [f for f in os.listdir(server_dir) 
                if os.path.isfile(os.path.join(server_dir, f))
                and f.endswith(('.xlsx', '.xls'))]
        
        return JsonResponse({
            'success': True,
            'message': 'File uploaded successfully',
            'files': files
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)
