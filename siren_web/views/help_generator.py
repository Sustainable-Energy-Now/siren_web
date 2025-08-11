# powermap_docs/help_generator.py
import os
import tempfile
import shutil
import base64
from jinja2 import Template
import markdown
import re
from datetime import datetime
from django.conf import settings

class SirenWebHelpGenerator:
    def __init__(self):
        self.temp_image_dir = tempfile.mkdtemp()
        self.help_template = self._load_help_template()

    def _load_help_template(self) -> str | Template:
        """Load markdown template from media/templates/help/help.md"""
        # Construct the path to the template file
        template_path = os.path.join(
            settings.MEDIA_ROOT, 
            'templates', 
            'help', 
            'help.md'
        )
        
        try:
            # Check if the file exists
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                print(f"Successfully loaded template from: {template_path}")
                return template_content
            else:
                print(f"Template file not found at: {template_path}")
                return ''

        except Exception as e:
            print(f"Error loading template file: {e}")
            print("Using fallback template...")
            return ''
       
    def generate_help_html(self):
        """Generate complete help HTML"""
        try:
            # Prepare context
            context = {
                'generation_date': datetime.now().strftime('%B %d, %Y at %I:%M %p')
            }
            
            # Render template
            template = Template(self.help_template)
            rendered_md = template.render(**context)
            
            # Convert to HTML without full HTML document structure
            return self._markdown_to_html_content_only(rendered_md)
            
        except Exception as e:
            return self._create_error_html(str(e))
    
    def _markdown_to_html_content_only(self, markdown_content):
        """Convert markdown to HTML content only (no html/head/body tags)"""
        def embed_image(match):
            alt_text = match.group(1)
            image_path = match.group(2)
            
            try:
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as img_file:
                        img_data = img_file.read()
                        img_base64 = base64.b64encode(img_data).decode()
                    
                    return f'<img src="data:image/png;base64,{img_base64}" alt="{alt_text}" style="max-width: 100%; height: auto; margin: 10px 0;">'
                else:
                    return f'<p><em>[Image not found: {alt_text}]</em></p>'
            except Exception as e:
                return f'<p><em>[Error loading image: {alt_text}]</em></p>'
        
        # Replace images
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        html_with_images = re.sub(image_pattern, embed_image, markdown_content)
        
        # Convert to HTML (content only)
        html = markdown.markdown(html_with_images, extensions=['tables', 'toc'])
        
        return html
       
    def _create_error_html(self, error_message):
        """Create error HTML if generation fails"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Help Generation Error</title></head>
        <body>
            <h1>Error Generating Help Documentation</h1>
            <p>An error occurred while generating the help documentation:</p>
            <pre>{error_message}</pre>
            <p><a href="javascript:history.back()">Go Back</a></p>
        </body>
        </html>
        """
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            if os.path.exists(self.temp_image_dir):
                shutil.rmtree(self.temp_image_dir)
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")
