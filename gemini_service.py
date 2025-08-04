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
    """Handles all interactions with Gemini AI with support for new v2 resume format"""
    
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
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-06-17")
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
        """Main method to optimize a resume section based on job details - updated for v2 format"""
        try:
            # Format the prompt based on section type (updated for v2)
            if section_name == 'professional_summary':
                prompt = self._create_professional_summary_prompt(current_content, job_details)
            elif section_name == 'core_competencies':
                prompt = self._create_core_competencies_prompt(current_content, job_details)
            elif section_name == 'professional_experience':
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
                
            # Process the response based on section type (updated for v2)
            if section_name == 'professional_summary':
                updated_content = self._process_professional_summary_response(response.text, current_content)
            elif section_name == 'core_competencies':
                updated_content = self._process_core_competencies_response(response.text, current_content)
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
            
    def _create_professional_summary_prompt(self, current_content, job_details):
        """Create prompt for the new unified professional summary optimization"""
        # Make skills a comma-separated string
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize a professional summary for a resume. This summary has 4 specific components that need to be optimized for the job description.

        Current Professional Summary:
        {json.dumps(current_content, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Keep the exact same structure with these 4 fields: "title_experience", "track_record", "expertise", "core_value"
        2. Optimize each field to emphasize relevance to the job description
        3. Use ** to highlight key terms relevant to the job (Example: **automation testing**)
        4. Maintain the professional tone and specific metrics where they exist
        5. Keep the "Senior SDET with 10+ years" opening format in title_experience
        6. Preserve any specific percentages and numbers in track_record
        7. Your output must be a valid JSON object that can be parsed directly
        
        IMPORTANT: Return ONLY the JSON object with the updated content, no other explanation or text before or after it.
        
        For example, your response should look exactly like:
        {{
          "title_experience": "**Senior SDET** with **10+ years** leading test automation initiatives...",
          "track_record": "Proven track record of reducing **production defects by 75%**...",
          "expertise": "Expert in **cloud-native testing**, **CI/CD integration**...",
          "core_value": "Transform manual testing processes into scalable, automated solutions..."
        }}
        """
        
        return prompt
        
    def _process_professional_summary_response(self, response_text, original_content):
        """Process and extract professional summary content from response - updated for v2"""
        try:
            # Try to extract JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_text = json_match.group(0)
                
                try:
                    # Try to parse the extracted JSON
                    content = json.loads(json_text)
                    
                    # Check if the content has the expected v2 structure
                    required_fields = ['title_experience', 'track_record', 'expertise', 'core_value']
                    if isinstance(content, dict) and all(field in content for field in required_fields):
                        # Clean the content
                        cleaned_content = {}
                        for field in required_fields:
                            text = content[field]
                            # Clean text
                            text = re.sub(r'\\n', ' ', text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            # Ensure bold markers are properly formatted
                            text = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', text)
                            cleaned_content[field] = text
                        
                        # Check for actual changes
                        if self._normalize_content(cleaned_content) != self._normalize_content(original_content):
                            self.logger.info("Successfully updated professional summary")
                            return cleaned_content
                        else:
                            self.logger.warning("No meaningful changes to professional summary")
                            return original_content
                except json.JSONDecodeError:
                    self.logger.warning("Extracted JSON isn't valid, continuing...")
            
            # Try to parse the whole response as JSON
            try:
                clean_text = self._clean_json_string(response_text)
                content = json.loads(clean_text)
                
                # Check if the content has the expected v2 structure
                required_fields = ['title_experience', 'track_record', 'expertise', 'core_value']
                if isinstance(content, dict) and all(field in content for field in required_fields):
                    # Clean the content
                    cleaned_content = {}
                    for field in required_fields:
                        text = content[field]
                        # Clean text
                        text = re.sub(r'\\n', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        # Ensure bold markers are properly formatted
                        text = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', text)
                        cleaned_content[field] = text
                    
                    # Check for actual changes
                    if self._normalize_content(cleaned_content) != self._normalize_content(original_content):
                        self.logger.info("Successfully updated professional summary")
                        return cleaned_content
                    else:
                        self.logger.warning("No meaningful changes to professional summary")
                        return original_content
            except json.JSONDecodeError:
                self.logger.warning("JSON parsing failed for professional summary, falling back to regex extraction")
                
            # If both JSON approaches failed, try regex extraction
            result = original_content.copy()
            found_updates = False
            
            required_fields = ['title_experience', 'track_record', 'expertise', 'core_value']
            for field in required_fields:
                field_pattern = f'"{field}"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"'
                field_match = re.search(field_pattern, response_text)
                
                if field_match:
                    text = field_match.group(1)
                    # Clean text
                    text = text.replace('\\"', '"')
                    text = re.sub(r'\\n', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    # Ensure bold markers are properly formatted
                    text = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', text)
                    
                    if text:
                        result[field] = text
                        found_updates = True
            
            # Check for actual changes
            if found_updates and self._normalize_content(result) != self._normalize_content(original_content):
                self.logger.info("Successfully extracted professional summary with regex")
                return result
                
            # If we couldn't extract anything useful, keep the original
            self.logger.warning("Could not extract useful professional summary content")
            return original_content
        except Exception as e:
            self.logger.error(f"Error processing professional summary response: {str(e)}")
            return original_content
            
    def _create_core_competencies_prompt(self, current_content, job_details):
        """Create prompt for core competencies optimization - replaces technical skills"""
        # Make skills a comma-separated string
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize the core competencies section of a resume to highlight skills relevant to the following job.

        Current Core Competencies:
        {json.dumps(current_content, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Keep the exact same 8 categories as in the original: programming_and_automation, testing_frameworks, cloud_and_devops, api_and_performance, quality_tools, databases, domain_expertise, leadership
        2. Optimize the skills lists to highlight skills relevant to the job
        3. Use ** to highlight key skills relevant to the job (Example: **Python**, **Selenium**)
        4. Do not remove important skills but add any relevant ones that are missing
        5. Maintain the structure where each category has a list of skills
        6. Your output must be a valid JSON object that can be parsed directly
        
        IMPORTANT: Return ONLY the JSON object with updated content, no other explanation or text before or after it.
        
        For example, your response should look exactly like:
        {{
          "programming_and_automation": ["**Java**", "**Python**", "JavaScript/TypeScript"],
          "testing_frameworks": ["**Selenium WebDriver**", "REST Assured", "Appium"],
          "cloud_and_devops": ["**AWS (EC2, RDS, CloudWatch, S3)**", "Docker", "Kubernetes"],
          ...
        }}
        """
        
        return prompt
        
    def _process_core_competencies_response(self, response_text, original_content):
        """Process and extract core competencies content from response - new for v2"""
        try:
            # Try to extract JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_text = json_match.group(0)
                
                try:
                    # Try to parse the extracted JSON
                    content = json.loads(json_text)
                    
                    # Check if the content has a dictionary structure with expected categories
                    expected_categories = ['programming_and_automation', 'testing_frameworks', 'cloud_and_devops', 
                                         'api_and_performance', 'quality_tools', 'databases', 'domain_expertise', 'leadership']
                    
                    if isinstance(content, dict) and any(cat in content for cat in expected_categories):
                        # Clean the content
                        cleaned_content = {}
                        for category, skills in content.items():
                            if category in expected_categories and isinstance(skills, list):
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
                        
                        # Ensure we keep all original categories
                        result = original_content.copy()
                        for category, skills in cleaned_content.items():
                            if category in result and skills:
                                result[category] = skills
                        
                        # Check for actual changes
                        if self._normalize_content(result) != self._normalize_content(original_content):
                            self.logger.info("Successfully updated core competencies")
                            return result
                        else:
                            self.logger.warning("No meaningful changes to core competencies")
                            return original_content
                except json.JSONDecodeError:
                    self.logger.warning("Extracted JSON isn't valid, continuing...")
            
            # Try to parse the whole response as JSON
            try:
                clean_text = self._clean_json_string(response_text)
                content = json.loads(clean_text)
                
                # Check if the content has a dictionary structure with expected categories
                expected_categories = ['programming_and_automation', 'testing_frameworks', 'cloud_and_devops', 
                                     'api_and_performance', 'quality_tools', 'databases', 'domain_expertise', 'leadership']
                
                if isinstance(content, dict) and any(cat in content for cat in expected_categories):
                    # Clean the content
                    cleaned_content = {}
                    for category, skills in content.items():
                        if category in expected_categories and isinstance(skills, list):
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
                    
                    # Ensure we keep all original categories
                    result = original_content.copy()
                    for category, skills in cleaned_content.items():
                        if category in result and skills:
                            result[category] = skills
                    
                    # Check for actual changes
                    if self._normalize_content(result) != self._normalize_content(original_content):
                        self.logger.info("Successfully updated core competencies")
                        return result
                    else:
                        self.logger.warning("No meaningful changes to core competencies")
                        return original_content
            except json.JSONDecodeError:
                self.logger.warning("JSON parsing failed for core competencies, falling back to regex extraction")
                
            # If both JSON approaches failed, try regex extraction
            result = original_content.copy()
            found_updates = False
            
            expected_categories = ['programming_and_automation', 'testing_frameworks', 'cloud_and_devops', 
                                 'api_and_performance', 'quality_tools', 'databases', 'domain_expertise', 'leadership']
            
            for category in expected_categories:
                if category in original_content:
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
                self.logger.info("Successfully extracted core competencies with regex")
                return result
                
            # If we couldn't extract anything useful, keep the original
            self.logger.warning("Could not extract useful core competencies content")
            return original_content
        except Exception as e:
            self.logger.error(f"Error processing core competencies response: {str(e)}")
            return original_content
            
    def _optimize_work_experience(self, experiences, job_details):
        """Optimize work experience entries - updated for v2 format"""
        try:
            result = []
            
            # Only process the first 3 jobs to avoid API limits
            for i, job in enumerate(experiences[:3]):
                self.logger.info(f"Optimizing job {i+1}: {job['company']}")
                
                # Create a prompt specific to this job (updated for v2)
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
                
                # Process the response to extract the updated job (updated for v2)
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
            
    def _create_work_experience_prompt(self, current_content, job_details):
        """Create prompt for work experience optimization with FIXED environment section handling"""
        skills_str = ', '.join(job_details.get('skills', []))
        
        prompt = f"""
        I need you to optimize the work experience section of a resume for the following job.

        Current Work Experience:
        {json.dumps(current_content, indent=2)}
        
        Job Details:
        Title: {job_details.get('title', '')}
        Skills Required: {skills_str}
        Description: {job_details.get('description', '')}

        Instructions:
        1. Keep the exact same structure for each job
        2. Optimize achievements to highlight skills relevant to the job
        3. Use ** to highlight key skills relevant to the job (Example: **Python**, **Selenium**)
        4. For the 'environment' field: ONLY list technical tools, technologies, and platforms - NO narrative text or explanatory phrases
        5. Environment should be a simple comma-separated list like: "Java, Selenium, AWS, Docker, Jenkins"
        6. Do NOT add phrases like "demonstrating passion" or "showcasing skills" to the environment section
        7. Maintain specific metrics and achievements where they exist
        8. Your output must be a valid JSON array that can be parsed directly
        
        CRITICAL: The environment field should contain ONLY technical tools and technologies, nothing else.
        
        IMPORTANT: Return ONLY the JSON array with updated content, no other explanation or text before or after it.
        """
        
        return prompt
   
    def _process_work_experience_response(self, response_text, original_job):
        """Process and extract work experience job content from response - updated for v2"""
        try:
            # Try to extract JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_text = json_match.group(0)
                
                try:
                    # Try to parse the extracted JSON
                    job = json.loads(json_text)
                    
                    # Check if the job has all the required fields
                    required_fields = ['company', 'location', 'position', 'duration']
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
                        
                        # Clean key_achievements if present (v2 feature)
                        if 'key_achievements' in job and isinstance(job['key_achievements'], list):
                            achievements = []
                            for achievement in job['key_achievements']:
                                if isinstance(achievement, str):
                                    # Clean achievement text
                                    achievement = achievement.replace('\\"', '"')
                                    achievement = re.sub(r'\\n', ' ', achievement)
                                    achievement = re.sub(r'\s+', ' ', achievement).strip()
                                    # Ensure bold markers are properly formatted
                                    achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                                    achievements.append(achievement)
                            
                            if achievements:
                                cleaned_job['key_achievements'] = achievements
                        
                        # Clean detailed_achievements if present (v2 feature)
                        if 'detailed_achievements' in job and isinstance(job['detailed_achievements'], list):
                            achievements = []
                            for achievement in job['detailed_achievements']:
                                if isinstance(achievement, str):
                                    # Clean achievement text
                                    achievement = achievement.replace('\\"', '"')
                                    achievement = re.sub(r'\\n', ' ', achievement)
                                    achievement = re.sub(r'\s+', ' ', achievement).strip()
                                    # Ensure bold markers are properly formatted
                                    achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                                    achievements.append(achievement)
                            
                            if achievements:
                                cleaned_job['detailed_achievements'] = achievements
                        
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
                required_fields = ['company', 'location', 'position', 'duration']
                if all(field in job for field in required_fields):
                    # Clean the content (same logic as above)
                    cleaned_job = original_job.copy()
                    
                    # Clean summary if present
                    if 'summary' in job and isinstance(job['summary'], str):
                        summary = job['summary']
                        summary = summary.replace('\\"', '"')
                        summary = re.sub(r'\\n', ' ', summary)
                        summary = re.sub(r'\s+', ' ', summary).strip()
                        summary = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', summary)
                        cleaned_job['summary'] = summary
                    
                    # Clean key_achievements if present
                    if 'key_achievements' in job and isinstance(job['key_achievements'], list):
                        achievements = []
                        for achievement in job['key_achievements']:
                            if isinstance(achievement, str):
                                achievement = achievement.replace('\\"', '"')
                                achievement = re.sub(r'\\n', ' ', achievement)
                                achievement = re.sub(r'\s+', ' ', achievement).strip()
                                achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                                achievements.append(achievement)
                        
                        if achievements:
                            cleaned_job['key_achievements'] = achievements
                    
                    # Clean detailed_achievements if present
                    if 'detailed_achievements' in job and isinstance(job['detailed_achievements'], list):
                        achievements = []
                        for achievement in job['detailed_achievements']:
                            if isinstance(achievement, str):
                                achievement = achievement.replace('\\"', '"')
                                achievement = re.sub(r'\\n', ' ', achievement)
                                achievement = re.sub(r'\s+', ' ', achievement).strip()
                                achievement = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', achievement)
                                achievements.append(achievement)
                        
                        if achievements:
                            cleaned_job['detailed_achievements'] = achievements
                    
                    # Clean environment if present
                    if 'environment' in job and 'environment' in original_job and isinstance(job['environment'], str):
                        environment = job['environment']
                        environment = environment.replace('\\"', '"')
                        environment = re.sub(r'\\n', ' ', environment)
                        environment = re.sub(r'\s+', ' ', environment).strip()
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
            
            # If both JSON approaches failed, try regex extraction (simplified for brevity)
            # This would follow similar pattern as above but using regex to extract fields
            # For now, return original if JSON parsing fails
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
            
            # Updated prompt for v2 resume format
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
            
            My Professional Summary:
            {resume_data['professional_summary']['title_experience']} {resume_data['professional_summary']['track_record']} {resume_data['professional_summary']['expertise']}
            
            Core Value: {resume_data['professional_summary']['core_value']}
            
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
    
    def convert_job_description_to_json(self, description_text: str, job_title: str = "Software Engineer", 
                                  company_name: str = "Unknown Company") -> dict:
        """Convert a plain text job description to structured JSON format using Gemini AI"""
        try:
            prompt = f"""
            Convert the following job description into a structured JSON object.
            
            Job Title: {job_title}
            Company: {company_name}
            
            Job Description:
            {description_text}
            
            Extract the following information:
            1. A clean job title (use the provided title if appropriate, otherwise extract from description)
            2. Company name (use the provided company name)
            3. Full job description (cleaned up and formatted)
            4. A list of required skills mentioned in the description (be comprehensive)
            5. Location information if mentioned
            
            Return ONLY a valid JSON object with the following structure:
            {{
            "title": "Extracted Job Title",
            "company": "Company Name",
            "location": "Location (if mentioned, otherwise 'Remote')",
            "description": "Full job description",
            "skills": ["Skill 1", "Skill 2", "Skill 3", ...]
            }}
            
            IMPORTANT: 
            - Return ONLY the JSON object with no other text before or after it
            - Make sure the skills list is comprehensive and identifies specific technologies, tools, and competencies
            - If location is not mentioned, use "Remote" as the default
            - Do not include any markdown formatting or code blocks
            """
            
            # Save the prompt for debugging
            with open(self.debug_dir / "job_description_to_json_prompt.txt", 'w') as f:
                f.write(prompt)
            
            # Make API call with key rotation
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
                self.logger.warning("No response received from Gemini for job description conversion")
                return None
            
            # Save the raw response for debugging
            with open(self.debug_dir / "job_description_to_json_response.txt", 'w') as f:
                f.write(response.text)
            
            # Extract JSON from the response using our robust utility function
            job_json = self._extract_json_from_text(response.text)
            
            if not job_json:
                self.logger.error("Failed to extract JSON from Gemini response")
                # Save the problematic response for debugging
                with open(self.debug_dir / "failed_json_response.txt", 'w') as f:
                    f.write(response.text)
                
                # Create a basic JSON with the job description text
                self.logger.info("Creating basic JSON from job description text")
                job_json = {
                    'title': job_title,
                    'company': company_name,
                    'description': description_text,
                    'location': 'Remote',
                    'skills': []
                }
                
                # Try to extract skills using regex patterns
                skill_patterns = [
                    r'(?:skills|requirements|qualifications):[^\n]*\n(.*?)(?:\n\n|\Z)',
                    r'(?:experience|technical skills|expertise):[^\n]*\n(.*?)(?:\n\n|\Z)'
                ]
                
                for pattern in skill_patterns:
                    match = re.search(pattern, description_text, re.DOTALL | re.IGNORECASE)
                    if match:
                        skills_section = match.group(1)
                        # Extract bullet points
                        skills_items = re.findall(r'[-•*]\s*([^\n]*)', skills_section)
                        if skills_items:
                            job_json['skills'] = [item.strip() for item in skills_items]
                            break
                
                # If no skills found, use common technical skills detection
                if not job_json['skills']:
                    common_tech_skills = [
                        'Python', 'Java', 'JavaScript', 'TypeScript', 'C#', 'C++', 
                        'SQL', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 
                        'REST', 'API', 'Git', 'CI/CD', 'Jenkins', 'Selenium', 
                        'Appium', 'JMeter', 'TestNG', 'JUnit', 'Maven', 'Gradle',
                        'HTML', 'CSS', 'React', 'Angular', 'Vue', 'Node.js',
                        'SDET', 'QA', 'Test Automation', 'Agile', 'Scrum'
                    ]
                    
                    # Find skills in description
                    for skill in common_tech_skills:
                        if re.search(r'\b' + re.escape(skill) + r'\b', description_text, re.IGNORECASE):
                            job_json['skills'].append(skill)
                
                # If still no skills, add default ones
                if not job_json['skills']:
                    job_json['skills'] = ["Test Automation", "Software Testing", "QA"]
            
            # Validate the JSON structure
            required_fields = ['title', 'company', 'description', 'skills']
            missing_fields = [field for field in required_fields if field not in job_json]
            
            if missing_fields:
                self.logger.error(f"Missing required fields in job JSON: {missing_fields}")
                
                # Create a fallback JSON with the missing fields
                if 'title' not in job_json:
                    job_json['title'] = job_title
                if 'company' not in job_json:
                    job_json['company'] = company_name
                if 'description' not in job_json:
                    job_json['description'] = description_text
                if 'skills' not in job_json:
                    # Extract potential skills using a basic keyword approach
                    common_tech_skills = [
                        'Python', 'Java', 'JavaScript', 'TypeScript', 'C#', 'C++', 
                        'SQL', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 
                        'REST', 'API', 'Git', 'CI/CD', 'Jenkins', 'Selenium', 
                        'Appium', 'JMeter', 'TestNG', 'JUnit', 'Maven', 'Gradle',
                        'HTML', 'CSS', 'React', 'Angular', 'Vue', 'Node.js',
                        'SDET', 'QA', 'Test Automation', 'Agile', 'Scrum',
                        'JIRA', 'Confluence', 'DevOps', 'Linux', 'Unix',
                        'Test Cases', 'Test Plan', 'Regression Testing',
                        'Performance Testing', 'Security Testing', 'API Testing',
                        'UI Testing', 'Unit Testing', 'HL7', 'FHIR', 'HIPAA'
                    ]
                    
                    # Find skills in description
                    found_skills = []
                    for skill in common_tech_skills:
                        if re.search(r'\b' + re.escape(skill) + r'\b', description_text, re.IGNORECASE):
                            found_skills.append(skill)
                    
                    job_json['skills'] = found_skills if found_skills else ["Test Automation", "Software Testing"]
                
                self.logger.info("Created fallback JSON with missing fields")
                # Save the fallback JSON for debugging
                with open(self.debug_dir / "fallback_job_json.json", 'w') as f:
                    json.dump(job_json, f, indent=2)
            
            # Ensure skills is a list
            if 'skills' in job_json and not isinstance(job_json['skills'], list):
                if isinstance(job_json['skills'], str):
                    job_json['skills'] = [skill.strip() for skill in job_json['skills'].split(',')]
                else:
                    job_json['skills'] = []
            
            # Ensure location is set
            if 'location' not in job_json or not job_json['location']:
                job_json['location'] = 'Remote'
            
            # Save the processed JSON for debugging
            with open(self.debug_dir / "job_description_to_json_processed.json", 'w') as f:
                json.dump(job_json, f, indent=2)
            
            return job_json
        
        except Exception as e:
            self.logger.error(f"Error converting job description to JSON: {str(e)}")
            return None

    def _extract_json_from_text(self, text: str) -> dict:
        """Extract a JSON object from text using multiple approaches"""
        try:
            # Save the original text for debugging
            with open(self.debug_dir / "json_extraction_input.txt", 'w') as f:
                f.write(text)
                
            # Method 1: Try direct parsing
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
                
            # Method 2: Find and extract JSON-like structure with curly braces
            try:
                matches = re.findall(r'({[^{]*})', text.replace('\n', ' '), re.DOTALL)
                
                if not matches:
                    # Try more aggressive pattern
                    matches = re.findall(r'({.*})', text, re.DOTALL)
                    
                # Try each match
                for match in matches:
                    try:
                        # Clean up the match - remove code markers, fix quotes, etc.
                        cleaned = match.strip()
                        cleaned = re.sub(r'```(?:json)?|```', '', cleaned)
                        cleaned = re.sub(r',\s*}', '}', cleaned)  # Remove trailing commas
                        cleaned = re.sub(r',\s*]', ']', cleaned)  # Remove trailing commas in arrays
                        
                        # Try with original quotes
                        try:
                            return json.loads(cleaned)
                        except json.JSONDecodeError:
                            # Try replacing single quotes with double quotes
                            cleaned = re.sub(r'\'', '"', cleaned)
                            try:
                                return json.loads(cleaned)
                            except json.JSONDecodeError:
                                continue
                    except:
                        continue
            except:
                pass
                
            # Method 3: Try to find JSON-like structure with "title", "company", etc. markers
            markers = ['title', 'company', 'description', 'skills']
            foundMarkers = []
            markerStart = None
            
            # Find where the first marker appears
            for marker in markers:
                pattern = f'"{marker}"\\s*:'
                match = re.search(pattern, text)
                if match:
                    foundMarkers.append(marker)
                    start = match.start()
                    if markerStart is None or start < markerStart:
                        markerStart = start
            
            if markerStart is not None:
                # Try to find opening brace before the first marker
                text_before = text[:markerStart]
                opening_brace = text_before.rfind('{')
                
                if opening_brace >= 0:
                    # Find matching closing brace
                    potential_json = text[opening_brace:]
                    brace_count = 0
                    closing_index = -1
                    
                    for i, char in enumerate(potential_json):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                closing_index = i
                                break
                    
                    if closing_index > 0:
                        extracted = potential_json[:closing_index + 1]
                        try:
                            return json.loads(extracted)
                        except json.JSONDecodeError:
                            # Try to clean up and retry
                            cleaned = re.sub(r',\s*}', '}', extracted)
                            cleaned = re.sub(r',\s*]', ']', cleaned)
                            try:
                                return json.loads(cleaned)
                            except json.JSONDecodeError:
                                pass
            
            # Method 4: Manual JSON construction (same as original)
            # Look for patterns like "title": "Software Engineer"
            result = {}
            for marker in markers:
                pattern = f'"{marker}"\\s*:\\s*"([^"]*)"'
                match = re.search(pattern, text)
                if match:
                    result[marker] = match.group(1)
                    
            # Handle skills (could be an array)
            skills_pattern = r'"skills"\s*:\s*\[(.*?)\]'
            skills_match = re.search(skills_pattern, text, re.DOTALL)
            if skills_match:
                skills_text = skills_match.group(1)
                # Extract items from array
                skills = []
                skill_matches = re.findall(r'"([^"]*)"', skills_text)
                for skill in skill_matches:
                    skills.append(skill)
                if skills:
                    result["skills"] = skills
            
            if len(result) >= 2:  # At least two fields found
                return result
                
            # Method 5: Super aggressive extraction (last resort) - same as original
            manual_json = {}
            
            # Try to find title
            title_patterns = [
                r'"title"\s*:\s*"([^"]*)"',
                r'title:\s*"([^"]*)"',
                r'title:\s*([^\n,]*)',
                r'Job Title:?\s*([^\n]*)'
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    manual_json['title'] = match.group(1).strip()
                    break
                    
            # Try to find company
            company_patterns = [
                r'"company"\s*:\s*"([^"]*)"',
                r'company:\s*"([^"]*)"',
                r'company:\s*([^\n,]*)',
                r'Company:?\s*([^\n]*)'
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    manual_json['company'] = match.group(1).strip()
                    break
                    
            # Extract description (take everything if necessary)
            manual_json['description'] = text.strip()
            
            # Skills is trickier - look for skills section or keywords
            manual_json['skills'] = []
            skills_section = None
            for pattern in [r'Skills:[^\n]*\n(.*?)(?:\n\n|\Z)', r'Requirements:[^\n]*\n(.*?)(?:\n\n|\Z)']:
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    skills_section = match.group(1)
                    break
                    
            if skills_section:
                # Extract bullet points or comma separated items
                skills_items = re.findall(r'[-•*]\s*([^\n]*)', skills_section)
                if skills_items:
                    manual_json['skills'] = [item.strip() for item in skills_items]
                else:
                    # Try comma separated
                    skills_items = skills_section.split(',')
                    if len(skills_items) > 1:
                        manual_json['skills'] = [item.strip() for item in skills_items]
            
            # Add default location
            manual_json['location'] = 'Remote'
            
            # Save this manual extraction for debugging
            with open(self.debug_dir / "manual_json_extraction.json", 'w') as f:
                json.dump(manual_json, f, indent=2)
                
            if len(manual_json) >= 3:  # At least three fields found
                return manual_json
                
            return None
        except Exception as e:
            self.logger.error(f"Error in JSON extraction: {str(e)}")
            return None    
    
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