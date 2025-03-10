import os
import json
import time
import random
import logging
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Set
from urllib.parse import quote
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

from config import (
    CHROME_PROFILE, 
    CHROME_ARGUMENTS,
    CHROMEDRIVER_PATH,
    DELAYS, 
    MAX_RETRIES, 
    JOB_TITLES,
    DICE_SEARCH_URL,
    JOBS_DIR,
    RESUME_DIR,
    DATA_DIR,
    DEBUG_MODE
)
from resume_handler import ResumeHandler
from gemini_service import GeminiService
from application_tracker import ApplicationTracker

class DiceBot:
    """Improved automated job application bot for Dice.com"""
    
    def __init__(self):
        self.setup_logging()
        self.resume_handler = ResumeHandler()
        self.gemini = GeminiService()
        self.tracker = ApplicationTracker(DATA_DIR)
        self.driver = None
        self.wait = None
        self.jobs_processed = 0
        self.jobs_applied = 0
        self.jobs_skipped = 0
        
        # Keep track of processed job IDs to avoid duplicates
        self.processed_job_ids = set()
        
        # Track processed job titles and pages
        self.processed_titles = {}  # Format: {title: last_page_processed}
        
    def setup_logging(self):
        """Configure logging"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            
            # File handler
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)
            
            fh = logging.FileHandler(
                log_dir / f'dice_bot_{datetime.now():%Y%m%d_%H%M%S}.log'
            )
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            
            # Console handler
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    def setup_driver(self) -> bool:
        """Initialize Chrome WebDriver with anti-detection measures and handle existing browser sessions"""
        try:
            # First try to close any existing Chrome processes to prevent profile conflicts
            self.logger.info("Checking for existing Chrome processes...")
            try:
                if os.name == 'nt':  # Windows
                    os.system("taskkill /f /im chrome.exe")
                    os.system("taskkill /f /im chromedriver.exe")
                else:  # Linux/Mac
                    os.system("pkill -f chrome")
                    os.system("pkill -f chromedriver")
                time.sleep(2)
                self.logger.info("Closed existing Chrome processes")
            except Exception as e:
                self.logger.warning(f"Failed to close existing Chrome processes: {str(e)}")
            
            # Create options with profile
            options = Options()
            
            # Set profile paths
            user_data_dir = CHROME_PROFILE['user_data_dir']
            profile_directory = CHROME_PROFILE['profile_directory']
            
            # Add essential Chrome options
            options.add_argument('--start-maximized')
            options.add_argument('--disable-extensions')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Anti-detection options
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Add User-Agent to appear as regular browser
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            # Try with profile first
            try:
                profile_options = options
                profile_options.add_argument(f'--user-data-dir={user_data_dir}')
                profile_options.add_argument(f'--profile-directory={profile_directory}')
                
                # Initialize ChromeDriver service
                service = Service(executable_path=CHROMEDRIVER_PATH)
                
                # Initialize driver with profile
                self.driver = webdriver.Chrome(service=service, options=profile_options)
                self.wait = WebDriverWait(self.driver, 15)
                self.logger.info("Initialized Chrome with user profile")
            except Exception as profile_error:
                # If profile fails, try without profile
                self.logger.warning(f"Failed to initialize with profile: {str(profile_error)}")
                self.logger.info("Trying to initialize Chrome without profile...")
                
                # Add incognito mode to avoid profile issues
                options.add_argument('--incognito')
                
                # Initialize driver without profile
                service = Service(executable_path=CHROMEDRIVER_PATH)
                self.driver = webdriver.Chrome(service=service, options=options)
                self.wait = WebDriverWait(self.driver, 15)
                self.logger.info("Initialized Chrome without user profile (incognito mode)")
            
            # Anti-detection script
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    // Override webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Add language plugins to appear more human-like
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en', 'es-ES', 'es']
                    });
                '''
            })
            
            time.sleep(1)
            self.driver.maximize_window()
            
            self.logger.info("WebDriver initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {str(e)}")
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            return False
    
    def random_delay(self, delay_type: str):
        """Add random delay between actions"""
        min_delay, max_delay = DELAYS.get(delay_type, (2, 5))
        time.sleep(random.uniform(min_delay, max_delay))

    def get_job_id_from_card(self, card) -> Optional[str]:
        """Extract job ID from card without opening job details"""
        try:
            # Try to get a unique identifier from the card
            job_url = None
            
            # First try to get the link directly
            try:
                title_link = card.find_element(By.CSS_SELECTOR, "[data-cy='card-title-link']")
                job_url = title_link.get_attribute('href')
            except NoSuchElementException:
                # Try alternative selectors
                for selector in [".card-title-link", "a.job-title", "h2 a", "h3 a"]:
                    try:
                        title_link = card.find_element(By.CSS_SELECTOR, selector)
                        job_url = title_link.get_attribute('href')
                        if job_url:
                            break
                    except:
                        continue
            
            # Extract job ID from URL or generate a hash
            if job_url:
                if '/jobs/' in job_url:
                    job_id = job_url.split('/jobs/')[1].split('/')[0]
                else:
                    job_id = hashlib.md5(job_url.encode()).hexdigest()
                
                return job_id
            else:
                # Create a hash from the card text as fallback
                card_text = card.text
                return hashlib.md5(card_text.encode()).hexdigest()
            
        except Exception as e:
            self.logger.warning(f"Could not extract job ID from card: {str(e)}")
            return None

    def check_easy_apply_available(self, card) -> bool:
        """Improved check if Easy Apply is available with proper delay and retries"""
        max_retries = MAX_RETRIES.get('status_check', 3)
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Checking for Easy Apply (attempt {attempt+1}/{max_retries})")
                
                # First delay to allow the page to fully update
                self.random_delay('status_check')
                
                # Method 1: Check for apply-button-wc web component (shadow DOM)
                apply_buttons = card.find_elements(By.TAG_NAME, "apply-button-wc")
                if apply_buttons:
                    for apply_button in apply_buttons:
                        # Check if it has an apply button in shadow DOM
                        has_apply = self.driver.execute_script("""
                            const applyButton = arguments[0];
                            if (!applyButton.shadowRoot) return false;
                            const button = applyButton.shadowRoot.querySelector('button');
                            return button && !button.disabled;
                        """, apply_button)
                        
                        if has_apply:
                            self.logger.info("Found Easy Apply in shadow DOM")
                            return True
                
                # Method 2: Look for standard Easy Apply indicators
                easy_apply_indicators = [
                    "[data-cy='easyApplyBtn']",
                    ".easy-apply-button",
                    ".easy-apply",
                    "button[class*='easyApply']",
                    "button[class*='easy-apply']"
                ]
                
                for indicator in easy_apply_indicators:
                    elements = card.find_elements(By.CSS_SELECTOR, indicator)
                    for element in elements:
                        if element.is_displayed():
                            self.logger.info(f"Found Easy Apply indicator: {indicator}")
                            return True
                
                # Method 3: Look for "Easy Apply" text
                easy_apply_elements = card.find_elements(
                    By.XPATH, 
                    ".//*[contains(translate(text(), 'EASY APPLY', 'easy apply'), 'easy apply')]"
                )
                for element in easy_apply_elements:
                    if element.is_displayed():
                        self.logger.info("Found Easy Apply text")
                        return True
                
                # If this is not the last attempt, wait longer before retry
                if attempt < max_retries - 1:
                    self.logger.info(f"Easy Apply not found, waiting before retry {attempt+1}")
                    time.sleep(2 * (attempt + 1))  # Progressive delay
                
            except Exception as e:
                self.logger.warning(f"Error checking Easy Apply availability (attempt {attempt+1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
        
        self.logger.info("Easy Apply not available after all attempts")
        return False
    
    def is_already_applied(self, card) -> bool:
        """Improved check if already applied to job with proper delay and retries"""
        max_retries = MAX_RETRIES.get('status_check', 3)
        
        try:
            # Get job ID first
            job_id = self.get_job_id_from_card(card)
            
            # First check our own tracker
            if job_id and self.tracker.is_job_applied(job_id):
                self.logger.info(f"Found job ID {job_id} in tracker as already applied")
                return True
                
            # Also check our in-memory set for this session
            if job_id in self.processed_job_ids:
                self.logger.info(f"Already processed job ID {job_id} in this session")
                return True
        except Exception as e:
            self.logger.warning(f"Error checking job ID: {str(e)}")
        
        # Proceed with UI checks with retries
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Checking if already applied (attempt {attempt+1}/{max_retries})")
                
                # Add delay to allow the page to update its status
                self.random_delay('status_check')
                
                # Method 1: Check for visible "Applied" indicators
                applied_indicators = [
                    ".ribbon-status-applied",
                    ".search-status-ribbon-mobile.ribbon-status-applied",
                    ".status-applied",
                    ".already-applied"
                ]
                
                for indicator in applied_indicators:
                    if card.find_elements(By.CSS_SELECTOR, indicator):
                        self.logger.info(f"Found applied indicator: {indicator}")
                        return True
                
                # Method 2: Check shadow DOM for "Application Submitted" text
                apply_buttons = card.find_elements(By.TAG_NAME, "apply-button-wc")
                if apply_buttons:
                    for apply_button in apply_buttons:
                        is_applied = self.driver.execute_script("""
                            const applyButton = arguments[0];
                            if (!applyButton.shadowRoot) return false;
                            
                            // Check for application-submitted component
                            const appSubmitted = applyButton.shadowRoot.querySelector('application-submitted');
                            if (appSubmitted) return true;
                            
                            // Check text content
                            const shadowText = applyButton.shadowRoot.textContent.toLowerCase();
                            return shadowText.includes('application submitted') || 
                                shadowText.includes('applied') ||
                                shadowText.includes('app submitted');
                        """, apply_button)
                        
                        if is_applied:
                            self.logger.info("Found applied status in shadow DOM")
                            return True
                
                # Method 3: Check card text
                card_text = card.text.lower()
                applied_texts = ['application submitted', 'applied', 'app submitted']
                for text in applied_texts:
                    if text in card_text:
                        self.logger.info(f"Found applied text: '{text}'")
                        return True
                
                # If this is not the last attempt, wait longer before retry
                if attempt < max_retries - 1:
                    self.logger.info(f"Applied status not found, waiting before retry {attempt+1}")
                    time.sleep(2 * (attempt + 1))  # Progressive delay
                    
            except Exception as e:
                self.logger.warning(f"Error checking applied status (attempt {attempt+1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
        
        self.logger.info("No applied status found after all attempts")
        return False
    
    def extract_job_details(self, card) -> Optional[Tuple[Dict, str]]:
        """Extract job details from card and detailed view"""
        original_window = self.driver.current_window_handle
        
        try:
            # Basic details from card
            job_details = {
                'title': 'Unknown Job',
                'company': 'Unknown Company',
                'location': 'Unknown Location'
            }
            
            # Extract title
            for selector in ["[data-cy='card-title-link']", ".card-title-link", "a.job-title", "h2 a", "h3 a"]:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, selector)
                    if title_elem:
                        job_details['title'] = title_elem.text.strip()
                        break
                except:
                    continue
            
            # Extract company
            for selector in ["[data-cy='search-result-company-name']", ".company-name", ".employer", "[data-cy='company-name']"]:
                try:
                    company_elem = card.find_element(By.CSS_SELECTOR, selector)
                    if company_elem:
                        job_details['company'] = company_elem.text.strip()
                        break
                except:
                    continue
            
            # Extract location
            for selector in ["[data-cy='search-result-location']", ".location", ".job-location"]:
                try:
                    location_elem = card.find_element(By.CSS_SELECTOR, selector)
                    if location_elem:
                        job_details['location'] = location_elem.text.strip()
                        break
                except:
                    continue
            
            # Find title link to click
            title_link = None
            for selector in ["[data-cy='card-title-link']", ".card-title-link", "a.job-title", "h2 a", "h3 a"]:
                try:
                    title_link = card.find_element(By.CSS_SELECTOR, selector)
                    if title_link:
                        break
                except:
                    continue
            
            if not title_link:
                self.logger.error("Could not find job title link to click")
                return None
            
            job_details['url'] = title_link.get_attribute('href') or ''
            
            # Click on title link to open job details
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", title_link)
                time.sleep(0.5)
                title_link.click()
            except:
                try:
                    self.driver.execute_script("arguments[0].click();", title_link)
                except Exception as e:
                    self.logger.error(f"Could not click job title link: {str(e)}")
                    return None
            
            self.random_delay('between_actions')
            
            # Switch to new window
            try:
                WebDriverWait(self.driver, 10).until(lambda d: len(d.window_handles) > 1)
                
                for window in self.driver.window_handles:
                    if window != original_window:
                        self.driver.switch_to.window(window)
                        break
            except:
                self.logger.error("Timeout waiting for new window")
                return None
            
            time.sleep(5)
            
            # Wait for job details page to load
            WebDriverWait(self.driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Extract skills
            skills = []
            
            # Try dedicated skills section first
            for selector in ["[data-cy='skillsList']", ".skills-list", ".job-skills"]:
                try:
                    skills_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    skill_items = skills_element.find_elements(By.CSS_SELECTOR, "span, li")
                    if skill_items:
                        skills = [skill.text.strip() for skill in skill_items if skill.text.strip()]
                        break
                except:
                    continue
            
            # If no skills found, try extracting from description
            if not skills:
                description_text = ''
                for selector in ["#jobDescription", ".job-description", "[data-cy='description']"]:
                    try:
                        desc_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if desc_elem:
                            description_text = desc_elem.text
                            break
                    except:
                        continue
                
                if description_text:
                    # Extract skills from description (simplified)
                    for pattern in ["Skills:", "Requirements:", "Qualifications:"]:
                        if pattern in description_text:
                            section = description_text.split(pattern, 1)[1].split("\n\n")[0]
                            candidates = [line.strip().lstrip('•-*·') for line in section.split('\n')]
                            skills = [s for s in candidates if 3 < len(s) < 50][:10]
                            if skills:
                                break
            
            # Extract description
            description = "No description available"
            for selector in ["#jobDescription", ".job-description", "[data-cy='description']"]:
                try:
                    desc_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if desc_elem:
                        description = desc_elem.text
                        if description.strip():
                            break
                except:
                    continue
            
            job_details['skills'] = skills or ["Not specified"]
            job_details['description'] = description
            
            # Generate unique job ID
            content = f"{job_details['title']}{job_details['company']}{job_details['description'][:100]}"
            job_details['job_id'] = hashlib.md5(content.encode()).hexdigest()
            
            # Add to processed jobs set
            self.processed_job_ids.add(job_details['job_id'])
            
            # Save job details
            job_file = JOBS_DIR / f"{job_details['job_id']}.json"
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job_details, f, indent=2)
            
            return job_details, original_window
            
        except Exception as e:
            self.logger.error(f"Error extracting job details: {str(e)}")
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(original_window)
            return None

    def click_easy_apply(self) -> bool:
        """Simplified method to click the Easy Apply button"""
        try:
            self.logger.info("Attempting to find and click Easy Apply button")
            
            # Take debug screenshot if in debug mode
            if DEBUG_MODE:
                debug_dir = Path('debug/easy_apply_click')
                debug_dir.mkdir(parents=True, exist_ok=True)
                self.driver.save_screenshot(f'debug/easy_apply_click/before_click_{self.jobs_processed}.png')
            
            # Method 1: Look for apply-button-wc web component
            apply_buttons = self.driver.find_elements(By.TAG_NAME, "apply-button-wc")
            if apply_buttons:
                for apply_button in apply_buttons:
                    # Try to click the button inside shadow DOM
                    clicked = self.driver.execute_script("""
                        const applyButton = arguments[0];
                        if (!applyButton.shadowRoot) return false;
                        
                        const button = applyButton.shadowRoot.querySelector('button');
                        if (button && !button.disabled) {
                            button.click();
                            return true;
                        }
                        return false;
                    """, apply_button)
                    
                    if clicked:
                        self.logger.info("Clicked button in shadow DOM")
                        time.sleep(2)
                        return True
            
            # Method 2: Standard button selectors
            button_selectors = [
                "[data-cy='easyApplyBtn']",
                ".easy-apply-button",
                "button.easy-apply",
                "a.easy-apply",
                "button[class*='easyApply']",
                "button[class*='easy-apply']",
                "button.apply-button"
            ]
            
            for selector in button_selectors:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        self.logger.info(f"Found Easy Apply button with selector: {selector}")
                        
                        # Try clicking
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                            time.sleep(0.5)
                            button.click()
                            time.sleep(1)
                            return True
                        except:
                            try:
                                self.driver.execute_script("arguments[0].click();", button)
                                time.sleep(1)
                                return True
                            except:
                                continue
            
            # Method 3: Look for any button with "Apply" text
            apply_elements = self.driver.find_elements(
                By.XPATH, 
                "//button[contains(translate(text(), 'APPLY', 'apply'), 'apply')] | //a[contains(translate(text(), 'APPLY', 'apply'), 'apply')]"
            )
            
            for element in apply_elements:
                if element.is_displayed() and element.is_enabled():
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(0.5)
                        element.click()
                        time.sleep(1)
                        return True
                    except:
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            time.sleep(1)
                            return True
                        except:
                            continue
            
            self.logger.error("Failed to find or click Easy Apply button")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking Easy Apply: {str(e)}")
            return False

    def submit_application(self, job_details: Dict) -> bool:
        """Submit job application"""
        try:
            self.logger.info(f"Generating optimized resume for {job_details['title']}")
            # Generate resume
            resume_path = self.resume_handler.generate_resume(job_details)
            if not resume_path:
                self.logger.error("Failed to generate resume")
                self.tracker.add_application(job_details, 'failed', notes="Failed to generate resume")
                return False
                
            # Generate cover letter
            self.logger.info("Generating cover letter")
            cover_letter = self.gemini.generate_cover_letter(job_details, resume_path)
            
            cover_letter_path = None
            if cover_letter:
                # Save cover letter
                resume_filename = os.path.basename(resume_path)
                base_name = os.path.splitext(resume_filename)[0]
                cover_letter_base = base_name.replace("Resume", "Cover_Letter")
                
                # Ensure unique filename
                cover_letter_filename = f"{cover_letter_base}.txt"
                counter = 1
                while (RESUME_DIR / cover_letter_filename).exists():
                    cover_letter_filename = f"{cover_letter_base}_v{counter}.txt"
                    counter += 1
                
                cover_letter_path = RESUME_DIR / cover_letter_filename
                with open(cover_letter_path, 'w') as f:
                    f.write(cover_letter)
                self.logger.info(f"Cover letter saved to {cover_letter_path}")
            
            # Click Easy Apply
            self.logger.info("Clicking Easy Apply button")
            if not self.click_easy_apply():
                self.logger.error("Failed to click Easy Apply button")
                self.tracker.add_application(
                    job_details, 'failed', resume_path, cover_letter_path,
                    notes="Failed to click Easy Apply button"
                )
                return False
                
            self.random_delay('between_actions')
            
            # Wait for application form
            application_selectors = [
                ".apply-container",
                ".application-form",
                "form[data-cy='applicationForm']",
                ".resume-container"
            ]
            
            application_container = None
            for selector in application_selectors:
                try:
                    application_container = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if application_container:
                        break
                except:
                    continue
            
            if not application_container:
                self.logger.error("Application form not found")
                self.tracker.add_application(
                    job_details, 'failed', resume_path, cover_letter_path,
                    notes="Application form not found"
                )
                return False
                
            # Handle resume upload
            self.logger.info("Handling resume upload")
            time.sleep(2)
            
            # Look for file upload element
            try:
                # Check if there's a resume container
                resume_container = None
                for selector in [".resume-container", ".file-upload-container", ".document-upload"]:
                    try:
                        resume_container = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if resume_container:
                            break
                    except:
                        continue
                
                if resume_container:
                    # Check if there's a file already selected
                    existing_file = resume_container.find_elements(By.CSS_SELECTOR, ".file-wrapper, .selected-file")
                    
                    if existing_file:
                        # Try to replace it
                        replace_buttons = resume_container.find_elements(By.CSS_SELECTOR, ".file-remove, .replace-button")
                        if replace_buttons:
                            replace_buttons[0].click()
                            time.sleep(1)
                    
                    # Look for file input in/near resume container
                    file_inputs = resume_container.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if not file_inputs:
                        # Look for file input in the entire form
                        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    
                    if file_inputs:
                        file_inputs[0].send_keys(os.path.abspath(resume_path))
                        time.sleep(2)
                else:
                    # Look for any file input
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_inputs[0].send_keys(os.path.abspath(resume_path))
                        time.sleep(2)
                    else:
                        self.logger.error("No file input found for resume")
                        self.tracker.add_application(
                            job_details, 'failed', resume_path, cover_letter_path,
                            notes="No file input found for resume"
                        )
                        return False
            except Exception as e:
                self.logger.error(f"Error handling resume upload: {str(e)}")
                
            # Handle file picker if it appeared - with improved handling for the specific modal
            try:
                # Wait for file picker modal to appear
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".fsp-modal__body, .file-picker-modal"))
                )
                
                self.logger.info("File picker modal detected")
                
                # First try the standard file input
                try:
                    file_input = self.driver.find_element(By.CSS_SELECTOR, "#fsp-fileUpload, input[type='file']")
                    file_input.send_keys(os.path.abspath(resume_path))
                    self.logger.info("Uploaded file using file input")
                    time.sleep(2)
                except:
                    # If standard file input not found, try JavaScript approach
                    self.logger.info("Standard file input not found, trying JavaScript approach")
                    # The resume is likely already uploaded and visible in the modal
                    self.logger.info("Checking for existing file in modal")
                
                # Click the Upload button - using JavaScript for more reliable clicking
                self.logger.info("Attempting to click Upload button")
                upload_clicked = self.driver.execute_script("""
                    // Look for the upload button in the modal
                    const uploadBtn = document.querySelector('.fsp-button-upload, .fsp-button--primary');
                    if (uploadBtn) {
                        uploadBtn.click();
                        return true;
                    }
                    return false;
                """)
                
                if upload_clicked:
                    self.logger.info("Successfully clicked Upload button using JavaScript")
                else:
                    # Try clicking with standard method as fallback
                    upload_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                        ".fsp-button-upload, .fsp-button--primary, .upload-button")
                    
                    for button in upload_buttons:
                        try:
                            if button.is_displayed() and 'disabled' not in button.get_attribute('class'):
                                # Scroll to the button first
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                time.sleep(0.5)
                                button.click()
                                self.logger.info("Clicked Upload button using standard method")
                                break
                        except:
                            continue
                
                # Wait for modal to disappear
                time.sleep(3)
            except Exception as e:
                self.logger.warning(f"Error handling file picker: {str(e)}")
                
            # Handle cover letter upload if available with improved modal handling
            if cover_letter_path:
                try:
                    self.logger.info("Uploading cover letter")
                    # Wait a bit to make sure the previous modal is gone
                    time.sleep(2)
                    
                    cover_letter_selectors = [
                        ".file-picker-wrapper.cover-letter",
                        ".cover-letter-container",
                        "[data-cy='coverLetterUpload']"
                    ]
                    
                    cover_letter_container = None
                    for selector in cover_letter_selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            cover_letter_container = elements[0]
                            break
                    
                    if cover_letter_container:
                        # Try to click using JavaScript first
                        self.logger.info("Found cover letter container, clicking button")
                        clicked = self.driver.execute_script("""
                            const container = arguments[0];
                            const button = container.querySelector('button');
                            if (button) {
                                button.click();
                                return true;
                            }
                            return false;
                        """, cover_letter_container)
                        
                        if not clicked:
                            # Try standard click method as fallback
                            buttons = cover_letter_container.find_elements(By.TAG_NAME, "button")
                            if buttons:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buttons[0])
                                time.sleep(0.5)
                                buttons[0].click()
                        
                        # Wait for file picker modal
                        time.sleep(2)
                        
                        # Handle file picker modal for cover letter
                        try:
                            # Wait for file picker modal
                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".fsp-modal__body, .file-picker-modal"))
                            )
                            
                            # Try to find file input 
                            file_input = self.driver.find_element(By.CSS_SELECTOR, "#fsp-fileUpload, input[type='file']")
                            file_input.send_keys(os.path.abspath(cover_letter_path))
                            time.sleep(2)
                            
                            # Click upload button using JavaScript for reliability
                            self.driver.execute_script("""
                                const uploadBtn = document.querySelector('.fsp-button-upload, .fsp-button--primary');
                                if (uploadBtn) {
                                    uploadBtn.click();
                                }
                            """)
                            
                            self.logger.info("Cover letter uploaded successfully")
                            time.sleep(3)
                        except Exception as e:
                            self.logger.warning(f"Error handling cover letter file picker: {str(e)}")
                except Exception as e:
                    self.logger.warning(f"Error uploading cover letter: {str(e)}")
            
            # Navigate through application steps
            try:
                # Look for next/submit buttons and click them
                for _ in range(3):  # Try up to 3 steps
                    button_selectors = [
                        ".navigation-buttons .btn-next",
                        ".navigation-buttons .btn-submit",
                        "button[type='submit']",
                        ".submit-button",
                        ".apply-button",
                        "button:contains('Next')",
                        "button:contains('Submit')"
                    ]
                    
                    button_found = False
                    for selector in button_selectors:
                        try:
                            buttons = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                            for button in buttons:
                                if button.is_displayed() and button.is_enabled():
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                    time.sleep(0.5)
                                    button.click()
                                    button_found = True
                                    time.sleep(2)
                                    break
                            if button_found:
                                break
                        except:
                            continue
                    
                    if not button_found:
                        break
            except Exception as e:
                self.logger.warning(f"Error navigating application steps: {str(e)}")
            
            # Verify application success
            try:
                success_indicators = [
                    ".post-apply-banner",
                    ".success-message",
                    ".application-submitted",
                    "div:contains('Application Submitted')"
                ]
                
                success = False
                for selector in success_indicators:
                    try:
                        element = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if element:
                            success = True
                            break
                    except:
                        continue
                
                if success:
                    self.logger.info("Application submitted successfully")
                    
                    # Record successful application
                    self.tracker.add_application(
                        job_details, 'success', resume_path, cover_letter_path
                    )
                    
                    self.jobs_applied += 1
                    return True
                else:
                    # Check page content for success indicators
                    page_source = self.driver.page_source.lower()
                    text_indicators = ["application submitted", "thank you for applying", "successfully applied"]
                    
                    for indicator in text_indicators:
                        if indicator in page_source:
                            self.logger.info(f"Application likely successful (found text: {indicator})")
                            self.tracker.add_application(
                                job_details, 'success', resume_path, cover_letter_path
                            )
                            self.jobs_applied += 1
                            return True
                    
                    self.logger.warning("No success confirmation found")
                    self.tracker.add_application(
                        job_details, 'failed', resume_path, cover_letter_path,
                        notes="No success confirmation found"
                    )
                    return False
            except Exception as e:
                self.logger.error(f"Error verifying application success: {str(e)}")
                self.tracker.add_application(
                    job_details, 'failed', resume_path, cover_letter_path,
                    notes=f"Error verifying success: {str(e)}"
                )
                return False
            
        except Exception as e:
            self.logger.error(f"Error submitting application: {str(e)}")
            self.tracker.add_application(
                job_details, 'failed', notes=f"Error: {str(e)}"
            )
            return False

    def process_search_results(self) -> int:
        """Process all jobs on current page with improved status checking, returns number of new jobs found"""
        new_jobs_found = 0
        try:
            # Find all job cards
            job_cards = []
            selectors = [
                "dhi-search-card[data-cy='search-card']",
                ".search-card",
                ".job-card"
            ]
            
            for selector in selectors:
                try:
                    cards = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if cards and len(cards) > 0:
                        job_cards = cards
                        self.logger.info(f"Found {len(cards)} job cards with selector: {selector}")
                        break
                except:
                    continue
            
            if not job_cards:
                self.logger.error("No job cards found on current page")
                return new_jobs_found
            
            for card in job_cards:
                self.jobs_processed += 1
                self.tracker.increment_jobs_found()
                new_jobs_found += 1
                
                # Scroll to the card to ensure it's in view
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                
                # Allow the page some time to update statuses after scrolling
                time.sleep(3)
                
                # First check if already applied - using the improved function with retries and delays
                if self.is_already_applied(card):
                    self.logger.info("Skipping already applied job")
                    self.jobs_skipped += 1
                    continue
                
                # Then check if Easy Apply is available - using the improved function with retries and delays
                if not self.check_easy_apply_available(card):
                    self.logger.info("Skipping job without Easy Apply")
                    
                    # Record this skip with basic info
                    job_id = self.get_job_id_from_card(card)
                    title = "Unknown"
                    company = "Unknown"
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, "[data-cy='card-title-link']")
                        title = title_elem.text
                    except:
                        pass
                        
                    try:
                        company_elem = card.find_element(By.CSS_SELECTOR, "[data-cy='search-result-company-name']")
                        company = company_elem.text
                    except:
                        pass
                    
                    job_info = {
                        'job_id': job_id or f"unknown_{self.jobs_processed}",
                        'title': title,
                        'company': company
                    }
                    
                    self.tracker.add_application(
                        job_info, 'skipped', notes="No Easy Apply available"
                    )
                    
                    self.jobs_skipped += 1
                    continue
                
                # Process job with Easy Apply
                result = self.extract_job_details(card)
                if not result:
                    self.jobs_skipped += 1
                    continue
                    
                job_details, original_window = result
                
                # Submit application
                application_result = self.submit_application(job_details)
                
                if application_result:
                    self.logger.info(f"Successfully applied to {job_details['title']}")
                else:
                    self.logger.warning(f"Failed to apply to {job_details['title']}")
                
                # Close detail window and return to search results
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                    
                self.random_delay('between_applications')
            
            return new_jobs_found
                
        except Exception as e:
            self.logger.error(f"Error processing search results: {str(e)}")
            # Try to get back to the search window
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return new_jobs_found
        
    def next_page_exists(self) -> bool:
        """Check if next page exists"""
        try:
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                "li.pagination-next:not(.disabled), a.next-page:not(.disabled)"
            )
            return bool(next_button)
        except:
            return False

    def go_to_next_page(self) -> bool:
        """Go to next page of results"""
        try:
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                "li.pagination-next:not(.disabled) a, a.next-page:not(.disabled)"
            )
            
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.5)
                next_button.click()
            except:
                try:
                    self.driver.execute_script("arguments[0].click();", next_button)
                except:
                    return False
                    
            self.random_delay('page_load')
            return True
        except:
            return False

    def search_jobs(self, title: str) -> bool:
        """Search for jobs with given title"""
        try:
            search_url = DICE_SEARCH_URL.format(quote(title))
            self.driver.get(search_url)
            self.random_delay('page_load')
            
            # Verify search results loaded
            results_selectors = [
                "div[id='searchDisplay-div']",
                ".job-cards-container",
                ".search-results"
            ]
            
            for selector in results_selectors:
                try:
                    results = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if results:
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error searching jobs: {str(e)}")
            return False

    def generate_summary_report(self):
        """Generate and print summary of the session"""
        report = self.tracker.generate_report()
        
        # Add session-specific stats
        session_report = [
            "",
            "Current Session Stats:",
            f"- Jobs processed: {self.jobs_processed}",
            f"- Jobs applied: {self.jobs_applied}",
            f"- Jobs skipped: {self.jobs_skipped}",
            f"- Success rate: {(self.jobs_applied / max(1, self.jobs_processed)) * 100:.1f}%",
            "",
            "Processed Job Titles:",
        ]
        
        for title, page in self.processed_titles.items():
            session_report.append(f"- {title}: processed up to page {page}")
        
        full_report = report + "\n" + "\n".join(session_report)
        
        # Print to console
        print("\n" + full_report)
        
        # Save to file
        report_dir = Path('reports')
        report_dir.mkdir(exist_ok=True)
        
        report_path = report_dir / f'application_report_{datetime.now():%Y%m%d_%H%M%S}.txt'
        with open(report_path, 'w') as f:
            f.write(full_report)
            
        return report_path

    def run(self):
        """Main execution flow with improved job title handling and API key monitoring"""
        try:
            if not self.setup_driver():
                return
                
            # Initialize the Gemini service for API key monitoring
            gemini_service = GeminiService()
                
            # Load tracking data if it exists
            tracking_file = DATA_DIR / 'tracking' / 'title_tracking.json'
            if tracking_file.exists():
                try:
                    with open(tracking_file, 'r') as f:
                        self.processed_titles = json.load(f)
                    self.logger.info(f"Loaded tracking data: {self.processed_titles}")
                except:
                    self.processed_titles = {}
            
            # Create a copy of job titles for this run
            available_titles = list(JOB_TITLES)
            random.shuffle(available_titles)
            
            # Process all titles with cycling instead of exhausting one at a time
            max_pages_per_title = 3  # Limit pages per title before cycling
            
            # Track API check frequency
            last_api_check_time = time.time()
            api_check_interval = 900  # Check API status every 15 minutes (900 seconds)
            
            while available_titles:
                # Periodically check API key status
                current_time = time.time()
                if current_time - last_api_check_time > api_check_interval:
                    self.logger.info("Checking API key status...")
                    
                    # Check if all API keys are exhausted
                    if gemini_service.are_all_keys_exhausted():
                        self.logger.error("All API keys have reached their daily limit. Stopping operation.")
                        print("\n⚠️ OPERATION HALTED: All API keys have reached their daily limit!")
                        print("Please try again tomorrow or add new API keys to config.py.")
                        
                        # Generate final report before stopping
                        report_path = self.generate_summary_report()
                        self.logger.info(f"Final report saved to: {report_path}")
                        return
                    
                    # Update last check time
                    last_api_check_time = current_time
                    
                    # Display current API usage
                    api_stats = gemini_service.get_api_usage_stats()
                    self.logger.info(f"API usage: {api_stats['total_usage']} calls today")
                    
                    current_key = None
                    for key_id, stats in api_stats['keys'].items():
                        if stats['is_current']:
                            current_key = key_id
                            current_usage = stats['usage']
                            current_limit = stats['limit']
                            current_percentage = stats['percentage']
                            
                    self.logger.info(f"Current key {current_key}: {current_usage}/{current_limit} ({current_percentage:.1f}%)")
                
                # Get next title to process
                current_title = available_titles.pop(0)
                self.logger.info(f"Processing job title: {current_title}")
                
                # Search for this title
                if not self.search_jobs(current_title):
                    continue
                
                # Get starting page (default to 1)
                current_page = 1
                max_page = current_page + max_pages_per_title
                
                # Process pages for this title
                while current_page < max_page:
                    self.logger.info(f"Processing page {current_page} for '{current_title}'")
                    new_jobs = self.process_search_results()
                    
                    self.logger.info(f"Found {new_jobs} new jobs on page {current_page}")
                    
                    # Update processed titles tracking
                    self.processed_titles[current_title] = current_page
                    
                    # Save tracking data
                    try:
                        tracking_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(tracking_file, 'w') as f:
                            json.dump(self.processed_titles, f)
                    except Exception as e:
                        self.logger.warning(f"Error saving tracking data: {str(e)}")
                    
                    # Check if all API keys are exhausted after processing each page
                    if gemini_service.are_all_keys_exhausted():
                        self.logger.error("All API keys have reached their daily limit during page processing. Stopping operation.")
                        print("\n⚠️ OPERATION HALTED: All API keys have reached their daily limit!")
                        print("Please try again tomorrow or add new API keys to config.py.")
                        
                        # Generate final report before stopping
                        report_path = self.generate_summary_report()
                        self.logger.info(f"Final report saved to: {report_path}")
                        return
                    
                    # Check if we should move to next page
                    if not self.next_page_exists():
                        break
                        
                    if not self.go_to_next_page():
                        break
                        
                    current_page += 1
                    self.random_delay('between_pages')
                
                # Put this title back at the end of the queue if it had more pages
                if self.next_page_exists():
                    available_titles.append(current_title)
                
                self.random_delay('between_actions')
                
                # If we've processed all titles once, shuffle and restart
                if not available_titles:
                    available_titles = list(JOB_TITLES)
                    random.shuffle(available_titles)
                    self.logger.info("Processed all job titles, cycling back to beginning with shuffled order")
                    
                    # Ask user if they want to continue
                    print("\nProcessed all job titles. Continue with another cycle? (y/n)")
                    user_input = input().strip().lower()
                    if user_input != 'y':
                        break
            
            # Generate summary report
            report_path = self.generate_summary_report()
            self.logger.info(f"Session report saved to: {report_path}")
                
        except Exception as e:
            self.logger.error(f"Error in main execution: {str(e)}")
            
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Browser closed")