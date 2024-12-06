# views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from configparser import ConfigParser
import os
from datetime import datetime
import shutil
import json

def backup_config(config_path):
    """Create a backup of the config file with timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{config_path}.{timestamp}.backup"
    shutil.copy2(config_path, backup_path)
    return backup_path

def get_config_dict(config):
    """Convert ConfigParser object to dictionary."""
    return {
        section: dict(config.items(section))
        for section in config.sections()
    }

def edit_config(request):
    config_dir = './siren_web/siren_files/siren_data/preferences/'
    config_path = os.path.join(config_dir, request.GET.get('filename', 'siren.ini'))
    
    # Get list of existing config files
    config_files = [f for f in os.listdir(config_dir) 
                   if f.endswith('.ini') and os.path.isfile(os.path.join(config_dir, f))]
    
    config = ConfigParser()
    
    if not os.path.exists(config_path):
        if request.GET.get('filename'):  # If specific file was requested
            messages.error(request, "Configuration file not found!")
            return redirect(reverse('edit_config'))
        # For default file, create it if it doesn't exist
        config.add_section('DEFAULT')
        with open(config_path, 'w') as configfile:
            config.write(configfile)
    
    config.read(config_path)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        
        if action == 'preview':
            # Create a new config object for preview
            new_config = ConfigParser()
            sections = json.loads(request.POST.get('config_data', '{}'))
            
            for section, options in sections.items():
                new_config.add_section(section)
                for option, value in options.items():
                    new_config.set(section, option, value)
            
            # Return both current and preview configurations
            return JsonResponse({
                'current': get_config_dict(config),
                'preview': get_config_dict(new_config)
            })
            
        elif action in ['save', 'save_as']:
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
            
            # Create backup if file exists
            if os.path.exists(target_path):
                backup_path = backup_config(target_path)
            
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
                if 'backup_path' in locals():
                    success_msg += f" Backup created at {os.path.basename(backup_path)}"
                messages.success(request, success_msg)
                
                if action == 'save_as':
                    redirect_url = f"{reverse('edit_config')}?filename={new_filename}"
                    return redirect(redirect_url)
                    
            except Exception as e:
                messages.error(request, f"Error saving configuration: {str(e)}")
            
            return redirect(reverse('edit_config'))
    
    # Prepare config data for the template
    config_data = get_config_dict(config)
    
    return render(request, 'edit_config.html', {
        'config_data': config_data,
        'current_file': os.path.basename(config_path),
        'config_files': config_files
    })
