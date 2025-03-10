import json
import logging
import os
import re
import time
from pathlib import Path
import google.generativeai as genai
from config import GEMINI_API_KEYS, DATA_DIR, API_DAILY_LIMIT, API_WARNING_THRESHOLD
from api_key_manager import APIKeyManager

class GeminiService:
    """Handles all interactions with Gemini AI with robust response handling and API key rotation"""
    
    def __init__(self):
        # Initialize logger first
        self.logger = logging.getLogger(__name__)
        
        # Create debug directory for response analysis
        self.debug_dir = Path('debug')
        self.debug_dir.mkdir(exist_ok=True)
        
        # Initialize the API key manager
        self.api_key_manager = APIKeyManager(
            GEMINI_API_KEYS, 
            DATA_DIR, 
            daily_limit=API_DAILY_LIMIT, 
            warning_threshold=API_WARNING_THRESHOLD
        )
        
        # Setup Gemini (now the logger is available)
        self.setup_gemini()
        
    def setup_gemini(self):
        """Initialize Gemini AI with current API key"""
        current_key = self.api_key_manager.get_current_key()
        genai.configure(api_key=current_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.logger.info("Configured Gemini with current API key")

    def _handle_api_error(self, error):
        """Handle API errors, particularly rate limit errors"""
        error_str = str(error)
        
        # Check if this is a rate limit or quota exceeded error
        rate_limit_patterns = [
            "rate limit",
            "quota exceeded",
            "resource exhausted",
            "limit exceeded",
            "too many requests"
        ]
        
        is_rate_limit = any(pattern in error_str.lower() for pattern in rate_limit_patterns)
        
        if is_rate_limit:
            self.logger.warning(f"API rate limit reached: {error_str}")
            
            # Try to rotate to next key
            if self.api_key_manager.increment_usage():
                self.setup_gemini()  # Reconfigure with new key
                return True  # Key rotation successful
            else:
                self.logger.error("All API keys have reached their daily limit")
                return False  # All keys exhausted
        
        # Some other API error
        self.logger.error(f"API error (not rate-limit related): {error_str}")
        return None  # Not a rate limit error

    def make_api_call(self, prompt, max_retries=2, **kwargs):
        """Make an API call with retry logic for rate limits"""
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Increment usage counter before making the call
                if not self.api_key_manager.increment_usage():
                    self.logger.error("All API keys have reached their daily limit")
                    return None
                
                response = self.model.generate_content(prompt, **kwargs)
                return response
                
            except Exception as e:
                result = self._handle_api_error(e)
                
                if result is True:
                    # Rate limit error, but successfully rotated to new key
                    retry_count += 1
                    self.logger.info(f"Retrying with new API key (attempt {retry_count}/{max_retries})")
                    time.sleep(1)  # Brief pause before retry
                    continue
                    
                elif result is False:
                    # All keys exhausted
                    self.logger.error("All API keys exhausted, cannot proceed")
                    return None
                    
                else:
                    # Not a rate limit error - don't retry
                    self.logger.error(f"API call failed: {str(e)}")
                    return None
                    
        # Max retries reached
        self.logger.error(f"Max retries ({max_retries}) reached for API call")
        return None

    def optimize_resume_section(self, section_name: str, current_content, job_details: dict):
        """Main method to optimize a resume section based on job details"""
        try:
            # Format the prompt based on section type
            if section_name == 'career_summary':
                prompt = self._create_career_summary_prompt(current_content, job_details)
            elif section_name == 'professional_summary':
                prompt = self._create_professional_summary_prompt(current_content, job_details)
            elif section_name == 'technical_skills':
                prompt = self._create_technical_skills_prompt(current_content, job_details)
            elif section_name == 'work_experience':
                # Work experience is handled differently - we optimize each job separately
                return self._optimize_work_experience(current_content, job_details)
            else:
                self.logger.warning(f"Unknown section: {section_name}, skipping optimization")
                return current_content
            
            # Save the prompt for debugging
            with open(self.debug_dir / f"{section_name}_prompt.txt", 'w') as f:
                f.write(prompt)
                
            # Get response from Gemini with API key rotation
            response = self.make_api_call(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    top_p=1,
                    top_k=1,
                    max_output_tokens=2048,
                )
            )
            
            if not response or not hasattr(response, 'text') or not response.text.strip():
                self.logger.warning(f"No response received for {section_name}")
                return current_content
            
            # Save the raw response for debugging
            with open(self.debug_dir / f"{section_name}_response.txt", 'w') as f:
                f.write(response.text)
                
            # Process the response based on section type
            if section_name == 'career_summary':
                updated_content = self._process_career_summary_response(response.text, current_content)
            elif section_name == 'professional_summary':
                updated_content = self._process_professional_summary_response(response.text, current_content)
            elif section_name == 'technical_skills':
                updated_content = self._process_technical_skills_response(response.text, current_content)
            else:
                updated_content = current_content
                
            # Save the processed content for debugging
            with open(self.debug_dir / f"{section_name}_processed.json", 'w') as f:
                json.dump(updated_content, f, indent=2)
            
            # Compare original and updated content
            original_normalized = json.dumps(self._normalize_content(current_content))
            updated_normalized = json.dumps(self._normalize_content(updated_content))
            
            if updated_normalized != original_normalized:
                self.logger.info(f"Successfully updated {section_name} with meaningful changes")
            else:
                self.logger.warning(f"No significant changes in {section_name} after processing")
                
            return updated_content
            
        except Exception as e:
            self.logger.error(f"Error optimizing {section_name}: {str(e)}")
            return current_content
    
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
            
    def _create_career_summary_prompt(self, current_content, job_details):
        """Create prompt for career summary optimization"""
        # Make skills a comma-separated string
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize a career summary for a resume. The summary should highlight experience and skills relevant to the job description.

        Current Career Summary:
        {json.dumps(current_content, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Maintain the same number of paragraphs ({len(current_content)})
        2. Use ** to highlight key terms relevant to the job (Example: **automation testing**)
        3. Keep each paragraph under 4 lines of text
        4. Do not use quotation marks around the paragraphs
        5. Return your output in the exact format of the input (valid JSON array)
        6. Your response should be a valid JSON array that can be directly parsed

        For example, your response should look like:
        [
          "First paragraph with **highlighted terms**...",
          "Second paragraph with more **relevant skills**...",
          "Third paragraph with additional **important experience**..."
        ]

        IMPORTANT: Return ONLY the JSON array with the updated content, no other explanation or text before or after it.
        """
        
        return prompt
        
    def _process_career_summary_response(self, response_text, original_content):
        """Process and extract career summary content from response"""
        try:
            # Try to parse as JSON array first
            try:
                # Extract JSON array pattern if present
                array_match = re.search(r'\[\s*".*"\s*(?:,\s*".*"\s*)*\]', response_text, re.DOTALL)
                if array_match:
                    extracted_array = array_match.group(0)
                    try:
                        content = json.loads(extracted_array)
                        if isinstance(content, list) and all(isinstance(item, str) for item in content):
                            # Process paragraphs to ensure proper formatting
                            processed_content = []
                            for paragraph in content:
                                # Clean paragraph text
                                paragraph = paragraph.replace('\\"', '"')
                                paragraph = re.sub(r'\\n', ' ', paragraph)
                                paragraph = re.sub(r'\s+', ' ', paragraph).strip()
                                
                                # Ensure bold markers are properly formatted
                                paragraph = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', paragraph)
                                processed_content.append(paragraph)
                            
                            # Ensure we keep the same number of paragraphs
                            result = processed_content[:len(original_content)]
                            while len(result) < len(original_content):
                                result.append(original_content[len(result)])
                            
                            # Check for actual changes
                            if self._normalize_content(result) != self._normalize_content(original_content):
                                self.logger.info("Successfully updated career summary content")
                                return result
                            else:
                                self.logger.warning("No meaningful changes to career summary content")
                                return original_content
                    except json.JSONDecodeError:
                        self.logger.warning("Extracted array isn't valid JSON, continuing...")
                
                # Try to parse the whole response as JSON
                content = json.loads(response_text)
                
                if isinstance(content, list) and all(isinstance(item, str) for item in content):
                    # Process paragraphs
                    processed_content = []
                    for paragraph in content:
                        # Clean paragraph text
                        paragraph = paragraph.replace('\\"', '"')
                        paragraph = re.sub(r'\\n', ' ', paragraph)
                        paragraph = re.sub(r'\s+', ' ', paragraph).strip()
                        
                        # Ensure bold markers are properly formatted
                        paragraph = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', paragraph)
                        processed_content.append(paragraph)
                    
                    # Ensure we keep the same number of paragraphs
                    result = processed_content[:len(original_content)]
                    while len(result) < len(original_content):
                        result.append(original_content[len(result)])
                    
                    # Check for actual changes
                    if self._normalize_content(result) != self._normalize_content(original_content):
                        self.logger.info("Successfully updated career summary content")
                        return result
                    else:
                        self.logger.warning("No meaningful changes to career summary content")
                        return original_content
            except json.JSONDecodeError:
                self.logger.warning("JSON parsing failed for career summary, falling back to regex extraction")
            
            # If JSON parsing failed, extract paragraphs with regex
            clean_text = self._clean_json_string(response_text)
            paragraphs = []
            
            # Extract quoted strings that look like paragraphs
            paragraph_matches = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', clean_text)
            if paragraph_matches:
                for paragraph in paragraph_matches:
                    # Clean paragraph text
                    paragraph = paragraph.replace('\\"', '"')
                    paragraph = re.sub(r'\\n', ' ', paragraph)
                    paragraph = re.sub(r'\s+', ' ', paragraph).strip()
                    
                    # Skip short strings or list markers
                    if len(paragraph) > 20 and not paragraph.startswith(('- ', '* ', '•')):
                        # Ensure bold markers are properly formatted
                        paragraph = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', paragraph)
                        paragraphs.append(paragraph)
            
            # If we didn't find paragraphs with quotes, try line-based approach
            if not paragraphs:
                lines = response_text.split('\n')
                current_paragraph = ""
                
                for line in lines:
                    line = line.strip()
                    # Skip empty lines, JSON markers, and code block markers
                    if not line or line in ('```json', '```', '[', ']', '{', '}'):
                        if current_paragraph:
                            # Clean paragraph text
                            paragraph = current_paragraph.strip()
                            paragraph = re.sub(r'\s+', ' ', paragraph)
                            
                            # Ensure bold markers are properly formatted
                            paragraph = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', paragraph)
                            paragraphs.append(paragraph)
                            current_paragraph = ""
                    else:
                        current_paragraph += " " + line
                
                # Add the last paragraph if there is one
                if current_paragraph:
                    paragraph = current_paragraph.strip()
                    paragraph = re.sub(r'\s+', ' ', paragraph)
                    
                    # Ensure bold markers are properly formatted
                    paragraph = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', paragraph)
                    paragraphs.append(paragraph)
            
            # If we found some paragraphs, use them
            if paragraphs:
                # Remove duplicates while preserving order
                unique_paragraphs = []
                seen = set()
                for p in paragraphs:
                    normalized = self._normalize_text(p)
                    if normalized not in seen and len(p) > 20:  # Only keep substantive paragraphs
                        seen.add(normalized)
                        unique_paragraphs.append(p)
                
                # Ensure we keep the same number of paragraphs
                result = unique_paragraphs[:len(original_content)]
                while len(result) < len(original_content):
                    result.append(original_content[len(result)])
                
                # Check for actual changes
                if self._normalize_content(result) != self._normalize_content(original_content):
                    self.logger.info("Successfully extracted career summary with regex")
                    return result
            
            # If we couldn't extract anything useful, keep the original
            self.logger.warning("Could not extract useful career summary paragraphs")
            return original_content
        except Exception as e:
            self.logger.error(f"Error processing career summary response: {str(e)}")
            return original_content
            
    def _create_professional_summary_prompt(self, current_content, job_details):
        """Create prompt for professional summary optimization"""
        # Make skills a comma-separated string
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize a professional summary for a resume to highlight experiences and skills relevant to the following job.

        Current Professional Summary:
        {json.dumps(current_content, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Keep the same exact structure with an "overview" and "highlights" array
        2. Optimize the overview paragraph to emphasize relevance to the job
        3. Choose and optimize the most relevant highlights (keep all of them)
        4. Use ** to highlight key terms relevant to the job (Example: **automation testing**)
        5. Remove any escape characters and unwanted symbols
        6. Your output must be a valid JSON object that can be parsed directly
        
        IMPORTANT: Return ONLY the JSON object with the updated content, no other explanation or text before or after it.
        
        For example, your response should look exactly like:
        {{
          "overview": "Overview paragraph with **highlighted terms**...",
          "highlights": [
            "First highlight with **key skills**...",
            "Second highlight with more **relevant experience**..."
          ]
        }}
        """
        
        return prompt
        
    def _process_professional_summary_response(self, response_text, original_content):
        """Process and extract professional summary content from response"""
        try:
            # Try to extract JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_text = json_match.group(0)
                
                try:
                    # Try to parse the extracted JSON
                    content = json.loads(json_text)
                    
                    # Check if the content has the expected structure
                    if isinstance(content, dict) and 'overview' in content and 'highlights' in content:
                        # Clean overview text
                        overview = content['overview']
                        overview = re.sub(r'\\n', ' ', overview)
                        overview = re.sub(r'\s+', ' ', overview).strip()
                        
                        # Clean highlights
                        highlights = []
                        for highlight in content['highlights']:
                            # Clean highlight text
                            highlight = highlight.replace('\\"', '"')
                            highlight = re.sub(r'\\n', ' ', highlight)
                            highlight = re.sub(r'\s+', ' ', highlight).strip()
                            
                            # Ensure bold markers are properly formatted
                            highlight = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', highlight)
                            highlights.append(highlight)
                        
                        # Ensure we have all highlights (don't lose any)
                        while len(highlights) < len(original_content['highlights']):
                            highlights.append(original_content['highlights'][len(highlights)])
                        
                        result = {
                            'overview': overview,
                            'highlights': highlights
                        }
                        
                        # Check for actual changes
                        if self._normalize_content(result) != self._normalize_content(original_content):
                            self.logger.info("Successfully updated professional summary")
                            return result
                        else:
                            self.logger.warning("No meaningful changes to professional summary")
                            return original_content
                except json.JSONDecodeError:
                    self.logger.warning("Extracted JSON isn't valid, continuing...")
            
            # Try to parse the whole response as JSON
            try:
                clean_text = self._clean_json_string(response_text)
                content = json.loads(clean_text)
                
                # Check if the content has the expected structure
                if isinstance(content, dict) and 'overview' in content and 'highlights' in content:
                    # Clean overview text
                    overview = content['overview']
                    overview = re.sub(r'\\n', ' ', overview)
                    overview = re.sub(r'\s+', ' ', overview).strip()
                    
                    # Clean highlights
                    highlights = []
                    for highlight in content['highlights']:
                        # Clean highlight text
                        highlight = highlight.replace('\\"', '"')
                        highlight = re.sub(r'\\n', ' ', highlight)
                        highlight = re.sub(r'\s+', ' ', highlight).strip()
                        
                        # Ensure bold markers are properly formatted
                        highlight = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', highlight)
                        highlights.append(highlight)
                    
                    # Ensure we have all highlights (don't lose any)
                    while len(highlights) < len(original_content['highlights']):
                        highlights.append(original_content['highlights'][len(highlights)])
                    
                    result = {
                        'overview': overview,
                        'highlights': highlights
                    }
                    
                    # Check for actual changes
                    if self._normalize_content(result) != self._normalize_content(original_content):
                        self.logger.info("Successfully updated professional summary")
                        return result
                    else:
                        self.logger.warning("No meaningful changes to professional summary")
                        return original_content
            except json.JSONDecodeError:
                self.logger.warning("JSON parsing failed for professional summary, falling back to regex extraction")
                
            # If both JSON approaches failed, try regex extraction
            # Extract overview
            overview = original_content['overview']
            overview_match = re.search(r'"overview":\s*"([^"]+)"', response_text)
            if overview_match:
                overview = overview_match.group(1)
                # Clean overview text
                overview = overview.replace('\\"', '"')
                overview = re.sub(r'\\n', ' ', overview)
                overview = re.sub(r'\s+', ' ', overview).strip()
                
                # Ensure bold markers are properly formatted
                overview = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', overview)
            
            # Extract highlights
            highlights = original_content['highlights']
            highlights_match = re.search(r'"highlights":\s*\[(.*?)\]', response_text, re.DOTALL)
            if highlights_match:
                highlights_text = highlights_match.group(1)
                highlight_matches = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', highlights_text)
                
                if highlight_matches:
                    new_highlights = []
                    for highlight in highlight_matches:
                        # Clean highlight text
                        highlight = highlight.replace('\\"', '"')
                        highlight = re.sub(r'\\n', ' ', highlight)
                        highlight = re.sub(r'\s+', ' ', highlight).strip()
                        
                        # Ensure bold markers are properly formatted
                        highlight = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', highlight)
                        new_highlights.append(highlight)
                    
                    # If we found highlights, use them
                    if new_highlights:
                        highlights = new_highlights
                        # Ensure we keep the same number of highlights
                        while len(highlights) < len(original_content['highlights']):
                            highlights.append(original_content['highlights'][len(highlights)])
            
            result = {
                'overview': overview,
                'highlights': highlights
            }
            
            # Check for actual changes
            if self._normalize_content(result) != self._normalize_content(original_content):
                self.logger.info("Successfully extracted professional summary with regex")
                return result
                
            # If we couldn't extract anything useful, keep the original
            self.logger.warning("Could not extract useful professional summary content")
            return original_content
        except Exception as e:
            self.logger.error(f"Error processing professional summary response: {str(e)}")
            return original_content
            
    def _create_technical_skills_prompt(self, current_content, job_details):
        """Create prompt for technical skills optimization"""
        # Make skills a comma-separated string
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize the technical skills section of a resume to highlight skills relevant to the following job.

        Current Technical Skills:
        {json.dumps(current_content, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Keep the exact same categories (keys) as in the original
        2. Optimize the skills lists to highlight skills relevant to the job
        3. Use ** to highlight key skills relevant to the job (Example: **Python**)
        4. Do not remove important skills but add any relevant ones that are missing
        5. Your output must be a valid JSON object that can be parsed directly
        
        IMPORTANT: Return ONLY the JSON object with updated content, no other explanation or text before or after it.
        
        For example, your response should look exactly like:
        {{
          "programming_languages": ["Java", "**Python**", "C++"],
          "testing_tools": ["**Selenium**", "JMeter", "Postman"]
        }}
        """
        
        return prompt
        
    def _process_technical_skills_response(self, response_text, original_content):
        """Process and extract technical skills content from response"""
        try:
            # Try to extract JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_text = json_match.group(0)
                
                try:
                    # Try to parse the extracted JSON
                    content = json.loads(json_text)
                    
                    # Check if the content has a dictionary structure
                    if isinstance(content, dict) and content:
                        # Clean the content
                        cleaned_content = {}
                        for category, skills in content.items():
                            if category in original_content and isinstance(skills, list):
                                cleaned_skills = []
                                for skill in skills:
                                    if isinstance(skill, str):
                                        # Clean skill text
                                        skill = skill.replace('\\"', '"')
                                        skill = re.sub(r'\\n', ' ', skill)
                                        skill = re.sub(r'\s+', ' ', skill).strip()
                                        
                                        # Ensure bold markers are properly formatted
                                        skill = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', skill)
                                        cleaned_skills.append(skill)
                                
                                if cleaned_skills:
                                    cleaned_content[category] = cleaned_skills
                        
                        # Ensure we keep all categories
                        result = original_content.copy()
                        for category, skills in cleaned_content.items():
                            if category in result and skills:
                                result[category] = skills
                        
                        # Check for actual changes
                        if self._normalize_content(result) != self._normalize_content(original_content):
                            self.logger.info("Successfully updated technical skills")
                            return result
                        else:
                            self.logger.warning("No meaningful changes to technical skills")
                            return original_content
                except json.JSONDecodeError:
                    self.logger.warning("Extracted JSON isn't valid, continuing...")
            
            # Try to parse the whole response as JSON
            try:
                clean_text = self._clean_json_string(response_text)
                content = json.loads(clean_text)
                
                # Check if the content has a dictionary structure
                if isinstance(content, dict) and content:
                    # Clean the content
                    cleaned_content = {}
                    for category, skills in content.items():
                        if category in original_content and isinstance(skills, list):
                            cleaned_skills = []
                            for skill in skills:
                                if isinstance(skill, str):
                                    # Clean skill text
                                    skill = skill.replace('\\"', '"')
                                    skill = re.sub(r'\\n', ' ', skill)
                                    skill = re.sub(r'\s+', ' ', skill).strip()
                                    
                                    # Ensure bold markers are properly formatted
                                    skill = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', skill)
                                    cleaned_skills.append(skill)
                            
                            if cleaned_skills:
                                cleaned_content[category] = cleaned_skills
                    
                    # Ensure we keep all categories
                    result = original_content.copy()
                    for category, skills in cleaned_content.items():
                        if category in result and skills:
                            result[category] = skills
                    
                    # Check for actual changes
                    if self._normalize_content(result) != self._normalize_content(original_content):
                        self.logger.info("Successfully updated technical skills")
                        return result
                    else:
                        self.logger.warning("No meaningful changes to technical skills")
                        return original_content
            except json.JSONDecodeError:
                self.logger.warning("JSON parsing failed for technical skills, falling back to regex extraction")
                
            # If both JSON approaches failed, try regex extraction
            # Try to extract category key-value pairs
            result = original_content.copy()
            found_updates = False
            
            for category in original_content.keys():
                category_pattern = f'"{category}"\\s*:\\s*\\[(.*?)\\]'
                category_match = re.search(category_pattern, response_text, re.DOTALL)
                
                if category_match:
                    skills_text = category_match.group(1)
                    skill_matches = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', skills_text)
                    
                    if skill_matches:
                        cleaned_skills = []
                        for skill in skill_matches:
                            # Clean skill text
                            skill = skill.replace('\\"', '"')
                            skill = re.sub(r'\\n', ' ', skill)
                            skill = re.sub(r'\s+', ' ', skill).strip()
                            
                            # Ensure bold markers are properly formatted
                            skill = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', skill)
                            cleaned_skills.append(skill)
                        
                        if cleaned_skills:
                            result[category] = cleaned_skills
                            found_updates = True
            
            # Check for actual changes
            if found_updates and self._normalize_content(result) != self._normalize_content(original_content):
                self.logger.info("Successfully extracted technical skills with regex")
                return result
                
            # If we couldn't extract anything useful, keep the original
            self.logger.warning("Could not extract useful technical skills content")
            return original_content
        except Exception as e:
            self.logger.error(f"Error processing technical skills response: {str(e)}")
            return original_content
            
    def _optimize_work_experience(self, experiences, job_details):
        """Optimize work experience entries - one job at a time"""
        try:
            result = []
            
            # Only process the first 3 jobs to avoid API limits
            for i, job in enumerate(experiences[:3]):
                self.logger.info(f"Optimizing job {i+1}: {job['company']}")
                
                # Create a prompt specific to this job
                prompt = self._create_work_experience_prompt(job, job_details)
                
                # Save the prompt for debugging
                with open(self.debug_dir / f"job_{i+1}_prompt.txt", 'w') as f:
                    f.write(prompt)
                
                # Get response from Gemini with API key rotation
                response = self.make_api_call(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.1,
                        top_p=1,
                        top_k=1,
                        max_output_tokens=4000,
                    )
                )
                
                if not response or not hasattr(response, 'text') or not response.text.strip():
                    self.logger.warning(f"No response received for job {i+1}")
                    result.append(job)
                    continue
                
                # Save the raw response for debugging
                with open(self.debug_dir / f"job_{i+1}_response.txt", 'w') as f:
                    f.write(response.text)
                
                # Process the response to extract the updated job
                updated_job = self._process_work_experience_response(response.text, job)
                
                # Save the processed job for debugging
                with open(self.debug_dir / f"job_{i+1}_processed.json", 'w') as f:
                    json.dump(updated_job, f, indent=2)
                
                result.append(updated_job)
                
                # Delay to avoid rate limiting
                time.sleep(2)
                
            # Add any remaining jobs unchanged
            result.extend(experiences[3:])
            
            self.logger.info(f"Successfully updated work_experience")
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing work experience: {str(e)}")
            return experiences
            
    def _create_work_experience_prompt(self, job, job_details):
        """Create prompt for work experience job optimization"""
        # Make skills a comma-separated string
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize a work experience entry for a resume to highlight skills and achievements relevant to the following job.

        Current Work Experience Entry:
        {json.dumps(job, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Keep the same structure with company, location, position, duration, summary, achievements, environment
        2. Optimize the summary and achievements to highlight relevance to the job description
        3. Use ** to highlight key terms relevant to the job (Example: **automation testing**)
        4. Do not add or remove fields from the original structure
        5. Return ONLY a valid JSON object that can be parsed directly
        
        IMPORTANT: Return ONLY the JSON object with updated content, no other explanation or text before or after it.
        
        For example, your response should look like:
        {{
          "company": "Company Name",
          "location": "Location",
          "position": "Position Title",
          "duration": "Duration",
          "summary": "Summary with **highlighted terms**...",
          "achievements": [
            "First achievement with **key skills**...",
            "Second achievement with more **relevant experience**..."
          ],
          "environment": "Environment with **key technologies**..."
        }}
        """
        
        return prompt
        
    def _process_work_experience_response(self, response_text, original_job):
        """Process and extract work experience job content from response"""
        try:
            # Try to extract JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_text = json_match.group(0)
                
                try:
                    # Try to parse the extracted JSON
                    job = json.loads(json_text)
                    
                    # Check if the job has all the required fields
                    required_fields = ['company', 'location', 'position', 'duration', 'achievements']
                    if all(field in job for field in required_fields):
                        # Clean the content
                        cleaned_job = original_job.copy()
                        
                        # Clean summary if present
                        if 'summary' in job and isinstance(job['summary'], str):
                            summary = job['summary']
                            # Clean summary text
                            summary = summary.replace('\\"', '"')
                            summary = re.sub(r'\\n', ' ', summary)
                            summary = re.sub(r'\s+', ' ', summary).strip()
                            
                            # Ensure bold markers are properly formatted
                            summary = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', summary)
                            cleaned_job['summary'] = summary
                        
                        # Clean achievements
                        if 'achievements' in job and isinstance(job['achievements'], list):
                            achievements = []
                            for achievement in job['achievements']:
                                if isinstance(achievement, str):
                                    # Clean achievement text
                                    achievement = achievement.replace('\\"', '"')
                                    achievement = re.sub(r'\\n', ' ', achievement)
                                    achievement = re.sub(r'\s+', ' ', achievement).strip()
                                    
                                    # Ensure bold markers are properly formatted
                                    achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                                    achievements.append(achievement)
                            
                            if achievements:
                                # Make sure we don't lose any achievements
                                cleaned_job['achievements'] = achievements[:len(original_job['achievements'])]
                                while len(cleaned_job['achievements']) < len(original_job['achievements']):
                                    cleaned_job['achievements'].append(original_job['achievements'][len(cleaned_job['achievements'])])
                        
                        # Clean environment if present
                        if 'environment' in job and 'environment' in original_job and isinstance(job['environment'], str):
                            environment = job['environment']
                            # Clean environment text
                            environment = environment.replace('\\"', '"')
                            environment = re.sub(r'\\n', ' ', environment)
                            environment = re.sub(r'\s+', ' ', environment).strip()
                            
                            # Ensure bold markers are properly formatted
                            environment = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', environment)
                            cleaned_job['environment'] = environment
                        
                        # Check for actual changes
                        if self._normalize_content(cleaned_job) != self._normalize_content(original_job):
                            self.logger.info(f"Successfully updated job experience for {cleaned_job['company']}")
                            return cleaned_job
                        else:
                            self.logger.warning(f"No meaningful changes to job experience for {cleaned_job['company']}")
                            return original_job
                except json.JSONDecodeError:
                    self.logger.warning("Extracted JSON isn't valid for work experience, continuing...")
            
            # Try to parse the whole response as JSON
            try:
                clean_text = self._clean_json_string(response_text)
                job = json.loads(clean_text)
                
                # Check if the job has all the required fields
                required_fields = ['company', 'location', 'position', 'duration', 'achievements']
                if all(field in job for field in required_fields):
                    # Clean the content
                    cleaned_job = original_job.copy()
                    
                    # Clean summary if present
                    if 'summary' in job and isinstance(job['summary'], str):
                        summary = job['summary']
                        # Clean summary text
                        summary = summary.replace('\\"', '"')
                        summary = re.sub(r'\\n', ' ', summary)
                        summary = re.sub(r'\s+', ' ', summary).strip()
                        
                        # Ensure bold markers are properly formatted
                        summary = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', summary)
                        cleaned_job['summary'] = summary
                    
                    # Clean achievements
                    if 'achievements' in job and isinstance(job['achievements'], list):
                        achievements = []
                        for achievement in job['achievements']:
                            if isinstance(achievement, str):
                                # Clean achievement text
                                achievement = achievement.replace('\\"', '"')
                                achievement = re.sub(r'\\n', ' ', achievement)
                                achievement = re.sub(r'\s+', ' ', achievement).strip()
                                
                                # Ensure bold markers are properly formatted
                                achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                                achievements.append(achievement)
                        
                        if achievements:
                            # Make sure we don't lose any achievements
                            cleaned_job['achievements'] = achievements[:len(original_job['achievements'])]
                            while len(cleaned_job['achievements']) < len(original_job['achievements']):
                                cleaned_job['achievements'].append(original_job['achievements'][len(cleaned_job['achievements'])])
                    
                    # Clean environment if present
                    if 'environment' in job and 'environment' in original_job and isinstance(job['environment'], str):
                        environment = job['environment']
                        # Clean environment text
                        environment = environment.replace('\\"', '"')
                        environment = re.sub(r'\\n', ' ', environment)
                        environment = re.sub(r'\s+', ' ', environment).strip()
                        
                        # Ensure bold markers are properly formatted
                        environment = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', environment)
                        cleaned_job['environment'] = environment
                    
                    # Check for actual changes
                    if self._normalize_content(cleaned_job) != self._normalize_content(original_job):
                        self.logger.info(f"Successfully updated job experience for {cleaned_job['company']}")
                        return cleaned_job
                    else:
                        self.logger.warning(f"No meaningful changes to job experience for {cleaned_job['company']}")
                        return original_job
            except json.JSONDecodeError:
                self.logger.warning("JSON parsing failed for work experience, falling back to regex extraction")
            
            # If both JSON approaches failed, try regex extraction
            cleaned_job = original_job.copy()
            found_updates = False
            
            # Try to extract summary
            summary_match = re.search(r'"summary":\s*"([^"\\]*(?:\\.[^"\\]*)*)"', response_text)
            if summary_match and 'summary' in original_job:
                summary = summary_match.group(1)
                # Clean summary text
                summary = summary.replace('\\"', '"')
                summary = re.sub(r'\\n', ' ', summary)
                summary = re.sub(r'\s+', ' ', summary).strip()
                
                # Ensure bold markers are properly formatted
                summary = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', summary)
                
                if summary:
                    cleaned_job['summary'] = summary
                    found_updates = True
            
            # Try to extract achievements
            achievements_match = re.search(r'"achievements":\s*\[(.*?)\]', response_text, re.DOTALL)
            if achievements_match:
                achievements_text = achievements_match.group(1)
                achievement_matches = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', achievements_text)
                
                if achievement_matches:
                    achievements = []
                    for achievement in achievement_matches:
                        # Clean achievement text
                        achievement = achievement.replace('\\"', '"')
                        achievement = re.sub(r'\\n', ' ', achievement)
                        achievement = re.sub(r'\s+', ' ', achievement).strip()
                        
                        # Ensure bold markers are properly formatted
                        achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                        achievements.append(achievement)
                    
                    if achievements:
                        # Make sure we don't lose any achievements
                        cleaned_job['achievements'] = achievements[:len(original_job['achievements'])]
                        while len(cleaned_job['achievements']) < len(original_job['achievements']):
                            cleaned_job['achievements'].append(original_job['achievements'][len(cleaned_job['achievements'])])
                        found_updates = True
            
            # Try to extract environment
            environment_match = re.search(r'"environment":\s*"([^"\\]*(?:\\.[^"\\]*)*)"', response_text)
            if environment_match and 'environment' in original_job:
                environment = environment_match.group(1)
                # Clean environment text
                environment = environment.replace('\\"', '"')
                environment = re.sub(r'\\n', ' ', environment)
                environment = re.sub(r'\s+', ' ', environment).strip()
                
                # Ensure bold markers are properly formatted
                environment = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', environment)
                
                if environment:
                    cleaned_job['environment'] = environment
                    found_updates = True
            
            # Check for actual changes
            if found_updates and self._normalize_content(cleaned_job) != self._normalize_content(original_job):
                self.logger.info(f"Successfully extracted job experience for {cleaned_job['company']} with regex")
                return cleaned_job
            
            # If we couldn't extract anything useful, keep the original
            self.logger.warning(f"Could not extract useful content for job experience {original_job['company']}")
            return original_job
        except Exception as e:
            self.logger.error(f"Error processing work experience response: {str(e)}")
            return original_job
    
    def _clean_json_string(self, text):
        """Clean a string to make it valid JSON"""
        if not text:
            return "{}"
            
        # Remove any leading/trailing whitespace
        text = text.strip()
        
        # Find JSON-like content
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
            
        # Remove any markdown code block markers
        text = re.sub(r'```(?:json)?\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Remove any language markers
        text = re.sub(r'javascript\s*', '', text)
        text = re.sub(r'python\s*', '', text)
        text = re.sub(r'json\s*', '', text)
        
        # Fix common JSON syntax issues
        text = re.sub(r',\s*}', '}', text)  # Remove trailing commas in objects
        text = re.sub(r',\s*\]', ']', text)  # Remove trailing commas in arrays
        
        # Handle unescaped quotes inside strings
        text = re.sub(r'(?<="[^"]*)"(?=[^"]*")', '\\"', text)
        
        # Fix single quotes to double quotes (common in response)
        text = re.sub(r"'([^']*)'", r'"\1"', text)
        
        return text

    def generate_cover_letter(self, job_details: dict, resume_path: str) -> str:
        """Generate cover letter from job details and resume with API key rotation"""
        try:
            # Load resume data from the JSON file
            try:
                # Convert .docx path to .json path
                resume_json_path = resume_path.replace('.docx', '.json')
                
                # Check if the JSON file exists
                if not os.path.exists(resume_json_path):
                    self.logger.error(f"Resume JSON file not found: {resume_json_path}")
                    return ""
                
                # Load the JSON data
                with open(resume_json_path, 'r') as f:
                    resume_data = json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading resume data: {str(e)}")
                return ""
                
            # Make skills a comma-separated string
            skills_str = ', '.join(job_details.get('skills', []))
            
            prompt = f"""
            Generate a professional cover letter using my resume data for the following job.
            
            My Information:
            Name: {resume_data['header']['name']}
            Email: {resume_data['header']['email']}
            Phone: {resume_data['header']['phone']}
            
            Job Details:
            Title: {job_details.get('title', '')}
            Company: {job_details.get('company', '')}
            Skills: {skills_str}
            
            My Experience Summary:
            {resume_data['professional_summary']['overview']}
            
            Requirements:
            1. Use natural, conversational tone
            2. Focus on 2-3 most relevant experiences from my resume
            3. Keep it concise (250-300 words)
            4. NO PLACEHOLDERS WHATSOEVER - use "Hiring Manager" instead of a name placeholder
            5. Match my actual experience to job requirements
            6. Skip formal header/footer - just the letter content
            7. Make it ready to send immediately with no editing needed
            8. Be specific about years of experience
            9. Avoid phrases like "[Company Name]" or "[Role]" - use the actual company and role
            10. Craft a compelling but honest narrative about why I'm a great fit
            
            The cover letter should be completely ready to submit with no edits needed.
            """

            # Save the prompt for debugging
            with open(self.debug_dir / "cover_letter_prompt.txt", 'w') as f:
                f.write(prompt)

            # Use the API key rotation mechanism
            response = self.make_api_call(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,  # Higher temperature for more natural writing
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=1024,
                )
            )
            
            if response and hasattr(response, 'text'):
                # Save the raw response for debugging
                with open(self.debug_dir / "cover_letter_response.txt", 'w') as f:
                    f.write(response.text)

                # Clean and format the cover letter
                cover_letter = response.text.strip()
                
                # Clean any potential placeholders
                cover_letter = re.sub(r'\[.*?\]', '', cover_letter)
                
                # Remove markdown code block markers
                cover_letter = re.sub(r'```(?:markdown)?\s*', '', cover_letter)
                cover_letter = re.sub(r'```\s*', '', cover_letter)
                
                # Clean up line breaks and spacing
                cover_letter = re.sub(r'\n{3,}', '\n\n', cover_letter)
                
                # Save the processed cover letter for debugging
                with open(self.debug_dir / "cover_letter_processed.txt", 'w') as f:
                    f.write(cover_letter)
                
                return cover_letter
            
            return ""
        except Exception as e:
            self.logger.error(f"Error generating cover letter: {str(e)}")
            return ""
            
    def get_api_usage_stats(self):
        """Get current API usage statistics"""
        return self.api_key_manager.get_usage_stats()
        
    def are_all_keys_exhausted(self):
        """Check if all API keys have reached their daily limit"""
        return self.api_key_manager.all_keys_exhausted()
        
    def test_connection(self):
        """Test the Gemini API connection"""
        try:
            response = self.make_api_call(
                "Hello, this is a connection test",
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=10,
                )
            )
            return response is not None
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False