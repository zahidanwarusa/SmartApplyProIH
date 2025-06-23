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
from webdriver_manager.chrome import ChromeDriverManager
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
        """Initialize Chrome WebDriver with automatic driver management"""
        try:
            self.logger.info("Initializing Chrome WebDriver...")
            
            # Import webdriver-manager
            from webdriver_manager.chrome import ChromeDriverManager
            
            # Create Chrome options
            options = Options()
            
            # Essential options
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Set user agent
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            # Try with user profile first
            try:
                # Add profile arguments
                user_data_dir = CHROME_PROFILE['user_data_dir']
                profile_directory = CHROME_PROFILE['profile_directory']
                
                options.add_argument(f'--user-data-dir={user_data_dir}')
                options.add_argument(f'--profile-directory={profile_directory}')
                
                # Use webdriver-manager to get the correct ChromeDriver
                service = Service(ChromeDriverManager().install())
                
                # Create driver
                self.driver = webdriver.Chrome(service=service, options=options)
                self.wait = WebDriverWait(self.driver, 15)
                
                self.logger.info("Chrome initialized successfully with user profile")
                
            except Exception as profile_error:
                self.logger.warning(f"Failed with profile: {str(profile_error)}")
                self.logger.info("Trying without profile...")
                
                # Create new options without profile
                options = Options()
                options.add_argument('--start-maximized')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
                
                # Use webdriver-manager to get the correct ChromeDriver
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                self.wait = WebDriverWait(self.driver, 15)
                
                self.logger.info("Chrome initialized successfully without profile")
            
            # Execute script to hide webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Maximize window
            self.driver.maximize_window()
            time.sleep(1)
            
            self.logger.info("WebDriver setup completed successfully")
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
        """Extract job ID from card with updated selectors for new UI"""
        try:
            # Method 1: Get the data-id attribute directly from the card (new UI)
            job_id = card.get_attribute("data-id")
            if job_id:
                return job_id
                
            # Method 2: Extract from the job link (fallback)
            try:
                job_link = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
                job_url = job_link.get_attribute("href")
                
                if '/job-detail/' in job_url:
                    job_id = job_url.split('/job-detail/')[1]
                    return job_id
            except NoSuchElementException:
                pass
                
            # Method 3: Old UI selectors (fallback)
            try:
                title_link = card.find_element(By.CSS_SELECTOR, "[data-cy='card-title-link'], a.job-title, h2 a, h3 a")
                job_url = title_link.get_attribute('href')
                if job_url and '/jobs/' in job_url:
                    job_id = job_url.split('/jobs/')[1].split('/')[0]
                    return job_id
            except NoSuchElementException:
                pass
            
            # Method 4: Create a hash from the card text as fallback
            card_text = card.text
            return hashlib.md5(card_text.encode()).hexdigest()
            
        except Exception as e:
            self.logger.warning(f"Could not extract job ID from card: {str(e)}")
            return None

    def check_easy_apply_available(self, card) -> bool:
        """Check if Easy Apply is available with improved detection for new UI"""
        max_retries = MAX_RETRIES.get('status_check', 3)
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Checking for Easy Apply (attempt {attempt+1}/{max_retries})")
                
                # First delay to allow the page to fully update
                self.random_delay('status_check')
                time.sleep(2) 
                
                # Method 1: Check for "Easy Apply" text in buttons (new UI)
                try:
                    # Look for Easy Apply text with lightning bolt icon
                    easy_apply_elements = card.find_elements(
                        By.XPATH, 
                        ".//span[contains(text(), 'Easy Apply')]"
                    )
                    if easy_apply_elements and any(elem.is_displayed() for elem in easy_apply_elements):
                        self.logger.info("Found Easy Apply text")
                        return True
                    
                    # Look for the lightning bolt icon that indicates Easy Apply
                    lightning_icons = card.find_elements(
                        By.XPATH,
                        ".//svg[contains(@viewBox, '0 0 512 512')]//path[contains(@d, 'M315.27 33 96 304h128')]"
                    )
                    if lightning_icons and any(icon.is_displayed() for icon in lightning_icons):
                        self.logger.info("Found Easy Apply lightning icon")
                        return True
                except:
                    pass
                
                # Method 2: Look for "Easy Apply" box in the new UI design
                try:
                    easy_apply_box = card.find_elements(By.CSS_SELECTOR, 
                        "div.box[aria-labelledby='easyApply-label']")
                    if easy_apply_box and any(box.is_displayed() for box in easy_apply_box):
                        self.logger.info("Found Easy Apply box")
                        return True
                except:
                    pass
                    
                # Method 3: Old UI selectors (fallback)
                for indicator in [
                    "[data-cy='easyApplyBtn']",
                    ".easy-apply-button",
                    ".easy-apply",
                    "button[class*='easyApply']",
                    "button[class*='easy-apply']"
                ]:
                    elements = card.find_elements(By.CSS_SELECTOR, indicator)
                    for element in elements:
                        if element.is_displayed():
                            self.logger.info(f"Found Easy Apply indicator: {indicator}")
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
        """Enhanced method to check if already applied to a job with new UI selectors"""
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
                
                # Method 1: Look for "Applied" text in the card
                card_text = card.text.lower()
                applied_indicators = ["applied", "application submitted", "app submitted"]
                if any(indicator in card_text for indicator in applied_indicators):
                    self.logger.info(f"Found applied text in card")
                    return True
                
                # Method 2: Check for any CSS classes that might indicate applied status
                try:
                    applied_elements = card.find_elements(
                        By.XPATH, 
                        ".//*[contains(@class, 'applied') or contains(@class, 'submitted')]"
                    )
                    if applied_elements and any(elem.is_displayed() for elem in applied_elements):
                        self.logger.info("Found applied class indicator")
                        return True
                except:
                    pass
                
                # Method 3: Old UI indicators (fallback)
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
        """Extract job details from card and detailed view with updated selectors for new UI"""
        original_window = self.driver.current_window_handle
        
        try:
            # Basic details from card
            job_details = {
                'title': 'Unknown Job',
                'company': 'Unknown Company',
                'location': 'Unknown Location'
            }
            
            # Extract title (new UI)
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
                if title_elem:
                    job_details['title'] = title_elem.text.strip()
            except NoSuchElementException:
                # Fallback to old UI selectors
                for selector in ["[data-cy='card-title-link']", ".card-title-link", "a.job-title", "h2 a", "h3 a"]:
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, selector)
                        if title_elem:
                            job_details['title'] = title_elem.text.strip()
                            break
                    except:
                        continue
            
            # Extract company (new UI)
            try:
                company_elem = card.find_element(By.CSS_SELECTOR, "a[data-rac][href*='company-profile']")
                if company_elem:
                    job_details['company'] = company_elem.text.strip()
            except NoSuchElementException:
                # Fallback to old UI selectors
                for selector in ["[data-cy='search-result-company-name']", ".company-name", ".employer", "[data-cy='company-name']"]:
                    try:
                        company_elem = card.find_element(By.CSS_SELECTOR, selector)
                        if company_elem:
                            job_details['company'] = company_elem.text.strip()
                            break
                    except:
                        continue
            
            # Extract location (new UI)
            try:
                location_elems = card.find_elements(By.CSS_SELECTOR, "p.text-sm.font-normal.text-zinc-600")
                if location_elems:
                    for loc_elem in location_elems:
                        # Filter out date info
                        if "ago" not in loc_elem.text.lower():
                            job_details['location'] = loc_elem.text.strip()
                            break
            except NoSuchElementException:
                # Fallback to old UI selectors
                for selector in ["[data-cy='search-result-location']", ".location", ".job-location"]:
                    try:
                        location_elem = card.find_element(By.CSS_SELECTOR, selector)
                        if location_elem:
                            job_details['location'] = location_elem.text.strip()
                            break
                    except:
                        continue
            
            # Find title link to click (new UI)
            title_link = None
            try:
                title_link = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
            except NoSuchElementException:
                # Fallback to old UI selectors
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
            
            # Extract skills (new UI)
            skills = []
            
            # Try new UI skills section first
            try:
                skills_element = self.driver.find_element(By.CSS_SELECTOR, "[data-cy='skillsList'], [data-testid='skillsList']")
                skill_items = skills_element.find_elements(By.CSS_SELECTOR, ".chip_chip__cYJs6 span, span, li")
                if skill_items:
                    skills = [skill.text.strip() for skill in skill_items if skill.text.strip()]
            except NoSuchElementException:
                # Try old UI selectors
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
                # Try new UI description selectors
                try:
                    desc_elem = self.driver.find_element(By.CSS_SELECTOR, "#jobDescription, [data-testid='jobDescriptionHtml']")
                    if desc_elem:
                        description_text = desc_elem.text
                except NoSuchElementException:
                    # Try old UI selectors
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
            
            # Extract description (new UI)
            description = "No description available"
            try:
                desc_elem = self.driver.find_element(By.CSS_SELECTOR, "#jobDescription, [data-testid='jobDescriptionHtml']")
                if desc_elem:
                    description = desc_elem.text
            except NoSuchElementException:
                # Fallback to old UI selectors
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
            
            # Extract or generate job ID
            if 'job_id' not in job_details or not job_details['job_id']:
                job_url = self.driver.current_url
                if '/job-detail/' in job_url:
                    job_details['job_id'] = job_url.split('/job-detail/')[1]
                else:
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
        """Click the Easy Apply button with support for shadow DOM in new UI"""
        try:
            self.logger.info("Attempting to find and click Easy Apply button")
            
            # Take debug screenshot if in debug mode
            if DEBUG_MODE:
                debug_dir = Path('debug/easy_apply_click')
                debug_dir.mkdir(parents=True, exist_ok=True)
                self.driver.save_screenshot(f'debug/easy_apply_click/before_click_{self.jobs_processed}.png')
            
            # Method 1: Look for apply-button-wc in shadow DOM (new UI)
            try:
                apply_button_wc = self.driver.find_element(By.CSS_SELECTOR, "apply-button-wc")
                
                # Access the shadow root and find the button
                clicked = self.driver.execute_script("""
                    const applyButtonWc = arguments[0];
                    if (!applyButtonWc.shadowRoot) return false;
                    
                    const applyButton = applyButtonWc.shadowRoot.querySelector('.btn-primary, button.btn');
                    if (applyButton) {
                        applyButton.click();
                        return true;
                    }
                    return false;
                """, apply_button_wc)
                
                if clicked:
                    self.logger.info("Clicked Easy Apply button in shadow DOM")
                    time.sleep(2)
                    return True
            except NoSuchElementException:
                self.logger.info("No apply-button-wc found, trying alternative methods")
                
            # Method 2: Look for Easy Apply button in job details page (new UI)
            try:
                apply_button_selectors = [
                    "a[data-rac] span:contains('Easy Apply')",
                    "a.outline-offset-2 span:contains('Easy Apply')",
                    "button:contains('Easy Apply')",
                    "div.btn-group--block button.btn-primary"
                ]
                
                for selector in apply_button_selectors:
                    try:
                        # For XPath selectors
                        if "contains" in selector:
                            xpath_selector = selector.replace(":contains('", "[contains(text(), '").replace("')", "')]")
                            buttons = self.driver.find_elements(By.XPATH, f"//{xpath_selector}")
                        else:
                            buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            
                        for button in buttons:
                            if button.is_displayed() and button.is_enabled():
                                self.logger.info(f"Found Easy Apply button with selector: {selector}")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                time.sleep(0.5)
                                button.click()
                                time.sleep(1)
                                return True
                    except:
                        continue
            except Exception as e:
                self.logger.warning(f"Error finding Easy Apply button in new UI: {str(e)}")
            
            # Method 3: Old UI selectors (fallback)
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
            
            # Method 4: Look for any button with "Apply" text
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
        """Submit job application with support for new UI"""
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
            
            # Wait for application form to appear
            application_selectors = [
                ".apply-container",
                ".application-form",
                "form[data-cy='applicationForm']",
                ".resume-container",
                "div[role='dialog']",  # New UI often uses dialog role
                ".modal-content",
                "div.rWCJ"  # Observed in the new UI
            ]
            
            application_container = None
            for selector in application_selectors:
                try:
                    application_container = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if application_container:
                        self.logger.info(f"Found application container with selector: {selector}")
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
                for selector in [".resume-container", ".file-upload-container", ".document-upload", 
                                "div[role='dialog']", ".modal-content"]:
                    try:
                        resume_container = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if resume_container:
                            self.logger.info(f"Found resume container with selector: {selector}")
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
                        self.logger.info("Uploaded resume via file input")
                        time.sleep(2)
                    else:
                        # Try to find a button that might trigger file selection
                        upload_buttons = resume_container.find_elements(
                            By.XPATH, 
                            ".//*[contains(text(), 'Upload') or contains(text(), 'Browse') or contains(text(), 'Select')]"
                        )
                        if upload_buttons:
                            upload_buttons[0].click()
                            self.logger.info("Clicked upload button to trigger file selection")
                            time.sleep(2)
                            
                            # Now try to find file input that might have appeared
                            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                            if file_inputs:
                                file_inputs[0].send_keys(os.path.abspath(resume_path))
                                self.logger.info("Uploaded resume after clicking upload button")
                                time.sleep(2)
                else:
                    # Look for any file input
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_inputs[0].send_keys(os.path.abspath(resume_path))
                        self.logger.info("Uploaded resume via file input (no container found)")
                        time.sleep(2)
                    else:
                        # Look for upload buttons
                        upload_buttons = self.driver.find_elements(
                            By.XPATH, 
                            "//*[contains(text(), 'Upload') or contains(text(), 'Browse') or contains(text(), 'Select')]"
                        )
                        if upload_buttons:
                            for button in upload_buttons:
                                try:
                                    if button.is_displayed():
                                        button.click()
                                        self.logger.info("Clicked upload button")
                                        time.sleep(2)
                                        
                                        # Now try to find file input that might have appeared
                                        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                                        if file_inputs:
                                            file_inputs[0].send_keys(os.path.abspath(resume_path))
                                            self.logger.info("Uploaded resume after clicking button")
                                            time.sleep(2)
                                            break
                                except:
                                    continue
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
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".fsp-modal__body, .file-picker-modal"))
                )
                
                self.logger.info("File picker modal detected")
                
                # First try the standard file input
                try:
                    file_input = self.driver.find_element(By.CSS_SELECTOR, "#fsp-fileUpload, input[type='file']")
                    file_input.send_keys(os.path.abspath(resume_path))
                    self.logger.info("Uploaded file using file input in modal")
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
                        ".fsp-button-upload, .fsp-button--primary, .upload-button, button:contains('Upload')")
                    
                    if not upload_buttons:
                        # Try XPath for buttons with "Upload" text
                        upload_buttons = self.driver.find_elements(By.XPATH, 
                            "//button[contains(text(), 'Upload')]")
                    
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
                        "[data-cy='coverLetterUpload']",
                        "label:contains('Cover Letter')",
                        "//label[contains(text(), 'Cover Letter')]"
                    ]
                    
                    cover_letter_container = None
                    for selector in cover_letter_selectors:
                        try:
                            if selector.startswith("//"):  # XPath selector
                                elements = self.driver.find_elements(By.XPATH, selector)
                            elif ":contains" in selector:  # Convert to XPath
                                xpath_selector = selector.replace(":contains('", "[contains(text(), '").replace("')", "')]")
                                elements = self.driver.find_elements(By.XPATH, f"//{xpath_selector}")
                            else:  # CSS selector
                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                
                            if elements:
                                cover_letter_container = elements[0]
                                self.logger.info(f"Found cover letter container with selector: {selector}")
                                break
                        except:
                            continue
                    
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
                                self.logger.info("Clicked button in cover letter container")
                            else:
                                # Try to find file input directly
                                file_inputs = cover_letter_container.find_elements(By.CSS_SELECTOR, "input[type='file']")
                                if file_inputs:
                                    file_inputs[0].send_keys(os.path.abspath(cover_letter_path))
                                    self.logger.info("Uploaded cover letter directly via file input")
                                    time.sleep(2)
                        
                        # Wait for file picker modal
                        time.sleep(2)
                        
                        # Handle file picker modal for cover letter
                        try:
                            # Wait for file picker modal
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".fsp-modal__body, .file-picker-modal"))
                            )
                            
                            # Try to find file input 
                            file_input = self.driver.find_element(By.CSS_SELECTOR, "#fsp-fileUpload, input[type='file']")
                            file_input.send_keys(os.path.abspath(cover_letter_path))
                            self.logger.info("Uploaded cover letter via file input in modal")
                            time.sleep(2)
                            
                            # Click upload button using JavaScript for reliability
                            self.driver.execute_script("""
                                const uploadBtn = document.querySelector('.fsp-button-upload, .fsp-button--primary');
                                if (uploadBtn) {
                                    uploadBtn.click();
                                    return true;
                                }
                                return false;
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
                for step in range(5):  # Try up to 5 steps - increased from 3 to handle more complex forms
                    button_selectors = [
                        # New UI selectors
                        "button.btn-primary",
                        "button.submit-application",
                        "button:contains('Next')",
                        "button:contains('Submit')",
                        "button:contains('Apply')",
                        
                        # Old UI selectors
                        ".navigation-buttons .btn-next",
                        ".navigation-buttons .btn-submit",
                        "button[type='submit']",
                        ".submit-button",
                        ".apply-button"
                    ]
                    
                    button_found = False
                    for selector in button_selectors:
                        try:
                            if "contains" in selector:
                                # Convert to XPath for text content search
                                text = selector.split("'")[1]
                                xpath_selector = f"//button[contains(text(), '{text}')]"
                                buttons = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_all_elements_located((By.XPATH, xpath_selector))
                                )
                            else:
                                buttons = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                                )
                                
                            for button in buttons:
                                if button.is_displayed() and button.is_enabled():
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                    time.sleep(0.5)
                                    button.click()
                                    self.logger.info(f"Clicked {selector} button in step {step+1}")
                                    button_found = True
                                    time.sleep(2)
                                    break
                            if button_found:
                                break
                        except:
                            continue
                    
                    if not button_found:
                        self.logger.info(f"No more buttons found after step {step+1}")
                        break
            except Exception as e:
                self.logger.warning(f"Error navigating application steps: {str(e)}")
            
            # Verify application success
            try:
                # New UI success indicators
                success_indicators = [
                    ".post-apply-banner",
                    ".success-message",
                    ".application-submitted",
                    "div:contains('Application Submitted')",
                    ".application-status",
                    ".status-applied",
                    ".confirmation-message"
                ]
                
                success = False
                for selector in success_indicators:
                    try:
                        if ":contains" in selector:
                            # Convert to XPath for text content search
                            text = selector.split("'")[1]
                            xpath_selector = f"//*[contains(text(), '{text}')]"
                            element = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, xpath_selector))
                            )
                        else:
                            element = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            
                        if element:
                            self.logger.info(f"Found success indicator: {selector}")
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
                    text_indicators = [
                        "application submitted", 
                        "thank you for applying", 
                        "successfully applied",
                        "your application has been submitted",
                        "application complete",
                        "application received"
                    ]
                    
                    for indicator in text_indicators:
                        if indicator in page_source:
                            self.logger.info(f"Application likely successful (found text: {indicator})")
                            self.tracker.add_application(
                                job_details, 'success', resume_path, cover_letter_path
                            )
                            self.jobs_applied += 1
                            return True
                    
                    # Look for visual cues like checkmarks or success icons
                    success_icon_selectors = [
                        ".success-icon",
                        ".check-icon",
                        ".status-success",
                        "svg[class*='success']",
                        "svg[class*='check']"
                    ]
                    
                    for selector in success_icon_selectors:
                        icons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if icons and any(icon.is_displayed() for icon in icons):
                            self.logger.info(f"Found success icon: {selector}")
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
        """Process all jobs on current page with updated selectors for new UI"""
        new_jobs_found = 0
        try:
            # Find all job cards (new UI)
            job_cards = []
            
            # Try new UI selectors first
            try:
                cards = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-id]"))
                )
                if cards and len(cards) > 0:
                    job_cards = cards
                    self.logger.info(f"Found {len(cards)} job cards with new UI selector: div[data-id]")
            except:
                # Fallback to old UI selectors
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
                    
                    # Try to extract title (new UI)
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
                        title = title_elem.text
                    except:
                        # Try old UI selector
                        try:
                            title_elem = card.find_element(By.CSS_SELECTOR, "[data-cy='card-title-link']")
                            title = title_elem.text
                        except:
                            pass
                    
                    # Try to extract company (new UI)
                    try:
                        company_elem = card.find_element(By.CSS_SELECTOR, "a[data-rac][href*='company-profile']")
                        company = company_elem.text
                    except:
                        # Try old UI selector
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
        """Check if next page exists with updated selectors for new UI"""
        try:
            # Try new UI selectors first
            try:
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "span[role='link'][aria-label='Next'], a[aria-label='Next']"
                )
                return not ("disabled" in next_button.get_attribute("class") or 
                           next_button.get_attribute("aria-disabled") == "true")
            except NoSuchElementException:
                # Fallback to old UI selectors
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "li.pagination-next:not(.disabled), a.next-page:not(.disabled)"
                )
                return bool(next_button)
        except:
            return False

    def go_to_next_page(self) -> bool:
        """Go to next page of results with updated selectors for new UI"""
        try:
            # Try new UI selectors first
            try:
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "span[role='link'][aria-label='Next'], a[aria-label='Next']"
                )
                
                if "disabled" in next_button.get_attribute("class") or next_button.get_attribute("aria-disabled") == "true":
                    return False
                    
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.5)
                next_button.click()
                self.logger.info("Clicked next page button (new UI)")
                self.random_delay('page_load')
                return True
            except NoSuchElementException:
                # Fallback to old UI selectors
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "li.pagination-next:not(.disabled) a, a.next-page:not(.disabled)"
                )
                
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(0.5)
                    next_button.click()
                    self.logger.info("Clicked next page button (old UI)")
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", next_button)
                        self.logger.info("Clicked next page button using JavaScript")
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
            
            # Verify search results loaded (new UI)
            results_selectors = [
                # New UI selectors
                "div[data-testid='jobSearchResultsContainer']",
                "div.max-w-[1400px]",
                
                # Old UI selectors
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
                        self.logger.info(f"Search results loaded with selector: {selector}")
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

    def analyze_page_structure(self):
        """Debug helper method to analyze page structure and save elements info"""
        debug_dir = Path('debug/page_structure')
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Take screenshot of the page
        self.driver.save_screenshot(f'{debug_dir}/page_screenshot.png')
        
        # Save page source
        with open(f'{debug_dir}/page_source.html', 'w', encoding='utf-8') as f:
            f.write(self.driver.page_source)
        
        # Analyze key elements
        elements_to_analyze = [
            {"name": "job_cards", "selectors": ["div[data-id]", "dhi-search-card[data-cy='search-card']", ".search-card"]},
            {"name": "apply_buttons", "selectors": ["a[data-rac] span:contains('Easy Apply')", "[data-cy='easyApplyBtn']", ".easy-apply-button"]},
            {"name": "pagination", "selectors": ["span[role='link'][aria-label='Next']", "li.pagination-next"]}
        ]
        
        analysis_results = []
        for element_type in elements_to_analyze:
            name = element_type["name"]
            selectors = element_type["selectors"]
            
            analysis_results.append(f"\n--- {name} Analysis ---")
            
            for selector in selectors:
                try:
                    if ":contains" in selector:
                        # Convert to XPath for text content search
                        text = selector.split("'")[1]
                        xpath_selector = f"//*[contains(text(), '{text}')]"
                        elements = self.driver.find_elements(By.XPATH, xpath_selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                    if elements:
                        analysis_results.append(f"Selector {selector}: Found {len(elements)} elements")
                        # Get more details about the first element
                        if len(elements) > 0:
                            elem = elements[0]
                            try:
                                displayed = elem.is_displayed()
                                enabled = elem.is_enabled()
                                tag_name = elem.tag_name
                                attributes = self.driver.execute_script(
                                    'var items = {}; for (var i = 0; i < arguments[0].attributes.length; i++) { items[arguments[0].attributes[i].name] = arguments[0].attributes[i].value }; return items;', 
                                    elem
                                )
                                analysis_results.append(f"  First element: {tag_name}, Displayed: {displayed}, Enabled: {enabled}")
                                analysis_results.append(f"  Attributes: {json.dumps(attributes, indent=2)}")
                            except:
                                analysis_results.append(f"  Error getting details for first element")
                    else:
                        analysis_results.append(f"Selector {selector}: No elements found")
                except Exception as e:
                    analysis_results.append(f"Selector {selector}: Error - {str(e)}")
        
        # Save analysis results
        with open(f'{debug_dir}/element_analysis.txt', 'w', encoding='utf-8') as f:
            f.write("\n".join(analysis_results))
            
        self.logger.info("Page structure analysis completed and saved to debug directory")
        return analysis_results

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