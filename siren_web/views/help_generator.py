# gendocs/help_generator.py
import logging
import os
import re
from datetime import datetime
import markdown
from typing import List, Dict
logging.getLogger('MARKDOWN').setLevel(logging.WARNING)

class SirenWebHelpGenerator:
    """Enhanced generator that creates paginated HTML from markdown"""

    def __init__(self, module_name=None):
        self.markdown_file = None
        self.sections = []
        self.toc_items = []
        self.module_name = module_name  # Store module name for context
        
    def load_markdown_file(self, file_path: str) -> str:
        """Load markdown content from file"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Markdown file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content


    def parse_markdown_sections(self, content: str) -> tuple:
        """Parse markdown and build TOC from actual headers

        Structure:
        - # (h1) creates new sections/pages
        - First ## (h2) after h1 stays on same page as subsection
        - Subsequent ## (h2) create new sections/pages
        - ### (h3) are always subsections
        """
        sections = []
        toc_items = []
        current_section = None
        current_content = []
        current_subsections = []
        first_h2_after_h1 = False  # Track if we just saw an h1

        lines = content.split('\n')

        for line in lines:
            # Handle level 1 headings (# )
            if line.startswith('# ') and not line.startswith('## '):
                # Save previous section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content),
                        'id': self.create_section_id(current_section)
                    })
                    toc_items.append({
                        'title': current_section,
                        'id': self.create_section_id(current_section),
                        'index': len(sections) - 1,
                        'subsections': current_subsections.copy(),
                        'type': 'section'
                    })

                # Start new section with level 1 heading
                current_section = line[2:].strip()
                current_content = [line]
                current_subsections = []
                first_h2_after_h1 = True  # Next h2 should be a subsection

            # Handle level 2 headings (## )
            elif line.startswith('## ') and not line.startswith('### '):
                # Check if this is the first h2 after an h1
                if first_h2_after_h1:
                    # Add as subsection to current h1
                    subsection_title = line[3:].strip()
                    subsection_id = self.create_section_id(subsection_title)
                    current_subsections.append({
                        'title': subsection_title,
                        'id': subsection_id,
                        'type': 'subsection'
                    })
                    current_content.append(line)
                    first_h2_after_h1 = False  # Next h2 will be a new section
                else:
                    # Save previous section and start new one
                    if current_section:
                        sections.append({
                            'title': current_section,
                            'content': '\n'.join(current_content),
                            'id': self.create_section_id(current_section)
                        })
                        toc_items.append({
                            'title': current_section,
                            'id': self.create_section_id(current_section),
                            'index': len(sections) - 1,
                            'subsections': current_subsections.copy(),
                            'type': 'section'
                        })

                    # Start new section with level 2 heading
                    current_section = line[3:].strip()
                    current_content = [line]
                    current_subsections = []

            # Handle level 3 headings (### ) as subsections
            elif line.startswith('### ') and not line.startswith('#### '):
                # Add subsection to current section
                if current_section:
                    subsection_title = line[4:].strip()
                    subsection_id = self.create_section_id(subsection_title)
                    current_subsections.append({
                        'title': subsection_title,
                        'id': subsection_id,
                        'type': 'subsection'
                    })
                current_content.append(line)

            else:
                if current_section:
                    current_content.append(line)

        # Handle last section
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content),
                'id': self.create_section_id(current_section)
            })
            toc_items.append({
                'title': current_section,
                'id': self.create_section_id(current_section),
                'index': len(sections) - 1,
                'subsections': current_subsections.copy(),
                'type': 'section'
            })

        return sections, toc_items

    def create_section_id(self, title: str) -> str:
        """Create URL-friendly ID from section title"""
        return re.sub(r'[^a-zA-Z0-9\s]', '', title).replace(' ', '-').lower()
    
    def markdown_to_html(self, markdown_text: str) -> str:
        """Convert markdown to HTML using the markdown library"""       
        if not markdown_text or not markdown_text.strip():
            return "<p>No content available</p>"
        
        # Create markdown processor with extensions
        md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc'])
        
        # Convert to HTML
        html = md.convert(markdown_text)
        
        return html

    def generate_dynamic_toc_html(self, toc_items):
        """Generate TOC HTML from parsed headers"""
        toc_html = ""
        
        for item in toc_items:
            active_class = "active" if item['index'] == 0 else ""
            
            toc_html += f'''
            <li class="toc-item">
                <a href="#" class="toc-link {active_class}" data-section="{item['index']}">{item['title']}</a>'''
            
            # Add subsections
            if item.get('subsections'):
                toc_html += '<ul class="toc-subsections">'
                for subsection in item['subsections']:
                    toc_html += f'''
                    <li class="toc-subitem">
                        <a href="#" class="toc-sublink" data-section="{item['index']}" data-subsection="{subsection['id']}">{subsection['title']}</a>
                    </li>'''
                toc_html += '</ul>'
            
            toc_html += '</li>'
        
        return toc_html

    def generate_paginated_html(self, markdown_file_path: str, show_home_link=False) -> str:
        """Generate complete paginated HTML from markdown file

        Args:
            markdown_file_path: Path to the markdown file
            show_home_link: If True, show link back to main help index
        """
        markdown_content = self.load_markdown_file(markdown_file_path)

        # Parse sections and build dynamic TOC
        sections, toc_items = self.parse_markdown_sections(markdown_content)

        # Filter out TOC sections from main content
        filtered_sections = []
        for section in sections:
            section['index'] = len(filtered_sections)  # Reindex
            filtered_sections.append(section)

        # Convert to HTML
        html_sections = []
        for section in filtered_sections:
            html_content = self.markdown_to_html(section['content'])
            html_sections.append({
                'title': section['title'],
                'content': html_content,
                'id': section['id']
            })

        # Generate TOC HTML from the dynamic structure
        return self.create_complete_html(html_sections, toc_items, show_home_link)

    def create_complete_html(self, sections: List[Dict], toc_items: List[Dict], show_home_link=False) -> str:
        """Create the complete HTML document with pagination

        Args:
            sections: List of section dictionaries
            toc_items: List of TOC item dictionaries
            show_home_link: If True, show link back to main help index
        """

        # Generate TOC HTML
        toc_html = ""
        for item in toc_items:
            active_class = "active" if item['index'] == 0 else ""
            toc_html += f'''
                <li class="toc-item">
                    <a href="#" class="toc-link {active_class}" data-section="{item['index']}">{item['title']}</a>
                </li>'''

            # Add subsections if they exist
            if item.get('subsections'):
                toc_html += '<ul class="toc-subsections">'
                for subsection in item['subsections']:
                    toc_html += f'''
                    <li class="toc-subitem">
                        <a href="#" class="toc-sublink" data-section="{item['index']}" data-subsection="{subsection['id']}">{subsection['title']}</a>
                    </li>'''
                toc_html += '</ul>'

            toc_html += '</li>'
        
        # Generate sections HTML
        sections_html = ""
        for i, section in enumerate(sections):
            active_class = "active" if i == 0 else ""
            sections_html += f'''
            <div class="page-section {active_class}" data-section="{i}">
                {section['content']}
            </div>'''

        # Generate home link if requested
        home_link_html = ""
        if show_home_link:
            home_link_html = '''
            <div style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.2);">
                <a href="/help/" style="color: rgba(255,255,255,0.9); text-decoration: none; padding: 10px 15px; display: block; border-radius: 8px; background: rgba(255,255,255,0.1); transition: all 0.3s ease;">
                    ← Back to Main Help
                </a>
            </div>'''

        # Determine page title
        page_title = "Siren Web User Manual"
        if self.module_name:
            module_titles = {
                'powermap': 'Powermap Module',
                'powermatch': 'Powermatch Module',
                'powerplot': 'Powerplot Module',
                'terminal': 'Terminal Management',
                'aemo_scada': 'AEMO SCADA Data Fetcher',
                'system_overview': 'System Overview'
            }
            page_title = module_titles.get(self.module_name, 'Siren Web Help')

        # Complete HTML template
        html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background: #f8f9fa;
            color: #333;
        }}
        
        .container {{
            display: flex;
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            min-height: 100vh;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        
        .sidebar {{
            width: 350px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 25px;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
        }}
        
        .sidebar h2 {{
            margin-top: 0;
            color: #ffffff;
            border-bottom: 2px solid rgba(255,255,255,0.3);
            padding-bottom: 15px;
            font-size: 1.4em;
            font-weight: 600;
        }}
        
        .toc-list {{
            list-style: none;
            padding: 0;
            margin: 20px 0;
        }}
        
        .toc-item {{
            margin: 5px 0;
        }}
        
        .toc-link {{
            color: rgba(255,255,255,0.8);
            text-decoration: none;
            padding: 12px 15px;
            display: block;
            border-radius: 8px;
            transition: all 0.3s ease;
            font-weight: 500;
            border-left: 3px solid transparent;
        }}
        
        .toc-link:hover {{
            background: rgba(255,255,255,0.1);
            color: white;
            transform: translateX(5px);
            border-left-color: rgba(255,255,255,0.5);
        }}
        
        .toc-link.active {{
            background: rgba(255,255,255,0.2);
            color: white;
            border-left-color: #ffd700;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        .toc-subsections {{
            list-style: none;
            padding: 0;
            margin: 5px 0 0 20px;
        }}

        .toc-subitem {{
            margin: 3px 0;
        }}

        .toc-sublink {{
            color: rgba(255,255,255,0.6);
            text-decoration: none;
            padding: 6px 12px;
            display: block;
            border-radius: 5px;
            transition: all 0.3s ease;
            font-size: 0.9em;
            border-left: 2px solid transparent;
        }}

        .toc-sublink:hover {{
            background: rgba(255,255,255,0.05);
            color: rgba(255,255,255,0.8);
            border-left-color: rgba(255,255,255,0.3);
        }}
        .content {{
            flex: 1;
            padding: 40px 50px;
            position: relative;
            max-width: none;
        }}
        
        .page-section {{
            display: none;
            animation: fadeIn 0.4s ease-in;
        }}
        
        .page-section.active {{
            display: block !important;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .navigation {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: flex;
            gap: 15px;
            z-index: 1000;
        }}
        
        .nav-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 20px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            min-width: 120px;
        }}
        
        .nav-btn:hover:not(:disabled) {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }}
        
        .nav-btn:disabled {{
            background: #cbd5e0;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }}
        
        .back-to-top {{
            position: fixed;
            bottom: 120px;
            right: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px;
            border-radius: 50%;
            cursor: pointer;
            width: 55px;
            height: 55px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            font-size: 18px;
        }}
        
        .back-to-top:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }}
        
        .page-indicator {{
            position: fixed;
            top: 30px;
            right: 30px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 15px;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 600;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }}
        
        /* Content Styling */
        h1, h2, h3, h4, h5, h6 {{
            color: #2d3748;
            margin-top: 2em;
            margin-bottom: 1em;
        }}
        
        h1 {{
            font-size: 2.5em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 0.5em;
            margin-top: 0;
        }}
        
        h2 {{
            font-size: 2em;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.3em;
        }}
        
        h3 {{
            font-size: 1.5em;
            color: #667eea;
        }}
        
        p {{
            margin-bottom: 1.2em;
            text-align: justify;
        }}
        
        ul, ol {{
            margin-bottom: 1.2em;
            padding-left: 2em;
        }}
        
        li {{
            margin-bottom: 0.5em;
        }}
        
        code {{
            background: #f7fafc;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', 'Consolas', monospace;
            color: #e53e3e;
            border: 1px solid #e2e8f0;
        }}
        
        pre {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1.5em 0;
        }}
        
        pre code {{
            background: none;
            padding: 0;
            border: none;
            color: inherit;
        }}
        
        strong {{
            color: #2d3748;
            font-weight: 600;
        }}
        
        /* Mobile Responsive */
        @media (max-width: 768px) {{
            .container {{
                flex-direction: column;
            }}
            
            .sidebar {{
                width: 100%;
                height: auto;
                position: relative;
                padding: 20px;
            }}
            
            .content {{
                padding: 30px 20px;
            }}
            
            .navigation {{
                position: relative;
                bottom: auto;
                right: auto;
                justify-content: center;
                margin-top: 30px;
            }}
            
            .page-indicator {{
                position: relative;
                top: auto;
                right: auto;
                margin-bottom: 20px;
                display: inline-block;
            }}
            
            .back-to-top {{
                display: none;
            }}
        }}
        
        /* Print Styles */
        @media print {{
            .sidebar, .navigation, .back-to-top, .page-indicator {{
                display: none;
            }}
            
            .page-section {{
                display: block !important;
                page-break-after: always;
            }}
            
            .content {{
                width: 100%;
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <nav class="sidebar">
            <h2>📖 Table of Contents</h2>
            {home_link_html}
            <ul class="toc-list" id="tocList">
                {toc_html}
            </ul>
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); font-size: 0.9em;">
                <p><strong>Generated:</strong><br>{datetime.now().strftime('%B %d, %Y')}</p>
                <p><strong>Sections:</strong> {len(sections)}</p>
            </div>
        </nav>
        
        <main class="content">
            <div class="page-indicator">
                Page <span id="currentPage">1</span> of <span id="totalPages">{len(sections)}</span>
            </div>
            
            {sections_html}
        </main>
    </div>
    
    <div class="navigation">
        <button class="nav-btn" id="prevBtn" onclick="previousPage()">← Previous</button>
        <button class="nav-btn" id="nextBtn" onclick="nextPage()">Next →</button>
    </div>
    
    <button class="back-to-top" onclick="scrollToTop()" title="Back to top">↑</button>
    
    <script>
        let currentSection = 0;
        const totalSections = {len(sections)};
        
        function showSection(sectionIndex) {{
            // Hide all sections
            document.querySelectorAll('.page-section').forEach(section => {{
                section.classList.remove('active');
            }});
            
            // Show selected section
            const targetSection = document.querySelector(`.content .page-section[data-section="${{sectionIndex}}"]`);
            if (targetSection) {{
                targetSection.classList.add('active');
            }}
            
            // Update TOC active state
            document.querySelectorAll('.toc-link').forEach(link => {{
                link.classList.remove('active');
            }});
            const activeLink = document.querySelector(`[data-section="${{sectionIndex}}"]`);
            if (activeLink) {{
                activeLink.classList.add('active');
            }}
            
            // Update current section
            currentSection = sectionIndex;
            
            // Update page indicator
            document.getElementById('currentPage').textContent = sectionIndex + 1;
            
            // Update navigation buttons
            updateNavigationButtons();
            
            // Scroll to top of content
            document.querySelector('.content').scrollTop = 0;
            window.scrollTo(0, 0);
        }}
        
        function updateNavigationButtons() {{
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            
            prevBtn.disabled = currentSection === 0;
            nextBtn.disabled = currentSection === totalSections - 1;
        }}
        
        function nextPage() {{
            if (currentSection < totalSections - 1) {{
                showSection(currentSection + 1);
            }}
        }}
        
        function previousPage() {{
            if (currentSection > 0) {{
                showSection(currentSection - 1);
            }}
        }}
        
        function scrollToTop() {{
            showSection(0);
        }}
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowRight' || e.key === 'PageDown') {{
                nextPage();
                e.preventDefault();
            }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{
                previousPage();
                e.preventDefault();
            }}
        }});
        
                // TOC click handlers
        document.addEventListener("DOMContentLoaded", function () {{
            const tocLinks = document.querySelectorAll(".toc-link");
            const tocSubLinks = document.querySelectorAll(".toc-sublink");
            const pageSections = document.querySelectorAll(".page-section");
            const currentPage = document.getElementById("currentPage");

            // Handle main section navigation
            tocLinks.forEach(link => {{
                link.addEventListener("click", function (e) {{
                    e.preventDefault();

                    const sectionIndex = this.dataset.section;

                    // Activate the correct section
                    pageSections.forEach(sec => {{
                        sec.classList.toggle("active", sec.dataset.section === sectionIndex);
                    }});

                    // Update TOC link active state
                    tocLinks.forEach(l => l.classList.remove("active"));
                    this.classList.add("active");

                    // Update page number
                    if (currentPage) currentPage.textContent = parseInt(sectionIndex) + 1;

                    // Scroll to top smoothly
                    window.scrollTo({{ top: 0, behavior: "smooth" }});
                }});
            }});

            // Handle subsection navigation
            tocSubLinks.forEach(link => {{
                link.addEventListener("click", function (e) {{
                    e.preventDefault();

                    const sectionIndex = this.dataset.section;
                    const subsectionId = this.dataset.subsection;

                    // 1️⃣ Activate correct section first
                    pageSections.forEach(sec => {{
                        sec.classList.toggle("active", sec.dataset.section === sectionIndex);
                    }});

                    // 2️⃣ Delay scroll until browser has rendered section
                    setTimeout(() => {{
                        const target = document.getElementById(subsectionId);
                        if (target) {{
                            target.scrollIntoView({{ behavior: "smooth", block: "center" }});

                            // 3️⃣ Temporary highlight
                            target.style.transition = "background-color 0.5s ease";
                            const originalBg = target.style.backgroundColor;
                            target.style.backgroundColor = "#fffa9e"; // light yellow
                            setTimeout(() => {{
                                target.style.backgroundColor = originalBg;
                            }}, 1200);
                        }}
                    }}, 100); // wait a bit to ensure section is visible
                }});
            }});
        }});

    </script>
</body>
</html>'''
        
        return html_template
    
    def cleanup(self):
        """Cleanup any temporary files or resources"""
        pass