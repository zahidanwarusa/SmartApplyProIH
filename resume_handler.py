import json
import logging
import time
import re
import os
from pathlib import Path
from typing import Dict, Optional, List, Union
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
import docx.oxml.shared
from docx.opc.constants import RELATIONSHIP_TYPE

from config import DEFAULT_RESUME, RESUME_DIR
from gemini_service import GeminiService

class ResumeHandler:
    """Handles resume generation and optimization for the new v2 format"""
    
    def __init__(self):
        self.gemini = GeminiService()
        self.logger = logging.getLogger(__name__)
        
    def generate_resume(self, job_details: Dict) -> Optional[str]:
        """Generate optimized resume for a job using the new v2 format"""
        try:
            # Load default resume
            if not DEFAULT_RESUME.exists():
                self.logger.error("Default resume template not found")
                return None
                
            with open(DEFAULT_RESUME, 'r') as f:
                resume_data = json.load(f)
                
            # Create output directories
            RESUME_DIR.mkdir(parents=True, exist_ok=True)
            
            # Log details for debugging
            self.logger.info(f"Processing resume for job: {job_details.get('title', 'Unknown')}")
            
            # Process sections for new v2 format
            sections_to_process = [
                'professional_summary',
                'core_competencies', 
                'professional_experience'
            ]
            
            for section_name in sections_to_process:
                if section_name in resume_data:
                    self.logger.info(f"Optimizing {section_name}...")
                    try:
                        updated_section = self.gemini.optimize_resume_section(
                            section_name,
                            resume_data[section_name],
                            job_details
                        )
                        
                        if updated_section:
                            # Deep comparison with original before replacing
                            original_normalized = json.dumps(self._normalize_content(resume_data[section_name]))
                            updated_normalized = json.dumps(self._normalize_content(updated_section))
                            
                            if original_normalized != updated_normalized:
                                resume_data[section_name] = updated_section
                                self.logger.info(f"Successfully updated {section_name} with meaningful changes")
                            else:
                                self.logger.warning(f"No significant changes detected for {section_name}")
                        else:
                            self.logger.warning(f"No valid response for {section_name}, keeping original")
                    except Exception as e:
                        self.logger.error(f"Error updating {section_name}: {str(e)}")
                    
                    # Avoid rate limiting
                    time.sleep(2)
            
            # Generate resume filename
            base_filename = self._create_professional_filename(job_details)
            
            # Ensure filename is unique
            resume_filename = self._ensure_unique_filename(base_filename, ".docx")
            json_filename = self._ensure_unique_filename(base_filename, ".json")
            
            # Generate files
            resume_path = RESUME_DIR / resume_filename
            json_path = RESUME_DIR / json_filename
            
            # Save JSON for reference
            with open(json_path, 'w') as f:
                json.dump(resume_data, f, indent=2)
                
            # Convert to DOCX using updated ResumeConverter
            converter = ResumeConverter()
            converter.convert_resume(resume_data)
            converter.save(str(resume_path))
            
            self.logger.info(f"Resume saved to {resume_path}")
            return str(resume_path)
            
        except Exception as e:
            self.logger.error(f"Error generating resume: {str(e)}")
            return None
            
    def _normalize_content(self, content):
        """Normalize content for comparison by removing formatting markers"""
        if isinstance(content, list):
            return [self._normalize_text(item) if isinstance(item, str) else self._normalize_content(item) for item in content]
        elif isinstance(content, dict):
            return {key: self._normalize_content(value) for key, value in content.items()}
        elif isinstance(content, str):
            return self._normalize_text(content)
        else:
            return content
    
    def _normalize_text(self, text):
        """Normalize text by removing bold markers and extra whitespace"""
        if not isinstance(text, str):
            return text
        # Remove bold markers
        text = re.sub(r'\*\*', '', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
            
    def _create_professional_filename(self, job_details: Dict) -> str:
        """Create a professional resume filename based on job details"""
        # Extract job title (avoid using company name)
        job_title = job_details.get('title', 'Job').strip()
        
        # Clean up the job title for the filename
        # Extract important keywords for role type
        role_keywords = ['SDET', 'QA', 'Test', 'Quality', 'Automation', 'Engineer', 'Lead', 'Senior', 'Manager', 'Business', 'Analyst', 'BA', 'Tester']
        
        # Find matching keywords in the job title
        role_parts = []
        for keyword in role_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', job_title, re.IGNORECASE):
                role_parts.append(keyword)
        
        # If no keywords found, use a generic "Role"
        if not role_parts:
            role_type = "QA"
        else:
            # Join found keywords to create role type
            role_type = "_".join(role_parts)
        
        # Create a standardized filename
        return f"{role_type}_Resume_Zahid_Anwar"
        
    def _create_filename_slug(self, text: str) -> str:
        """Create a filename-friendly slug from text"""
        # Replace spaces with underscores and remove special characters
        slug = re.sub(r'[^a-zA-Z0-9_]', '', text.replace(' ', '_'))
        # Limit length
        return slug[:30] if slug else "Untitled"
        
    def _ensure_unique_filename(self, base_filename: str, extension: str) -> str:
        """Ensure filename is unique by adding a counter if needed"""
        filename = f"{base_filename}{extension}"
        counter = 1
        
        while (RESUME_DIR / filename).exists():
            # Add version number for better tracking
            filename = f"{base_filename}_v{counter}{extension}"
            counter += 1
            
        return filename


class ResumeConverter:
    """Converts resume JSON to formatted DOCX document using new v2 format"""
    
    def __init__(self):
        self.doc = Document()
        self._setup_document()
        
    def _setup_document(self):
        """Setup document properties and styles with correct fonts"""
        # Set up margins (narrow)
        sections = self.doc.sections
        for section in sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)
            section.page_height = Inches(11)  # Letter size
            section.page_width = Inches(8.5)
        
        # Set up styles with user-specified fonts
        styles = self.doc.styles
        
        # Heading style (Tahoma as requested)
        style_heading = styles['Heading 1']
        font = style_heading.font
        font.name = 'Tahoma'
        font.size = Pt(14)
        font.bold = True
        font.color.rgb = RGBColor(0, 0, 0)
        
        # Normal text style (Calibri as requested)
        style_normal = styles['Normal']
        font = style_normal.font
        font.name = 'Calibri'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0, 0, 0)
        
        # Set up list style
        style_list = styles.add_style('Custom List', style_normal.type)
        font = style_list.font
        font.name = 'Calibri'
        font.size = Pt(11)
        paragraph_format = style_list.paragraph_format
        paragraph_format.left_indent = Inches(0.25)
        paragraph_format.space_before = Pt(0)
        paragraph_format.space_after = Pt(6)

    def _add_hyperlink(self, paragraph, text, url):
        """Add a hyperlink to a paragraph"""
        # This gets access to the document.xml.rels file and gets a new relation id value
        part = paragraph.part
        r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

        # Create the w:hyperlink tag and add needed values
        hyperlink = docx.oxml.shared.OxmlElement('w:hyperlink')
        hyperlink.set(docx.oxml.shared.qn('r:id'), r_id)

        # Create a w:r element and a new w:rPr element
        new_run = docx.oxml.shared.OxmlElement('w:r')
        rPr = docx.oxml.shared.OxmlElement('w:rPr')

        # Join all the xml elements together add add the required text to the w:r element
        new_run.append(rPr)
        new_run.text = text
        hyperlink.append(new_run)

        # Create a new Run object and add the hyperlink into it
        r = paragraph.add_run()
        r._r.append(hyperlink)
        r.font.name = 'Calibri'
        r.font.color.rgb = RGBColor(0, 0, 255)
        
        return r

    def _create_header(self, header_data: Dict):
        """Create document header section"""
        section = self.doc.sections[0]
        header = section.header
        
        # First line: Name, Email, Phone
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Name on left
        name_run = p.add_run(header_data['name'])
        name_run.font.name = 'Tahoma'
        name_run.font.bold = True
        name_run.font.size = Pt(12)
        
        p.add_run(' | ')
        
        # Email in middle with hyperlink
        self._add_hyperlink(p, header_data['email'].strip(), f"mailto:{header_data['email'].strip()}")
        
        p.add_run(' | ')
        
        # Phone on right
        phone_run = p.add_run(header_data['phone'])
        phone_run.font.name = 'Calibri'
        
        # Second line: Citizenship and LinkedIn
        p = header.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Citizenship on left
        citizen_run = p.add_run(header_data['citizenship'])
        citizen_run.font.name = 'Calibri'
        
        p.add_run(' | ')
        
        # LinkedIn on right with hyperlink
        linkedin_url = "https://" + header_data['linkedin'] if not header_data['linkedin'].startswith(('http://', 'https://')) else header_data['linkedin']
        self._add_hyperlink(p, header_data['linkedin'], linkedin_url)

    def _add_professional_summary(self, summary_data: Dict):
        """Add the new unified professional summary section"""
        heading = self.doc.add_heading('PROFESSIONAL SUMMARY', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Tahoma'
            run.font.bold = True
        
        # Title and experience line
        p = self.doc.add_paragraph()
        self._add_formatted_text(p, summary_data.get('title_experience', ''))
        p.paragraph_format.space_after = Pt(6)
        
        # Track record line
        p = self.doc.add_paragraph()
        self._add_formatted_text(p, summary_data.get('track_record', ''))
        p.paragraph_format.space_after = Pt(6)
        
        # Expertise line
        p = self.doc.add_paragraph()
        self._add_formatted_text(p, summary_data.get('expertise', ''))
        p.paragraph_format.space_after = Pt(6)
        
        # Core value line (with "Core Value:" prefix)
        p = self.doc.add_paragraph()
        core_value_run = p.add_run('Core Value: ')
        core_value_run.font.name = 'Calibri'
        core_value_run.font.bold = True
        
        self._add_formatted_text(p, summary_data.get('core_value', ''))
        p.paragraph_format.space_after = Pt(12)

    def _add_core_competencies(self, competencies: Dict):
        """Add the detailed core competencies section"""
        heading = self.doc.add_heading('CORE COMPETENCIES', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Tahoma'
            run.font.bold = True
        
        # Category mappings for proper display names
        category_display_names = {
            'programming_and_automation': 'Programming & Automation',
            'testing_frameworks': 'Testing Frameworks',
            'cloud_and_devops': 'Cloud & DevOps',
            'api_and_performance': 'API & Performance',
            'quality_tools': 'Quality Tools',
            'databases': 'Databases',
            'domain_expertise': 'Domain Expertise',
            'leadership': 'Leadership'
        }
        
        for category_key, skills in competencies.items():
            if not skills:  # Skip empty categories
                continue
                
            p = self.doc.add_paragraph()
            
            # Add category name in bold
            display_name = category_display_names.get(category_key, category_key.replace('_', ' ').title())
            category_run = p.add_run(f'{display_name}: ')
            category_run.font.name = 'Calibri'
            category_run.font.bold = True
            
            # Add skills separated by bullet points
            for i, skill in enumerate(skills):
                if i > 0:
                    bullet_run = p.add_run(' • ')
                    bullet_run.font.name = 'Calibri'
                
                # Handle bold formatting in skills
                self._add_formatted_text(p, skill)
            
            p.paragraph_format.space_after = Pt(6)

    def _add_professional_experience(self, experiences: List[Dict]):
        """Add professional experience section with new format"""
        heading = self.doc.add_heading('PROFESSIONAL EXPERIENCE', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Tahoma'
            run.font.bold = True
            
        # Add space after heading
        heading.paragraph_format.space_after = Pt(12)
        
        for exp in experiences:
            # Company name and location on same line with separator
            p = self.doc.add_paragraph()
            company_run = p.add_run(f"{exp['company']} | {exp['location']}")
            company_run.bold = True
            company_run.font.name = 'Calibri'
            company_run.font.size = Pt(12)
            p.paragraph_format.space_after = Pt(2)
            
            # Position and duration on same line
            p = self.doc.add_paragraph()
            position_run = p.add_run(f"{exp['position']} | {exp['duration']}")
            position_run.bold = True
            position_run.font.name = 'Calibri'
            p.paragraph_format.space_after = Pt(6)
            
            # Summary paragraph
            if exp.get('summary'):
                p = self.doc.add_paragraph()
                self._add_formatted_text(p, exp['summary'])
                p.paragraph_format.space_after = Pt(6)
            
            # Key achievements (if present)
            if exp.get('key_achievements'):
                for achievement in exp['key_achievements']:
                    p = self.doc.add_paragraph(style='Custom List')
                    p.paragraph_format.left_indent = Inches(0)
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    
                    bullet_run = p.add_run('• ')
                    bullet_run.font.name = 'Calibri'
                    
                    self._add_formatted_text(p, achievement)
            
            # Detailed achievements
            if exp.get('detailed_achievements'):
                for achievement in exp['detailed_achievements']:
                    p = self.doc.add_paragraph(style='Custom List')
                    p.paragraph_format.left_indent = Inches(0)
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    
                    bullet_run = p.add_run('• ')
                    bullet_run.font.name = 'Calibri'
                    
                    self._add_formatted_text(p, achievement)
            
            # Environment (if present)
            if exp.get('environment'):
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
                env_run = p.add_run('Environment: ')
                env_run.bold = True
                env_run.font.name = 'Calibri'
                
                self._add_formatted_text(p, exp['environment'])
                    
            # Add spacing after each experience entry
            self.doc.add_paragraph().paragraph_format.space_after = Pt(12)

    def _add_education(self, education_data: List[Dict]):
        """Add education section"""
        heading = self.doc.add_heading('EDUCATION', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Tahoma'
            run.font.bold = True
        
        for edu in education_data:
            p = self.doc.add_paragraph()
            
            # Format: MBA, Information Technology | Strayer University, USA (2016)
            degree_run = p.add_run(f"{edu['degree']}, {edu['major']}")
            degree_run.font.name = 'Calibri'
            degree_run.font.bold = True
            
            separator_run = p.add_run(' | ')
            separator_run.font.name = 'Calibri'
            
            university_run = p.add_run(f"{edu['university']} ({edu['year']})")
            university_run.font.name = 'Calibri'
            
            p.paragraph_format.space_after = Pt(6)

    def _add_formatted_text(self, paragraph, text):
        """Add text to paragraph with proper bold formatting"""
        if not text:
            return
            
        # Handle bold highlighting with ** markers
        parts = text.split('**')
        for i, part in enumerate(parts):
            if part:  # Skip empty parts
                run = paragraph.add_run(part)
                run.bold = i % 2 == 1  # Odd indices are bold
                run.font.name = 'Calibri'

    def convert_resume(self, resume_data: Dict):
        """Convert full resume from JSON data to DOCX using new v2 format"""
        # Create header
        self._create_header(resume_data['header'])
        
        # Add Professional Summary (new unified section)
        self._add_professional_summary(resume_data['professional_summary'])
        
        # Add Core Competencies (replaces technical skills)
        self._add_core_competencies(resume_data['core_competencies'])
        
        # Add Professional Experience
        self._add_professional_experience(resume_data['professional_experience'])
        
        # Add Education
        self._add_education(resume_data['education'])

    def save(self, filename: str):
        """Save the document"""
        self.doc.save(filename)