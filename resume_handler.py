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
    """Handles resume generation and optimization"""
    
    def __init__(self):
        self.gemini = GeminiService()
        self.logger = logging.getLogger(__name__)
        
    def generate_resume(self, job_details: Dict) -> Optional[str]:
        """Generate optimized resume for a job"""
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
            
            # Process sections
            sections_to_process = [
                'career_summary',
                'professional_summary', 
                'technical_skills',
                'work_experience'
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
                
            # Convert to DOCX using ResumeConverter implementation
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
    """Converts resume JSON to formatted DOCX document"""
    
    def __init__(self):
        self.doc = Document()
        self._setup_document()
        
    def _setup_document(self):
        """Setup document properties and styles"""
        # Set up margins (narrow)
        sections = self.doc.sections
        for section in sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)
            section.page_height = Inches(11)  # Letter size
            section.page_width = Inches(8.5)
        
        # Set up styles
        styles = self.doc.styles
        
        # Heading style (Times New Roman)
        style_heading = styles['Heading 1']
        font = style_heading.font
        font.name = 'Times New Roman'
        font.size = Pt(14)
        font.bold = True
        font.color.rgb = RGBColor(0, 0, 0)
        
        # Normal text style (Tahoma)
        style_normal = styles['Normal']
        font = style_normal.font
        font.name = 'Tahoma'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0, 0, 0)
        
        # Set up list style
        style_list = styles.add_style('Custom List', style_normal.type)
        font = style_list.font
        font.name = 'Tahoma'
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
        r.font.name = 'Tahoma'
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
        name_run.font.name = 'Times New Roman'
        name_run.font.bold = True
        
        p.add_run(' | ')
        
        # Email in middle with hyperlink
        self._add_hyperlink(p, header_data['email'].strip(), f"mailto:{header_data['email'].strip()}")
        
        p.add_run(' | ')
        
        # Phone on right
        phone_run = p.add_run(header_data['phone'])
        phone_run.font.name = 'Tahoma'
        
        # Second line: Citizenship and LinkedIn
        p = header.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Citizenship on left
        citizen_run = p.add_run(header_data['citizenship'])
        citizen_run.font.name = 'Tahoma'
        
        p.add_run(' | ')
        
        # LinkedIn on right with hyperlink
        linkedin_url = "https://" + header_data['linkedin'] if not header_data['linkedin'].startswith(('http://', 'https://')) else header_data['linkedin']
        self._add_hyperlink(p, header_data['linkedin'], linkedin_url)

    def _add_education(self, education_data: List[Dict]):
        """Add education section"""
        heading = self.doc.add_heading('Education', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Times New Roman'
        
        for edu in education_data:
            # University line
            p = self.doc.add_paragraph(style='Custom List')
            p.add_run('• ').bold = False
            univ_run = p.add_run(edu['university'])
            univ_run.bold = False
            
            # Degree line with spacing
            p = self.doc.add_paragraph(style='Custom List')
            p.paragraph_format.left_indent = Inches(0.5)
            p.paragraph_format.space_before = Pt(0)
            degree_run = p.add_run(edu['degree'])
            degree_run.bold = True
            p.add_run(f" in {edu['major']} ({edu['year']})").bold = False
            
            # Less space after each education entry
            p.paragraph_format.space_after = Pt(6)

    def _add_career_summary(self, summary_data: List[str]):
        """Add career summary section"""
        heading = self.doc.add_heading('Career Summary', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Times New Roman'
        
        for paragraph in summary_data:
            p = self.doc.add_paragraph()
            # Handle bold highlighting with ** markers
            parts = paragraph.split('**')
            for i, part in enumerate(parts):
                run = p.add_run(part)
                run.bold = i % 2 == 1  # Odd indices are bold
                run.font.name = 'Tahoma'

    def _add_professional_summary(self, summary_data: Dict):
        """Add professional summary section"""
        heading = self.doc.add_heading('Professional Summary', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Times New Roman'
        
        # Overview paragraph
        p = self.doc.add_paragraph()
        # Handle bold highlighting with ** markers
        parts = summary_data['overview'].split('**')
        for i, part in enumerate(parts):
            run = p.add_run(part)
            run.bold = i % 2 == 1
            run.font.name = 'Tahoma'
        
        # Bullet points
        for highlight in summary_data['highlights']:
            p = self.doc.add_paragraph(style='Custom List')
            p.add_run('• ')
            # Handle bold highlighting with ** markers
            parts = highlight.split('**')
            for i, part in enumerate(parts):
                run = p.add_run(part)
                run.bold = i % 2 == 1
                run.font.name = 'Tahoma'

    def _add_technical_skills(self, skills: Dict[str, List[str]]):
        """Add technical skills section with tabular format"""
        heading = self.doc.add_heading('Technical Skills', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Times New Roman'
        
        # Create table with exact number of rows needed
        num_skills = len(skills)
        table = self.doc.add_table(rows=num_skills, cols=2)
        table.style = 'Table Grid'
        table.autofit = True
        
        # Fill table
        for idx, (category, items) in enumerate(skills.items()):
            row = table.rows[idx].cells
            
            # Category name in first column
            category_name = category.replace('_', ' ').title()
            category_para = row[0].paragraphs[0]
            category_run = category_para.add_run(category_name)
            category_run.bold = True
            category_run.font.name = 'Tahoma'
            
            # Build skills list for second column
            skills_para = row[1].paragraphs[0]
            
            # Process each skill item to handle any bold formatting
            for i, skill in enumerate(items):
                if i > 0:
                    # Add comma separator between skills
                    skills_para.add_run(", ").font.name = 'Tahoma'
                
                # Check if the skill has bold formatting
                if '**' in skill:
                    parts = skill.split('**')
                    for j, part in enumerate(parts):
                        if part:  # Skip empty parts
                            run = skills_para.add_run(part)
                            run.bold = j % 2 == 1  # Odd indices are bold
                            run.font.name = 'Tahoma'
                else:
                    # No bold formatting, add as regular text
                    run = skills_para.add_run(skill)
                    run.font.name = 'Tahoma'
            
        # Set column widths
        table.columns[0].width = Inches(2.0)
        table.columns[1].width = Inches(5.0)

    def _add_work_experience(self, experiences: List[Dict]):
        """Add work experience section with specified layout"""
        heading = self.doc.add_heading('Work Experience', level=1)
        heading.style = self.doc.styles['Heading 1']
        for run in heading.runs:
            run.font.name = 'Times New Roman'
            
        # Add space after heading
        heading.paragraph_format.space_after = Pt(12)
        
        for exp in experiences:
            # Company name
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            company_run = p.add_run(exp['company'])
            company_run.bold = True
            company_run.font.name = 'Tahoma'
            
            # Location
            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            location_run = p.add_run(exp['location'])
            location_run.font.name = 'Tahoma'
            
            # Duration
            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            duration_run = p.add_run(exp['duration'])
            duration_run.italic = True
            duration_run.font.name = 'Tahoma'
            
            # Position
            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(6)
            position_run = p.add_run(exp['position'])
            position_run.bold = True
            position_run.font.name = 'Tahoma'
            
            # Summary paragraph
            if exp.get('summary'):
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(6)
                
                # Handle bold highlighting with ** markers
                parts = exp['summary'].split('**')
                for i, part in enumerate(parts):
                    run = p.add_run(part)
                    run.bold = i % 2 == 1
                    run.font.name = 'Tahoma'
            
            # Achievements
            for achievement in exp['achievements']:
                p = self.doc.add_paragraph(style='Custom List')
                p.paragraph_format.left_indent = Inches(0.25)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.add_run('• ')
                
                # Handle bold highlighting with ** markers
                parts = achievement.split('**')
                for i, part in enumerate(parts):
                    run = p.add_run(part)
                    run.bold = i % 2 == 1
                    run.font.name = 'Tahoma'
            
            # Environment (optional)
            if exp.get('environment'):
                p = self.doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.25)
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
                env_run = p.add_run('Environment: ')
                env_run.bold = True
                env_run.font.name = 'Tahoma'
                
                # Handle bold highlighting with ** markers
                parts = exp['environment'].split('**')
                for i, part in enumerate(parts):
                    run = p.add_run(part)
                    run.bold = i % 2 == 1
                    run.font.name = 'Tahoma'
                    
            # Add spacing after each experience entry
            self.doc.add_paragraph().paragraph_format.space_after = Pt(12)

    def convert_resume(self, resume_data: Dict):
        """Convert full resume from JSON data to DOCX"""
        # Create header
        self._create_header(resume_data['header'])
        
        # Add Education
        self._add_education(resume_data['education'])
        
        # Add Career Summary
        self._add_career_summary(resume_data['career_summary'])
        
        # Add Professional Summary
        self._add_professional_summary(resume_data['professional_summary'])
        
        # Add Technical Skills
        self._add_technical_skills(resume_data['technical_skills'])
        
        # Add Work Experience
        self._add_work_experience(resume_data['work_experience'])

    def save(self, filename: str):
        """Save the document"""
        self.doc.save(filename)