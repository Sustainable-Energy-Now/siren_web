from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from configparser import ConfigParser
import os
import json

@login_required
def get_config_dict(config):
    """Convert ConfigParser object to dictionary."""
    return {
        section: dict(config.items(section))
        for section in config.sections()
    }

@login_required
def edit_config(request):
    config_dir = './siren_web/siren_files/preferences/'
    if request.GET.get('filename'):  # If specific file was requested
        config_file = request.GET.get('filename')
    else:
        config_file= request.session.get('config_file', '')
    if not config_file:
        config_file = 'siren.ini'
    config_path = os.path.join(config_dir, config_file)
    
    # Get list of existing config files
    config_files = [f for f in os.listdir(config_dir) 
                   if f.endswith('.ini') and os.path.isfile(os.path.join(config_dir, f))]
    
    config = ConfigParser()
    
    if not os.path.exists(config_path):
        if config_file != 'siren.ini':
            messages.error(request, "Configuration file not found!")
            return redirect(reverse('edit_config'))
        else:
        # For default file, create it if it doesn't exist
            config.add_section('DEFAULT')
            with open(config_path, 'w') as configfile:
                config.write(configfile)
    request.session['config_file'] = config_file
    config.read(config_path)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action in ['save', 'save_as']:
            # Get target filename for save
            if action == 'save_as':
                new_filename = request.POST.get('new_filename', '').strip()
                if not new_filename:
                    messages.error(request, "Please provide a filename!")
                    return redirect(reverse('edit_config'))
                if not new_filename.endswith('.ini'):
                    new_filename += '.ini'
                target_path = os.path.join(config_dir, new_filename)
            else:
                target_path = config_path
            
            # Create a new config object for the updated values
            new_config = ConfigParser()
            sections = json.loads(request.POST.get('config_data', '{}'))
            
            try:
                for section, options in sections.items():
                    new_config.add_section(section)
                    for option, value in options.items():
                        new_config.set(section, option, value)
                
                with open(target_path, 'w') as configfile:
                    new_config.write(configfile)
                
                success_msg = "Configuration updated successfully!"
                if action == 'save_as':
                    success_msg = f"Configuration saved as {new_filename}!"
                messages.success(request, success_msg)
                
                if action == 'save_as':
                    redirect_url = f"{reverse('edit_config')}?filename={new_filename}"
                    return redirect(redirect_url)
                    
            except Exception as e:
                messages.error(request, f"Error saving configuration: {str(e)}")
            
            return redirect(reverse('edit_config'))
    
    # Prepare config data for the template
    config_data = get_config_dict(config)
    
    return render(request, 'config.html', {
        'config_data': config_data,
        'current_file': os.path.basename(config_path),
        'config_files': config_files
    })
