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
        """Chrome WebDriver initialization with configurable headless mode"""
        try:
            from config import HEADLESS_MODE
            
            mode_text = "headless" if HEADLESS_MODE else "visible"
            self.logger.info(f"Starting Chrome in {mode_text} mode...")
            
            options = Options()
            
            if HEADLESS_MODE:
                options.add_argument('--headless')
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
            else:
                options.add_argument('--start-maximized')
            
            # Common options for both modes
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 15)
            
            # Hide the fact that this is automated (helps with detection)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("Chrome started successfully with fresh profile")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Chrome: {str(e)}")
            return False

    def login_to_dice(self) -> bool:
        """Handle the two-step Dice login process"""
        try:
            from config import DICE_LOGIN
            
            self.logger.info("Starting Dice login process...")
            
            # Navigate to login page
            self.driver.get("https://www.dice.com/dashboard/login")
            time.sleep(3)  # Allow page to load
            
            # Step 1: Enter email and click Continue
            self.logger.info("Entering email address...")
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            email_input.clear()
            email_input.send_keys(DICE_LOGIN['email'])
            
            # Click Continue button
            continue_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='sign-in-button']")
            continue_button.click()
            time.sleep(3)  # Wait for password form to appear
            
            # Step 2: Enter password and click Sign In
            self.logger.info("Entering password...")
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            password_input.clear()
            password_input.send_keys(DICE_LOGIN['password'])
            
            # Click Sign In button
            signin_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='submit-password']")
            signin_button.click()
            time.sleep(10)  # Wait for login to complete
            
            # Step 3: Verify successful login
            return self.verify_login_success()
            
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False

    def verify_login_success(self) -> bool:
        """Verify that login was successful by checking for user name"""
        try:
            # Check if we're on the home feed page
            if "home-feed" in self.driver.current_url:
                self.logger.info("Successfully reached home feed page")
                
                # Look for the user name in the dropdown to confirm login
                try:
                    user_dropdown = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Zahid Anwar')]"))
                    )
                    self.logger.info("Login verified - user name found in header")
                    return True
                except:
                    self.logger.warning("On home feed but couldn't find user name - assuming login worked")
                    return True
            else:
                self.logger.error(f"Login may have failed - current URL: {self.driver.current_url}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying login: {str(e)}")
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
                self.logger.debug(f"Found job ID from data-id: {job_id}")
                return job_id
                
            # Method 2: Get the data-job-guid attribute (new UI)
            job_guid = card.get_attribute("data-job-guid")
            if job_guid:
                self.logger.debug(f"Found job ID from data-job-guid: {job_guid}")
                return job_guid
                
            # Method 3: Extract from the job link URL (new UI)
            try:
                job_link = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
                job_url = job_link.get_attribute("href")
                
                if '/job-detail/' in job_url:
                    job_id = job_url.split('/job-detail/')[1]
                    self.logger.debug(f"Found job ID from URL: {job_id}")
                    return job_id
            except NoSuchElementException:
                pass
                
            # Method 4: Old UI selectors (fallback)
            try:
                title_link = card.find_element(By.CSS_SELECTOR, "[data-cy='card-title-link'], a.job-title, h2 a, h3 a")
                job_url = title_link.get_attribute('href')
                if job_url and '/jobs/' in job_url:
                    job_id = job_url.split('/jobs/')[1].split('/')[0]
                    self.logger.debug(f"Found job ID from fallback URL: {job_id}")
                    return job_id
            except NoSuchElementException:
                pass
            
            # Method 5: Create a hash from the card text as last resort
            card_text = card.text
            job_id = hashlib.md5(card_text.encode()).hexdigest()
            self.logger.debug(f"Generated hash-based job ID: {job_id}")
            return job_id
            
        except Exception as e:
            self.logger.warning(f"Could not extract job ID from card: {str(e)}")
            return None
    
    def check_easy_apply_available(self, card) -> bool:
        """Check if Easy Apply is available with improved detection for new UI"""
        max_retries = MAX_RETRIES.get('status_check', 3)
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Checking for Easy Apply (attempt {attempt+1}/{max_retries})")
                
                # Allow the page to fully update
                self.random_delay('status_check')
                time.sleep(2) 
                
                # Method 1: Check for Easy Apply text with lightning bolt SVG (new UI)
                try:
                    # Look for the lightning bolt SVG path that indicates Easy Apply
                    lightning_svg_path = 'M315.27 33 96 304h128l-31.51 173.23a2.36 2.36 0 0 0 2.33 2.77h0a2.36 2.36 0 0 0 1.89-.95L416 208H288l31.66-173.25a2.45 2.45 0 0 0-2.44-2.75h0a2.42 2.42 0 0 0-1.95 1z'
                    
                    lightning_elements = card.find_elements(
                        By.XPATH,
                        f".//svg//path[@d='{lightning_svg_path}']"
                    )
                    
                    for lightning in lightning_elements:
                        # Check if this SVG is part of an Easy Apply button
                        parent_element = lightning
                        for _ in range(5):  # Check up to 5 levels up
                            parent_element = parent_element.find_element(By.XPATH, "..")
                            if parent_element.tag_name in ['a', 'button']:
                                parent_text = parent_element.text.lower()
                                if 'easy apply' in parent_text and parent_element.is_displayed():
                                    self.logger.info("Found Easy Apply via lightning bolt SVG")
                                    return True
                                break
                except Exception as e:
                    self.logger.debug(f"Lightning SVG check failed: {e}")
                
                # Method 2: Look for "Easy Apply" text in buttons/links (new UI)
                try:
                    easy_apply_elements = card.find_elements(
                        By.XPATH, 
                        ".//a[contains(text(), 'Easy Apply')] | .//button[contains(text(), 'Easy Apply')] | .//span[contains(text(), 'Easy Apply')]"
                    )
                    
                    for elem in easy_apply_elements:
                        # Check if the element or its parent is clickable and visible
                        clickable_parent = elem
                        for _ in range(3):  # Check element and up to 2 levels up
                            if clickable_parent.tag_name in ['a', 'button'] and clickable_parent.is_displayed():
                                self.logger.info("Found Easy Apply text element")
                                return True
                            try:
                                clickable_parent = clickable_parent.find_element(By.XPATH, "..")
                            except:
                                break
                except Exception as e:
                    self.logger.debug(f"Easy Apply text check failed: {e}")
                
                # Method 3: Look for Easy Apply indicator box (mobile/small screens)
                try:
                    easy_apply_box = card.find_elements(By.CSS_SELECTOR, 
                        "div.box[aria-labelledby='easyApply-label'], p[id='easyApply-label']")
                        
                    for box in easy_apply_box:
                        if box.is_displayed() and 'easy apply' in box.text.lower():
                            self.logger.info("Found Easy Apply indicator box")
                            return True
                except Exception as e:
                    self.logger.debug(f"Easy Apply box check failed: {e}")
                    
                # Method 4: Old UI selectors (fallback)
                old_selectors = [
                    "[data-cy='easyApplyBtn']",
                    ".easy-apply-button",
                    ".easy-apply",
                    "button[class*='easyApply']",
                    "button[class*='easy-apply']"
                ]
                
                for selector in old_selectors:
                    try:
                        elements = card.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed():
                                self.logger.info(f"Found Easy Apply with fallback selector: {selector}")
                                return True
                    except:
                        continue
                
                # If this is not the last attempt, wait before retry
                if attempt < max_retries - 1:
                    self.logger.debug(f"Easy Apply not found, waiting before retry {attempt+1}")
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
            # Get job ID first and check our tracker
            job_id = self.get_job_id_from_card(card)
            
            # Check our own tracker first
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
                self.logger.debug(f"Checking if already applied (attempt {attempt+1}/{max_retries})")
                
                # Add delay to allow the page to update its status
                self.random_delay('status_check')
                
                # Method 1: Look for "Applied" text with checkmark SVG (new UI)
                try:
                    # Look for the checkmark SVG path that indicates Applied status
                    checkmark_svg_paths = [
                        'M448 256c0-106-86-192-192-192S64 150 64 256s86 192 192 192 192-86 192-192z',  # Circle
                        'M352 176 217.6 336 160 272'  # Checkmark
                    ]
                    
                    for svg_path in checkmark_svg_paths:
                        checkmark_elements = card.find_elements(
                            By.XPATH,
                            f".//svg//path[@d='{svg_path}']"
                        )
                        
                        for checkmark in checkmark_elements:
                            # Check if this SVG is part of an Applied button
                            parent_element = checkmark
                            for _ in range(5):  # Check up to 5 levels up
                                parent_element = parent_element.find_element(By.XPATH, "..")
                                if parent_element.tag_name in ['a', 'button']:
                                    parent_text = parent_element.text.lower()
                                    if 'applied' in parent_text and parent_element.is_displayed():
                                        self.logger.info("Found Applied status via checkmark SVG")
                                        return True
                                    break
                except Exception as e:
                    self.logger.debug(f"Checkmark SVG check failed: {e}")
                
                # Method 2: Look for "Applied" text in the card
                card_text = card.text.lower()
                applied_indicators = ["applied", "application submitted", "app submitted"]
                if any(indicator in card_text for indicator in applied_indicators):
                    self.logger.info(f"Found applied text in card")
                    return True
                
                # Method 3: Look for Applied text in buttons/links
                try:
                    applied_elements = card.find_elements(
                        By.XPATH, 
                        ".//a[contains(text(), 'Applied')] | .//button[contains(text(), 'Applied')] | .//span[contains(text(), 'Applied')]"
                    )
                    
                    for elem in applied_elements:
                        if elem.is_displayed():
                            self.logger.info("Found Applied text element")
                            return True
                except Exception as e:
                    self.logger.debug(f"Applied text check failed: {e}")
                
                # Method 4: Check for any CSS classes that might indicate applied status
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
                
                # Method 5: Old UI indicators (fallback)
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
                
                # If this is not the last attempt, wait before retry
                if attempt < max_retries - 1:
                    self.logger.debug(f"Applied status not found, waiting before retry {attempt+1}")
                    time.sleep(2 * (attempt + 1))  # Progressive delay
                    
            except Exception as e:
                self.logger.warning(f"Error checking applied status (attempt {attempt+1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
        
        self.logger.debug("No applied status found after all attempts")
        return False

    def _verify_easy_apply_on_details_page(self) -> bool:
        """
        Verify that Easy Apply is actually available on the job details page by checking 
        the shadow DOM content of apply-button-wc element
        """
        try:
            # Give the page a moment to fully load the shadow DOM content
            time.sleep(3)
            
            # Look for the apply-button-wc element
            apply_button_wc = self.driver.find_element(By.CSS_SELECTOR, "apply-button-wc")
            
            if not apply_button_wc:
                self.logger.warning("apply-button-wc element not found on job details page")
                return False
            
            # Check the shadow DOM content to determine the actual status
            shadow_content_check = self.driver.execute_script("""
                const applyButtonWc = arguments[0];
                if (!applyButtonWc.shadowRoot) {
                    return {status: 'no_shadow_root', content: ''};
                }
                
                // Check for application-submitted element (already applied)
                const applicationSubmitted = applyButtonWc.shadowRoot.querySelector('application-submitted');
                if (applicationSubmitted) {
                    const submittedText = applicationSubmitted.textContent || '';
                    return {
                        status: 'already_applied', 
                        content: submittedText,
                        element: 'application-submitted'
                    };
                }
                
                // Check for apply-button element (can still apply)
                const applyButton = applyButtonWc.shadowRoot.querySelector('apply-button');
                if (applyButton) {
                    const buttonText = applyButton.textContent || '';
                    return {
                        status: 'can_apply', 
                        content: buttonText,
                        element: 'apply-button'
                    };
                }
                
                // Check for any button with "Easy Apply" text
                const easyApplyBtn = applyButtonWc.shadowRoot.querySelector('button.btn-primary');
                if (easyApplyBtn && easyApplyBtn.textContent.includes('Easy apply')) {
                    return {
                        status: 'can_apply', 
                        content: easyApplyBtn.textContent,
                        element: 'button.btn-primary'
                    };
                }
                
                // Get all content for debugging
                const allContent = applyButtonWc.shadowRoot.innerHTML;
                return {
                    status: 'unknown', 
                    content: allContent,
                    element: 'unknown'
                };
            """, apply_button_wc)
            
            self.logger.debug(f"Shadow DOM check result: {shadow_content_check}")
            
            status = shadow_content_check.get('status', 'unknown')
            content = shadow_content_check.get('content', '')
            element = shadow_content_check.get('element', '')
            
            if status == 'already_applied':
                self.logger.info(f"Job already applied - found 'application-submitted' in shadow DOM: {content}")
                return False
            elif status == 'can_apply':
                self.logger.info(f"Easy Apply available - found '{element}' in shadow DOM: {content}")
                return True
            elif status == 'no_shadow_root':
                self.logger.warning("No shadow root found in apply-button-wc element")
                return False
            else:
                self.logger.warning(f"Unknown shadow DOM content: {content}")
                # Try to determine from content
                if any(phrase in content.lower() for phrase in ['application submitted', 'already applied', 'applied']):
                    self.logger.info("Detected already applied from shadow DOM content")
                    return False
                elif any(phrase in content.lower() for phrase in ['easy apply', 'apply']):
                    self.logger.info("Detected Easy Apply available from shadow DOM content")
                    return True
                else:
                    self.logger.warning("Could not determine application status from shadow DOM")
                    return False
                    
        except NoSuchElementException:
            self.logger.warning("apply-button-wc element not found on job details page")
            return False
        except Exception as e:
            self.logger.error(f"Error verifying Easy Apply on details page: {str(e)}")
            return False

    def _extract_job_id_from_url(self) -> Optional[str]:
        """Extract job ID from current URL"""
        try:
            current_url = self.driver.current_url
            if '/job-detail/' in current_url:
                return current_url.split('/job-detail/')[1].split('?')[0]
            return None
        except Exception as e:
            self.logger.warning(f"Could not extract job ID from URL: {str(e)}")
            return None

    def extract_job_details(self, card) -> Optional[Tuple[Dict, str]]:
        """Extract job details from card and detailed view with early application status verification"""
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
            
            # Extract location (new UI) - filter out dates
            try:
                location_elems = card.find_elements(By.CSS_SELECTOR, "p.text-sm.font-normal.text-zinc-600")
                if location_elems:
                    for loc_elem in location_elems:
                        text = loc_elem.text.strip()
                        # Filter out date information (contains "ago", "Yesterday", "Today", etc.)
                        date_indicators = ["ago", "yesterday", "today", "•"]
                        if not any(indicator in text.lower() for indicator in date_indicators) and len(text) > 2:
                            job_details['location'] = text
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
            
            # Wait for job details page to load
            time.sleep(5)
            WebDriverWait(self.driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # *** CRITICAL NEW CHECK: Verify Easy Apply is still available on job details page ***
            self.logger.info(f"Verifying Easy Apply availability on job details page for: {job_details['title']}")
            
            if not self._verify_easy_apply_on_details_page():
                self.logger.warning(f"Job details page shows already applied or no Easy Apply available: {job_details['title']}")
                
                # Create basic job info for tracking
                job_id = self._extract_job_id_from_url()
                job_details['job_id'] = job_id or hashlib.md5(f"{job_details['title']}{job_details['company']}".encode()).hexdigest()
                
                # Record this as already applied
                self.tracker.add_application(
                    job_details, 'skipped', 
                    notes="Already applied (discovered on job details page)"
                )
                
                # Close detail window and return to search results
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                
                return None  # Don't proceed with full extraction
            
            self.logger.info(f"Easy Apply confirmed available on job details page: {job_details['title']}")
            
            # Now proceed with full job details extraction since we know we can apply
            
            # Extract skills (new UI)
            skills = []
            
            # Try new UI skills section first
            try:
                skills_element = self.driver.find_element(By.CSS_SELECTOR, "[data-cy='skillsList'], [data-testid='skillsList']")
                skill_items = skills_element.find_elements(By.CSS_SELECTOR, ".chip_chip__cYJs6 span, span[id^='skillChip:'], li")
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
                job_details['job_id'] = self._extract_job_id_from_url()
                if not job_details['job_id']:
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

    def debug_search_page(self):
        """Debug helper to analyze what's on the search results page"""
        try:
            self.logger.info("=== DEBUG: Analyzing search results page ===")
            
            # Check for results container
            containers = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='job-search-results-container']")
            self.logger.info(f"Found {len(containers)} results containers")
            
            # Check for various job card selectors
            selectors_to_check = [
                "div[data-testid='job-search-serp-card']",
                "div[data-id]",
                "div[role='listitem']",
                "[data-cy='search-card']"
            ]
            
            for selector in selectors_to_check:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                self.logger.info(f"Selector '{selector}': found {len(elements)} elements")
                
                if elements and len(elements) > 0:
                    # Log details about first element
                    first_elem = elements[0]
                    try:
                        self.logger.info(f"  First element text preview: {first_elem.text[:100]}...")
                        self.logger.info(f"  First element data-id: {first_elem.get_attribute('data-id')}")
                        self.logger.info(f"  First element data-testid: {first_elem.get_attribute('data-testid')}")
                    except:
                        pass
            
            # Check page title and URL
            self.logger.info(f"Current URL: {self.driver.current_url}")
            self.logger.info(f"Page title: {self.driver.title}")
            
            # Look for any error messages or "no results" indicators
            no_results_selectors = [
                "[data-cy='no-results']",
                ".no-results",
                "text*='No jobs found'",
                "text*='0 results'"
            ]
            
            for selector in no_results_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    self.logger.warning(f"Found 'no results' indicator: {selector}")
            
            self.logger.info("=== END DEBUG ===")
            
        except Exception as e:
            self.logger.error(f"Error in debug_search_page: {str(e)}")

    def process_search_results(self) -> int:
        """Process all jobs on current page with enhanced debugging for new UI"""
        new_jobs_found = 0
        try:
            self.logger.info("Starting to process search results...")
            
            # Wait for the results container to load first
            try:
                results_container = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='job-search-results-container']"))
                )
                self.logger.info("Found job search results container")
            except TimeoutException:
                self.logger.error("Could not find job search results container")
                return new_jobs_found
            
            # Wait a bit more for dynamic content to load
            time.sleep(3)
            
            # Try multiple selectors in order of preference
            job_cards = []
            selectors_to_try = [
                # New UI - most specific
                "div[data-testid='job-search-serp-card'][data-id]",
                # New UI - less specific
                "div[data-testid='job-search-serp-card']",
                # New UI - by role
                "div[role='listitem'] div[data-testid='job-search-serp-card']",
                # New UI - by data-id only
                "div[data-id]",
                # Old UI fallbacks
                "dhi-search-card[data-cy='search-card']",
                ".search-card",
                ".job-card"
            ]
            
            for selector in selectors_to_try:
                try:
                    self.logger.info(f"Trying selector: {selector}")
                    cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if cards and len(cards) > 0:
                        # Filter out any cards that might not be actual job cards
                        valid_cards = []
                        for card in cards:
                            try:
                                # Check if card has job-related content
                                card_text = card.text.strip()
                                if len(card_text) > 50:  # Job cards should have substantial content
                                    valid_cards.append(card)
                            except:
                                continue
                        
                        if valid_cards:
                            job_cards = valid_cards
                            self.logger.info(f"Found {len(job_cards)} valid job cards with selector: {selector}")
                            break
                    else:
                        self.logger.debug(f"No cards found with selector: {selector}")
                        
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {str(e)}")
                    continue
            
            if not job_cards:
                self.logger.error("No job cards found with any selector")
                # Debug: Save page source for analysis
                try:
                    debug_dir = Path('debug')
                    debug_dir.mkdir(exist_ok=True)
                    with open(debug_dir / f'no_cards_found_{datetime.now():%Y%m%d_%H%M%S}.html', 'w', encoding='utf-8') as f:
                        f.write(self.driver.page_source)
                    self.logger.info("Saved page source to debug directory for analysis")
                except:
                    pass
                return new_jobs_found
            
            self.logger.info(f"Processing {len(job_cards)} job cards...")
            
            for i, card in enumerate(job_cards):
                try:
                    self.logger.info(f"Processing job card {i+1}/{len(job_cards)}")
                    
                    self.jobs_processed += 1
                    self.tracker.increment_jobs_found()
                    new_jobs_found += 1
                    
                    # Scroll to the card to ensure it's in view
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    
                    # Allow the page some time to update statuses after scrolling
                    time.sleep(3)
                    
                    # Get basic job info for logging
                    job_title = "Unknown"
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
                        job_title = title_elem.text.strip()
                    except:
                        try:
                            title_elem = card.find_element(By.CSS_SELECTOR, "[data-cy='card-title-link']")
                            job_title = title_elem.text.strip()
                        except:
                            pass
                    
                    self.logger.info(f"Processing job: {job_title}")
                    
                    # Check if already applied first
                    if self.is_already_applied(card):
                        self.logger.info(f"Skipping already applied job: {job_title}")
                        self.jobs_skipped += 1
                        continue
                    
                    # Then check if Easy Apply is available
                    if not self.check_easy_apply_available(card):
                        self.logger.info(f"Skipping job without Easy Apply: {job_title}")
                        
                        # Record this skip with basic info
                        job_id = self.get_job_id_from_card(card)
                        company = "Unknown"
                        
                        # Try to extract company
                        try:
                            company_elem = card.find_element(By.CSS_SELECTOR, "a[data-rac][href*='company-profile']")
                            company = company_elem.text.strip()
                        except:
                            try:
                                company_elem = card.find_element(By.CSS_SELECTOR, "[data-cy='search-result-company-name']")
                                company = company_elem.text.strip()
                            except:
                                pass
                        
                        job_info = {
                            'job_id': job_id or f"unknown_{self.jobs_processed}",
                            'title': job_title,
                            'company': company
                        }
                        
                        self.tracker.add_application(
                            job_info, 'skipped', notes="No Easy Apply available"
                        )
                        
                        self.jobs_skipped += 1
                        continue
                    
                    # Process job with Easy Apply
                    self.logger.info(f"Found Easy Apply job, extracting details: {job_title}")
                    result = self.extract_job_details(card)
                    if not result:
                        self.logger.warning(f"Failed to extract job details for: {job_title}")
                        self.jobs_skipped += 1
                        continue
                        
                    job_details, original_window = result
                    
                    # Submit application
                    self.logger.info(f"Submitting application for: {job_details['title']}")
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
                    
                except Exception as e:
                    self.logger.error(f"Error processing job card {i+1}: {str(e)}")
                    # Try to get back to the search window if we're in a detail window
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                    continue
            
            self.logger.info(f"Completed processing {len(job_cards)} job cards. Found {new_jobs_found} new jobs.")
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
        """Search for jobs with given title and enhanced debugging"""
        try:
            search_url = DICE_SEARCH_URL.format(quote(title))
            self.logger.info(f"Navigating to search URL: {search_url}")
            self.driver.get(search_url)
            self.random_delay('page_load')
            
            # Wait longer for the new UI to load completely
            time.sleep(5)
            
            # Verify search results loaded (new UI)
            results_selectors = [
                # New UI selectors
                "div[data-testid='jobSearchResultsContainer']",
                "div[data-testid='job-search-results-container']",
                "div.max-w-[1400px]",
                
                # Old UI selectors
                "div[id='searchDisplay-div']",
                ".job-cards-container",
                ".search-results"
            ]
            
            results_found = False
            for selector in results_selectors:
                try:
                    results = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if results:
                        self.logger.info(f"Search results loaded with selector: {selector}")
                        results_found = True
                        break
                except:
                    continue
            
            if not results_found:
                self.logger.error("Could not verify search results loaded")
                return False
            
            # Add debug analysis
            if DEBUG_MODE:
                self.debug_search_page()
            
            return True
                
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
            
                
            # Login to Dice
            if not self.login_to_dice():
                self.logger.error("Failed to login to Dice")
                return
                
            self.logger.info("Successfully logged in - proceeding with job search...")
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
            max_pages_per_title = 50  # Limit pages per title before cycling
            
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