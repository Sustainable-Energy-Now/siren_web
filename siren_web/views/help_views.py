# gendocs/help_views.py
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings
import os
import shutil
from .help_generator import SirenWebHelpGenerator

@login_required
def generate_help_html(request):
    """Generate paginated HTML from the Siren Web markdown manual"""
    try:
        # Define path to your markdown file
        markdown_file_path = os.path.join(settings.MEDIA_ROOT, 'templates', 'help', 'siren_web_manual.md')
        
        # Check if markdown file exists
        if not os.path.exists(markdown_file_path):
            return HttpResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Markdown File Not Found</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .error {{ color: red; }}
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
                <h2 class="error">❌ Markdown File Not Found</h2>
                <p>Could not find the markdown file at: <code>{markdown_file_path}</code></p>
                <p>Please ensure the file exists and try again.</p>
                <a href="javascript:history.back()" class="button">Go Back</a>
            </body>
            </html>
            """, status=404)
        
        # Create generator and generate HTML
        generator = SirenWebHelpGenerator()
        html_content = generator.generate_paginated_html(markdown_file_path)
        
        # Ensure help directory exists
        help_dir = os.path.join(settings.MEDIA_ROOT, 'help')
        os.makedirs(help_dir, exist_ok=True)
        
        # Save HTML file
        help_file_path = os.path.join(help_dir, 'siren_web_manual.html')
        with open(help_file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Clean up
        generator.cleanup()
        
        # Create success response with preview and download options
        help_url = reverse('display_help_html')
        download_url = reverse('download_help_html')
        
        return HttpResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Help Generated Successfully</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    margin: 40px; 
                    background: #f8f9fa;
                    color: #333;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                .success {{ 
                    color: #28a745; 
                    font-size: 1.5em;
                    margin-bottom: 20px;
                }}
                .button {{ 
                    display: inline-block; 
                    padding: 12px 24px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; 
                    text-decoration: none; 
                    border-radius: 25px; 
                    margin: 10px 10px 10px 0;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
                    color: white;
                    text-decoration: none;
                }}
                .button.secondary {{
                    background: #6c757d;
                    box-shadow: 0 4px 15px rgba(108, 117, 125, 0.4);
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .stats h3 {{
                    margin-top: 0;
                    color: #495057;
                }}
                ul {{
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="success">✅ Help Documentation Generated Successfully!</h2>
                
                <div class="stats">
                    <h3>Generation Details</h3>
                    <ul>
                        <li><strong>Source:</strong> {os.path.basename(markdown_file_path)}</li>
                        <li><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</li>
                        <li><strong>Format:</strong> Paginated HTML with table of contents</li>
                        <li><strong>Features:</strong> Responsive design, keyboard navigation, print support</li>
                    </ul>
                </div>
                
                <div style="margin-top: 30px;">
                    <a href="{help_url}" class="button" target="_blank">📖 View Interactive Manual</a>
                    <a href="{download_url}" class="button secondary">⬇️ Download HTML File</a>
                    <a href="javascript:history.back()" class="button secondary">← Go Back</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HttpResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Generation Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h2 class="error">❌ Error Generating Paginated Help</h2>
            <p>An error occurred while processing your markdown file:</p>
            <pre style="background: #f8f8f8; padding: 20px; border-radius: 5px;">{str(e)}</pre>
            <p><a href="javascript:history.back()">← Go Back</a></p>
        </body>
        </html>
        """, status=500)

def display_help_html(request, module_name=None):
    """Display the generated paginated help HTML file

    Args:
        request: Django request object
        module_name: Optional module name (e.g., 'powermap', 'powermatch', etc.)
                    If None, displays the main help index
    """
    # Determine which help file to display
    if module_name:
        help_file_name = f'{module_name}_help.html'
    else:
        help_file_name = 'help_index.html'

    help_file_path = os.path.join(settings.MEDIA_ROOT, 'help', help_file_name)

    if not os.path.exists(help_file_path):
        # Try to auto-generate the help file
        try:
            if module_name:
                markdown_file_name = f'{module_name}_help.md'
            else:
                markdown_file_name = 'help_index.md'

            markdown_file_path = os.path.join(settings.MEDIA_ROOT, 'templates', 'help', markdown_file_name)

            if os.path.exists(markdown_file_path):
                # Auto-generate the help HTML
                generator = SirenWebHelpGenerator(module_name=module_name)
                html_content = generator.generate_paginated_html(
                    markdown_file_path,
                    show_home_link=(module_name is not None)
                )

                # Save the generated HTML
                help_dir = os.path.join(settings.MEDIA_ROOT, 'help')
                os.makedirs(help_dir, exist_ok=True)

                with open(help_file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                generator.cleanup()

                # Return the generated content
                return HttpResponse(html_content, content_type='text/html')
        except Exception as e:
            pass  # Fall through to error handling

        context = {
            'error_title': 'Help Documentation Not Found',
            'error_message': f'The help documentation for "{module_name or "main index"}" has not been generated yet.',
            'suggestion': 'Please generate the help documentation first.',
            'generate_url': reverse('generate_module_help', kwargs={'module_name': module_name}) if module_name else reverse('generate_help_html')
        }
        return render(request, 'help_not_found.html', context, status=404)

    try:
        with open(help_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Return the HTML directly since it's a complete document
        return HttpResponse(html_content, content_type='text/html')

    except Exception as e:
        context = {
            'error_title': 'Error Loading Help Documentation',
            'error_message': f'An error occurred while loading the help file: {str(e)}',
            'suggestion': 'Try regenerating the help documentation.',
            'generate_url': reverse('generate_module_help', kwargs={'module_name': module_name}) if module_name else reverse('generate_help_html')
        }
        return render(request, 'help_error.html', context, status=500)

def download_help_html(request):
    """Download the generated HTML file"""
    help_file_path = os.path.join(settings.MEDIA_ROOT, 'help', 'siren_web_manual.html')
    
    if not os.path.exists(help_file_path):
        return HttpResponse("Help file not found. Please generate it first.", status=404)
    
    try:
        with open(help_file_path, 'rb') as f:
            file_content = f.read()
        
        response = HttpResponse(file_content, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="siren_web_manual_{datetime.now().strftime("%Y%m%d")}.html"'
        response['Content-Length'] = len(file_content)
        return response
        
    except Exception as e:
        return HttpResponse(f"Error downloading file: {str(e)}", status=500)

@login_required
def generate_module_help(request, module_name):
    """Generate help HTML for a specific module"""
    try:
        # Define path to module markdown file
        markdown_file_path = os.path.join(
            settings.MEDIA_ROOT, 'templates', 'help', f'{module_name}_help.md'
        )

        # Check if markdown file exists
        if not os.path.exists(markdown_file_path):
            return HttpResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Markdown File Not Found</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .error {{ color: red; }}
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
                <h2 class="error">❌ Markdown File Not Found</h2>
                <p>Could not find the markdown file at: <code>{markdown_file_path}</code></p>
                <p>Please create the markdown file first or edit it.</p>
                <a href="/help/{module_name}/edit/" class="button">Edit Markdown</a>
                <a href="javascript:history.back()" class="button">Go Back</a>
            </body>
            </html>
            """, status=404)

        # Create generator and generate HTML
        generator = SirenWebHelpGenerator(module_name=module_name)
        html_content = generator.generate_paginated_html(
            markdown_file_path,
            show_home_link=True
        )

        # Ensure help directory exists
        help_dir = os.path.join(settings.MEDIA_ROOT, 'help')
        os.makedirs(help_dir, exist_ok=True)

        # Save HTML file
        help_file_path = os.path.join(help_dir, f'{module_name}_help.html')
        with open(help_file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Clean up
        generator.cleanup()

        # Create success response
        help_url = reverse('display_module_help', kwargs={'module_name': module_name})

        return HttpResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Help Generated Successfully</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 40px;
                    background: #f8f9fa;
                    color: #333;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                .success {{
                    color: #28a745;
                    font-size: 1.5em;
                    margin-bottom: 20px;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 25px;
                    margin: 10px 10px 10px 0;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
                    color: white;
                    text-decoration: none;
                }}
                .button.secondary {{
                    background: #6c757d;
                    box-shadow: 0 4px 15px rgba(108, 117, 125, 0.4);
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="success">✅ {module_name.title()} Help Generated Successfully!</h2>

                <div class="stats">
                    <h3>Generation Details</h3>
                    <ul>
                        <li><strong>Module:</strong> {module_name}</li>
                        <li><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</li>
                        <li><strong>Format:</strong> Paginated HTML with navigation</li>
                    </ul>
                </div>

                <div style="margin-top: 30px;">
                    <a href="{help_url}" class="button" target="_blank">📖 View Module Help</a>
                    <a href="/help/" class="button secondary">← Back to Main Help</a>
                </div>
            </div>
        </body>
        </html>
        """)

    except Exception as e:
        return HttpResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Generation Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h2 class="error">❌ Error Generating Help</h2>
            <p>An error occurred while processing the markdown file:</p>
            <pre style="background: #f8f8f8; padding: 20px; border-radius: 5px;">{str(e)}</pre>
            <p><a href="javascript:history.back()">← Go Back</a></p>
        </body>
        </html>
        """, status=500)

@login_required
def regenerate_from_markdown(request):
    """API endpoint to regenerate help from markdown file"""
    if request.method == 'POST':
        try:
            markdown_file_path = request.POST.get('markdown_path',
                os.path.join(settings.BASE_DIR, 'siren_web_manual.md'))

            if not os.path.exists(markdown_file_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Markdown file not found: {markdown_file_path}'
                })

            generator = SirenWebHelpGenerator()
            html_content = generator.generate_paginated_html(markdown_file_path)

            help_dir = os.path.join(settings.MEDIA_ROOT, 'help')
            os.makedirs(help_dir, exist_ok=True)

            help_file_path = os.path.join(help_dir, 'siren_web_manual.html')
            with open(help_file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            generator.cleanup()

            # Count sections for response
            sections = generator.parse_markdown_sections(
                generator.load_markdown_file(markdown_file_path)
            )

            return JsonResponse({
                'success': True,
                'message': 'Help documentation regenerated successfully',
                'sections_count': len(sections),
                'generated_at': datetime.now().isoformat(),
                'file_size': len(html_content)
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def edit_module_help_markdown(request, module_name):
    """Edit markdown file for a specific module"""
    markdown_file_path = os.path.join(
        settings.MEDIA_ROOT, 'templates', 'help', f'{module_name}_help.md'
    )

    if request.method == 'POST':
        try:
            content = request.POST.get('template_content', '')

            # Normalize line endings
            content = content.replace('\r\n', '\n')
            content = content.replace('\r', '\n')

            # Validate markdown content
            validation_errors = validate_markdown_content(content)
            if validation_errors:
                for error in validation_errors:
                    messages.warning(request, f'Markdown Warning: {error}')

            # Create backup before saving
            create_markdown_backup(markdown_file_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(markdown_file_path), exist_ok=True)

            # Save the markdown file
            with open(markdown_file_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)

            messages.success(request, f'Markdown file saved successfully!')

            # If user clicked "Save & Generate", redirect to generation
            if 'generate' in request.POST or request.POST.get('action') == 'generate':
                return redirect('generate_module_help', module_name=module_name)

            return redirect('edit_module_help_markdown', module_name=module_name)

        except Exception as e:
            messages.error(request, f'Error saving markdown file: {str(e)}')
            import traceback
            print(f"Full error traceback: {traceback.format_exc()}")

    # Load existing markdown file
    try:
        if os.path.exists(markdown_file_path):
            with open(markdown_file_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        else:
            # Create default content if file doesn't exist
            module_titles = {
                'powermap': 'Powermap Module',
                'powermatch': 'Powermatch Module',
                'powerplot': 'Powerplot Module',
                'terminal': 'Terminal Management',
                'aemo_scada': 'AEMO SCADA Data Fetcher',
                'system_overview': 'System Overview'
            }
            module_title = module_titles.get(module_name, module_name.title())

            template_content = f"""# {module_title}

## Overview

Welcome to the {module_title} documentation.

## Getting Started

Instructions for using this module...

## Features

Key features of this module...

*Edit this markdown file to customize the help documentation for {module_title}.*"""

            # Create the file with default content
            os.makedirs(os.path.dirname(markdown_file_path), exist_ok=True)
            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                f.write(template_content)

    except Exception as e:
        template_content = f"Error loading markdown file: {str(e)}"
        messages.error(request, f'Error loading markdown file: {str(e)}')

    # Get file statistics
    file_stats = {}
    if os.path.exists(markdown_file_path):
        stat = os.stat(markdown_file_path)
        file_stats = {
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'lines': len(template_content.split('\n'))
        }

    context = {
        'template_content': template_content,
        'template_path': markdown_file_path,
        'markdown_file_path': markdown_file_path,
        'file_exists': os.path.exists(markdown_file_path),
        'file_stats': file_stats,
        'backups_available': get_available_backups(markdown_file_path),
        'module_name': module_name,
    }

    return render(request, 'edit_help.html', context)

@login_required
def edit_help_markdown(request, module_name=None):
    """Enhanced template editor that works with markdown files"""
    # If module_name is provided, redirect to module-specific editor
    if module_name:
        return edit_module_help_markdown(request, module_name)

    markdown_file_path = os.path.join(settings.MEDIA_ROOT, 'templates', 'help', 'siren_web_manual.md')
    
    if request.method == 'POST':
        try:
            content = request.POST.get('template_content', '')

            # Normalize line endings to prevent extra blank lines
            # Replace Windows line endings (\r\n) with Unix line endings (\n)
            content = content.replace('\r\n', '\n')
            # Remove any standalone \r characters
            content = content.replace('\r', '\n')

            # Validate markdown content
            validation_errors = validate_markdown_content(content)
            if validation_errors:
                for error in validation_errors:
                    messages.warning(request, f'Markdown Warning: {error}')

            # Create backup before saving
            create_markdown_backup(markdown_file_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(markdown_file_path), exist_ok=True)

            # Save the markdown file with normalized line endings
            with open(markdown_file_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            
            messages.success(request, f'Markdown file saved successfully to {markdown_file_path}!')
            
            # If user clicked "Save & Generate", redirect to generation
            if 'generate' in request.POST or request.POST.get('action') == 'generate':
                return redirect('generate_help_html')
            
            return redirect('edit_help_markdown')
            
        except Exception as e:
            messages.error(request, f'Error saving markdown file: {str(e)}')
            # Add more detailed error information
            import traceback
            print(f"Full error traceback: {traceback.format_exc()}")
    
    # Load existing markdown file
    try:
        if os.path.exists(markdown_file_path):
            with open(markdown_file_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        else:
            # Create default content if file doesn't exist
            template_content = """# Siren Web User Manual

## System Overview

Welcome to Siren Web - your renewable energy modeling platform.

## Getting Started

Follow these steps to begin using the system:

1. Login to your account
2. Select your scenario
3. Choose your analysis module

## Main Landing Page

The main landing page provides access to three core modules:
- Powermap
- Powermatch 
- Powerplot

*Edit this markdown file to customize your help documentation.*"""
            
            # Create the file with default content
            os.makedirs(os.path.dirname(markdown_file_path), exist_ok=True)
            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
                
    except Exception as e:
        template_content = f"Error loading markdown file: {str(e)}"
        messages.error(request, f'Error loading markdown file: {str(e)}')
    
    # Get file statistics
    file_stats = {}
    if os.path.exists(markdown_file_path):
        stat = os.stat(markdown_file_path)
        file_stats = {
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'lines': len(template_content.split('\n'))
        }
    
    context = {
        'template_content': template_content,
        'template_path': markdown_file_path,  # Match the template variable name
        'markdown_file_path': markdown_file_path,
        'file_exists': os.path.exists(markdown_file_path),
        'file_stats': file_stats,
        'backups_available': get_available_backups(markdown_file_path),
    }
    
    return render(request, 'edit_help.html', context)
def validate_markdown_content(content):
    """Validate markdown content for common issues"""
    errors = []
    
    # Check for basic markdown structure
    if not content.strip():
        errors.append("Content cannot be empty")
        return errors
    
    lines = content.split('\n')
    
    # Check for title
    has_h1 = any(line.startswith('# ') for line in lines)
    if not has_h1:
        errors.append("Document should start with a main title (# Title)")
    
    # Check for section headers
    h2_count = sum(1 for line in lines if line.startswith('## ') and not line.startswith('### '))
    if h2_count == 0:
        errors.append("Document should have section headers (## Section)")
    elif h2_count > 20:
        errors.append(f"Too many sections ({h2_count}). Consider consolidating for better pagination.")
    
    # Check for table of contents if it exists
    toc_lines = [line for line in lines if 'table of contents' in line.lower()]
    if toc_lines and h2_count > 0:
        # Basic TOC validation - just warn if structure seems off
        pass
    
    # Check for very long sections
    current_section_lines = 0
    max_section_lines = 0
    for line in lines:
        if line.startswith('## '):
            max_section_lines = max(max_section_lines, current_section_lines)
            current_section_lines = 0
        else:
            current_section_lines += 1
    
    if max_section_lines > 200:
        errors.append(f"Some sections are very long ({max_section_lines} lines). Consider breaking into subsections.")
    
    return errors

def create_markdown_backup(file_path):
    """Create a backup of the markdown file"""
    if os.path.exists(file_path):
        backup_dir = os.path.join(os.path.dirname(file_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'siren_web_manual_backup_{timestamp}.md'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        shutil.copy2(file_path, backup_path)
        
        # Keep only last 10 backups
        cleanup_old_backups(backup_dir, prefix='siren_web_manual_backup_')

def cleanup_old_backups(backup_dir, keep_count=10, prefix='help_backup_'):
    """Keep only the most recent backups"""
    try:
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith(prefix)]
        backup_files.sort(reverse=True)
        
        for old_backup in backup_files[keep_count:]:
            os.remove(os.path.join(backup_dir, old_backup))
            
    except Exception as e:
        print(f"Error cleaning up backups: {e}")

def get_available_backups(file_path):
    """Get list of available file backups"""
    backup_dir = os.path.join(os.path.dirname(file_path), 'backups')
    backups = []
    
    if os.path.exists(backup_dir):
        backup_files = [f for f in os.listdir(backup_dir) 
                       if f.startswith('siren_web_manual_backup_') and f.endswith('.md')]
        for backup_file in sorted(backup_files, reverse=True)[:5]:
            backup_path = os.path.join(backup_dir, backup_file)
            timestamp = os.path.getmtime(backup_path)
            backups.append({
                'filename': backup_file,
                'timestamp': datetime.fromtimestamp(timestamp),
                'path': backup_path,
                'size': os.path.getsize(backup_path)
            })
    
    return backups

@login_required
def restore_markdown_backup(request, backup_filename):
    """Restore markdown file from backup"""
    if request.method == 'POST':
        try:
            markdown_file_path = os.path.join(settings.BASE_DIR, 'siren_web_manual.md')
            backup_path = os.path.join(os.path.dirname(markdown_file_path), 'backups', backup_filename)
            
            if os.path.exists(backup_path) and backup_filename.endswith('.md'):
                # Create backup of current file before restoring
                create_markdown_backup(markdown_file_path)
                
                # Restore from backup
                shutil.copy2(backup_path, markdown_file_path)
                
                messages.success(request, f'Markdown file restored from backup: {backup_filename}')
            else:
                messages.error(request, 'Backup file not found or invalid')
                
        except Exception as e:
            messages.error(request, f'Error restoring backup: {str(e)}')
    
    return redirect('edit_help_markdown')

def preview_markdown_section(request):
    """AJAX endpoint to preview markdown sections"""
    if request.method == 'POST':
        try:
            content = request.POST.get('content', '')
            generator = SirenWebHelpGenerator()
            
            # Parse sections
            sections = generator.parse_markdown_sections(content)
            
            # Return section information
            section_info = []
            for i, section in enumerate(sections):
                word_count = len(section['content'].split())
                line_count = len(section['content'].split('\n'))
                
                section_info.append({
                    'index': i,
                    'title': section['title'],
                    'id': section['id'],
                    'word_count': word_count,
                    'line_count': line_count,
                    'preview': section['content'][:200] + '...' if len(section['content']) > 200 else section['content']
                })
            
            return JsonResponse({
                'success': True,
                'sections': section_info,
                'total_sections': len(sections)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})