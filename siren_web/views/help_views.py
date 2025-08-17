# gendocs/help_views.py
from datetime import datetime
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings
import os
import shutil
from .help_generator import SirenWebHelpGenerator

def generate_help_html(request):
    """Generate and save help HTML file"""
    try:
        # Create generator
        generator = SirenWebHelpGenerator()
        
        # Generate HTML content
        html_content = generator.generate_help_html()
        
        # Ensure help directory exists
        help_dir = os.path.join(settings.MEDIA_ROOT, 'help')
        os.makedirs(help_dir, exist_ok=True)
        
        # Save HTML file
        help_file_path = os.path.join(help_dir, 'siren_web_manual.html')
        with open(help_file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Clean up
        generator.cleanup()
        
        # Create success response
        help_url = reverse('display_help_html')
        return HttpResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Help Generated Successfully</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .success {{ color: green; }}
                .button {{ 
                    display: inline-block; 
                    padding: 10px 20px; 
                    background: #007cba; 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 10px 5px;
                }}
            </style>
        </head>
        <body>
            <h2 class="success">✓ Help Documentation Generated Successfully!</h2>
            <p>The PowerMap help documentation has been generated and saved.</p>
            
            <a href="{help_url}" class="button" target="_blank">View Help Documentation</a>
            <a href="javascript:history.back()" class="button">Go Back</a>
            
            <h3>Next Steps:</h3>
            <ul>
                <li>Review the generated documentation</li>
                <li>Customize the templates if needed</li>
                <li>Add more detailed charts and content</li>
            </ul>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HttpResponse(f"""
        <!DOCTYPE html>
        <html>
        <head><title>Generation Error</title></head>
        <body>
            <h2 style="color: red;">Error Generating Help</h2>
            <p>An error occurred: {str(e)}</p>
            <p><a href="javascript:history.back()">Go Back</a></p>
        </body>
        </html>
        """, status=500)

def display_help_html(request):
    """Display the generated help HTML file using Django template"""
    help_file_path = os.path.join(settings.MEDIA_ROOT, 'help', 'siren_web_manual.html')
    
    if not os.path.exists(help_file_path):
        return render(request, 'help_not_found.html', status=404)
    
    try:
        with open(help_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract just the content (remove html/head/body tags if present)
        if '<body>' in html_content:
            start = html_content.find('<body>') + 6
            end = html_content.find('</body>')
            html_content = html_content[start:end] if end != -1 else html_content[start:]
        
        # Remove any remaining html/head tags
        import re
        html_content = re.sub(r'</?(?:html|head|body)[^>]*>', '', html_content)
        
        context = {
            'help_html_content': html_content,
            'last_generated': os.path.getmtime(help_file_path),
        }
        
        return render(request, 'help_display.html', context)
        
    except Exception as e:
        context = {'error': str(e)}
        return render(request, 'help_error.html', context, status=500)

def edit_help_template(request):
    """Allow editing of the help template file"""
    template_path = os.path.join(settings.MEDIA_ROOT, 'templates', 'help', 'siren_web_manual.md')
    
    if request.method == 'POST':
        try:
            content = request.POST.get('template_content', '')
            # Validate the template
            validation_errors = validate_template_content(content)
            if validation_errors:
               for error in validation_errors:
                   messages.warning(request, f'Template Warning: {error}')
            
            # Create backup before saving
            create_template_backup(template_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(template_path), exist_ok=True)
            
            # Save the template
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            messages.success(request, 'Template saved successfully!')
            # If user clicked "Save & Generate", redirect to generation
            if 'generate' in request.POST:
                return redirect('generate_help_html')
           
            return redirect('edit_help_template')
            
        except Exception as e:
            messages.error(request, f'Error saving template: {str(e)}')
    
    # Load existing template
    try:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        else:
            template_content = "# PowerMap User Manual\n\n*Edit this template to customize your help documentation.*"
    except Exception as e:
        template_content = f"Error loading template: {str(e)}"
    
    context = {
        'template_content': template_content,
        'template_path': template_path,
        'template_exists': os.path.exists(template_path),
        'backups_available': get_available_backups(template_path),
    }
    
    return render(request, 'edit_template.html', context)

def validate_template_content(content):
   """Validate template content for common issues"""
   errors = []
   
   # Check for basic Jinja2 syntax issues
   try:
       from jinja2 import Template
       Template(content)
   except Exception as e:
       errors.append(f"Jinja2 syntax error: {str(e)}")
   
   # Check for required sections
   required_sections = ['# Siren-Web User Manual', '## Getting Started', '## Map Navigation']
   for section in required_sections:
       if section not in content:
           errors.append(f"Missing recommended section: {section}")
   
   # Check for valid image variables
   valid_variables = [
       'logo_path', 'interface_screenshot', 'navigation_chart', 'facility_legend_chart',
       'generation_date'
   ]
   
   import re
   used_variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', content)
   for var in used_variables:
       if var not in valid_variables:
           errors.append(f"Unknown variable used: {{ {var} }}")
   
   return errors

def create_template_backup(template_path):
   """Create a backup of the current template"""
   if os.path.exists(template_path):
       backup_dir = os.path.join(os.path.dirname(template_path), 'backups')
       os.makedirs(backup_dir, exist_ok=True)
       
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       backup_path = os.path.join(backup_dir, f'help_backup_{timestamp}.md')
       
       shutil.copy2(template_path, backup_path)
       
       # Keep only last 10 backups
       cleanup_old_backups(backup_dir)

def cleanup_old_backups(backup_dir, keep_count=10):
   """Keep only the most recent backups"""
   try:
       backup_files = [f for f in os.listdir(backup_dir) if f.startswith('help_backup_')]
       backup_files.sort(reverse=True)
       
       for old_backup in backup_files[keep_count:]:
           os.remove(os.path.join(backup_dir, old_backup))
           
   except Exception as e:
       print(f"Error cleaning up backups: {e}")
       
def get_available_backups(template_path):
   """Get list of available template backups"""
   backup_dir = os.path.join(os.path.dirname(template_path), 'backups')
   backups = []
   
   if os.path.exists(backup_dir):
       backup_files = [f for f in os.listdir(backup_dir) if f.startswith('help_backup_')]
       for backup_file in sorted(backup_files, reverse=True)[:5]:  # Show last 5
           backup_path = os.path.join(backup_dir, backup_file)
           timestamp = os.path.getmtime(backup_path)
           backups.append({
               'filename': backup_file,
               'timestamp': datetime.fromtimestamp(timestamp),
               'path': backup_path
           })
   
   return backups

def restore_template_backup(request, backup_filename):
   """Restore a template from backup"""
   if request.method == 'POST':
       try:
           template_path = os.path.join(settings.MEDIA_ROOT, 'templates', 'help', 'siren_web_manual.md')
           backup_path = os.path.join(os.path.dirname(template_path), 'backups', backup_filename)
           
           if os.path.exists(backup_path):
               # Create backup of current template before restoring
               create_template_backup(template_path)
               
               # Restore from backup
               shutil.copy2(backup_path, template_path)
               
               messages.success(request, f'Template restored from backup: {backup_filename}')
           else:
               messages.error(request, 'Backup file not found')
               
       except Exception as e:
           messages.error(request, f'Error restoring backup: {str(e)}')
   
   return redirect('edit_help_template')
