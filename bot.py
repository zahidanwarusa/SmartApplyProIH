import os
import json
import time
import random
import logging
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple
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
    JOBS_DIR
)
from resume_handler import ResumeHandler
from gemini_service import GeminiService

class DiceBot:
    """Automated job application bot for Dice.com"""
    
    def __init__(self):
        self.setup_logging()
        self.resume_handler = ResumeHandler()
        self.gemini = GeminiService()
        self.driver = None
        self.wait = None
        
    def setup_logging(self):
        """Configure logging"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
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
        """Initialize Chrome WebDriver"""
        try:
            options = Options()
            
            # Set profile paths
            user_data_dir = 'C:\\Users\\ABC\\AppData\\Local\\Google\\Chrome\\User Data'
            profile_directory = 'Profile 1'
            
            # Basic Chrome options
            options.add_argument(f'--user-data-dir={user_data_dir}')
            options.add_argument(f'--profile-directory={profile_directory}')
            
            # Window management options
            options.add_argument('--start-maximized')
            options.add_argument('--disable-extensions')
            options.add_argument('--window-size=1920,1080')
            
            # SSL and security options
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--allow-insecure-localhost')
            options.add_argument('--ignore-ssl-errors')
            
            # Graphics and performance options
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-webgl')
            options.add_argument('--disable-software-rasterizer')
            
            # Anti-detection options
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_experimental_option('detach', True)
            
            # Additional stability options
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-backgrounding-occluded-windows')
            
            # Initialize ChromeDriver service
            service = Service(
                executable_path=r"webdriver\\chromedriver.exe",
                log_path="chromedriver.log"
            )
            
            # Close any existing Chrome processes
            os.system("taskkill /f /im chrome.exe")
            time.sleep(2)
            
            # Initialize driver
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 15)
            
            # Anti-detection script
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Add irregular mouse movements
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                '''
            })
            
            # Wait for window to be properly initialized
            time.sleep(3)
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

    def extract_job_details(self, card) -> Optional[Tuple[Dict, str]]:
        """Extract job details from card and detailed view"""
        original_window = self.driver.current_window_handle
        
        try:
            # Basic details from card
            job_details = {
                'title': card.find_element(
                    By.CSS_SELECTOR,
                    "[data-cy='card-title-link']"
                ).text,
                'company': card.find_element(
                    By.CSS_SELECTOR,
                    "[data-cy='search-result-company-name']"
                ).text,
                'location': card.find_element(
                    By.CSS_SELECTOR,
                    "[data-cy='search-result-location']"
                ).text
            }
            
            # Open detailed view
            title_link = card.find_element(
                By.CSS_SELECTOR,
                "[data-cy='card-title-link']"
            )
            job_details['url'] = title_link.get_attribute('href')
            title_link.click()
            
            self.random_delay('between_actions')
            
            # Switch to new window
            for window in self.driver.window_handles:
                if window != original_window:
                    self.driver.switch_to.window(window)
                    break
            
            # Extract skills
            skills_element = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-cy='skillsList']")
                )
            )
            job_details['skills'] = [
                skill.text for skill in skills_element.find_elements(
                    By.CSS_SELECTOR,
                    "span[id^='skillChip']"
                )
            ]
            
            # Extract description
            description = self.wait.until(
                EC.presence_of_element_located(
                    (By.ID, "jobDescription")
                )
            )
            job_details['description'] = description.text
            
            # Generate unique job ID
            content = f"{job_details['title']}{job_details['company']}{job_details['description']}"
            job_details['job_id'] = hashlib.md5(content.encode()).hexdigest()
            
            # Save job details
            job_file = JOBS_DIR / f"{job_details['job_id']}.json"
            with open(job_file, 'w') as f:
                json.dump(job_details, f, indent=2)
            
            # Important: Don't close the window - we need it for applying!
            return job_details, original_window
            
        except Exception as e:
            self.logger.error(f"Error extracting job details: {str(e)}")
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(original_window)
            return None

    def is_already_applied(self, card) -> bool:
        """Check if already applied to job"""
        try:
            applied_indicators = [
                ".ribbon-status-applied",
                ".search-status-ribbon-mobile.ribbon-status-applied",
                ".status-applied",
                ".already-applied"
            ]
            
            for indicator in applied_indicators:
                if card.find_elements(By.CSS_SELECTOR, indicator):
                    return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking applied status: {str(e)}")
            return False

    def wait_for_element_with_retry(self, by, selector, timeout=15, retries=2):
        """Wait for element with retries"""
        for attempt in range(retries + 1):
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                return element
            except (TimeoutException, StaleElementReferenceException):
                if attempt < retries:
                    self.logger.warning(f"Retry {attempt + 1} waiting for element: {selector}")
                    time.sleep(2)
                else:
                    return None
        return None

    def click_easy_apply(self) -> bool:
        """Click the Easy Apply button"""
        try:
            button_selectors = [
                (By.TAG_NAME, "apply-button-wc"),
                (By.CSS_SELECTOR, "[data-cy='easyApplyBtn']"),
                (By.CSS_SELECTOR, "button.easy-apply"),
                (By.CSS_SELECTOR, "button.job-app")
            ]
            
            for by, selector in button_selectors:
                try:
                    button = self.wait_for_element_with_retry(by, selector)
                    
                    if button:
                        self.logger.info(f"Found Easy Apply button with selector: {selector}")
                        if by == By.TAG_NAME and selector == "apply-button-wc":
                            shadow_root = self.driver.execute_script(
                                'return arguments[0].shadowRoot',
                                button
                            )
                            if shadow_root:
                                shadow_button = shadow_root.find_element(
                                    By.CSS_SELECTOR,
                                    "button"
                                )
                                return self.click_with_retry(shadow_button)
                        else:
                            return self.click_with_retry(button)
                except Exception as e:
                    self.logger.warning(f"Error with selector {selector}: {str(e)}")
                    continue
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking Easy Apply: {str(e)}")
            return False

    def submit_application(self, job_details: Dict) -> bool:
        """Submit job application"""
        try:
            self.logger.info(f"Generating optimized resume for {job_details['title']}")
            # Generate optimized resume
            resume_path = self.resume_handler.generate_resume(job_details)
            if not resume_path:
                self.logger.error("Failed to generate resume")
                return False
                
            self.logger.info("Generating cover letter")
            # Generate cover letter
            cover_letter = self.gemini.generate_cover_letter(
                job_details,
                resume_path
            )
            
            cover_letter_path = None
            if cover_letter:
                cover_letter_path = JOBS_DIR / f"{job_details['job_id']}_cover_letter.txt"
                with open(cover_letter_path, 'w') as f:
                    f.write(cover_letter)
                self.logger.info(f"Cover letter saved to {cover_letter_path}")
            else:
                self.logger.warning("No cover letter generated")
            
            self.logger.info("Clicking Easy Apply button")
            # Click Easy Apply
            if not self.click_easy_apply():
                self.logger.error("Failed to click Easy Apply button")
                return False
                
            self.random_delay('between_actions')
            
            # Wait for the application container to be visible
            self.logger.info("Waiting for application form")
            application_container = self.wait_for_element_with_retry(
                By.CSS_SELECTOR, 
                ".apply-container",
                timeout=20,
                retries=3
            )
            
            if not application_container:
                self.logger.error("Application form not found")
                return False
                
            # Check if existing resume is already selected or need to upload new one
            self.logger.info("Checking resume status")
            time.sleep(3)  # Give the form time to fully load
            
            # Look for file upload element
            try:
                # First check if we need to upload a resume or if one is already selected
                resume_container = self.wait_for_element_with_retry(
                    By.CSS_SELECTOR,
                    ".resume-container",
                    timeout=5
                )
                
                if resume_container:
                    # Check if there's a file already selected
                    existing_file = resume_container.find_elements(By.CSS_SELECTOR, ".file-wrapper")
                    
                    if existing_file:
                        self.logger.info("Existing resume found, replacing it")
                        # Click replace button
                        replace_button = resume_container.find_element(
                            By.CSS_SELECTOR,
                            ".file-remove"
                        )
                        if not self.click_with_retry(replace_button):
                            self.logger.warning("Could not click replace button, trying to continue")
                    else:
                        self.logger.info("No existing resume found, uploading new one")
                        # Look for direct file input
                        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        if file_inputs:
                            file_inputs[0].send_keys(str(resume_path))
                        else:
                            self.logger.error("No file input found for resume")
                            return False
                else:
                    self.logger.warning("Resume container not found, looking for file input")
                    # Look for direct file input
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_inputs[0].send_keys(str(resume_path))
                    else:
                        self.logger.error("No file input found for resume")
                        return False
            except Exception as e:
                self.logger.error(f"Error handling resume upload: {str(e)}")
                
            # Wait for file picker if it appeared
            time.sleep(3)
            try:
                # Check if file picker modal appeared
                file_picker = self.driver.find_elements(By.CSS_SELECTOR, ".fsp-modal__body")
                if file_picker:
                    self.logger.info("File picker modal appeared, handling it")
                    # Find file input in modal
                    file_input = self.driver.find_element(By.CSS_SELECTOR, "#fsp-fileUpload")
                    file_input.send_keys(str(resume_path))
                    
                    # Wait for file to upload and click next/upload button
                    time.sleep(2)
                    upload_buttons = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        ".fsp-button.fsp-button--primary:not(.fsp-button--disabled)"
                    )
                    if upload_buttons:
                        self.click_with_retry(upload_buttons[0])
                        time.sleep(2)
                    
                    # Look for final upload button if needed
                    final_upload = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        ".fsp-button-upload"
                    )
                    if final_upload:
                        self.click_with_retry(final_upload[0])
                        time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Error handling file picker: {str(e)}")
                
            # Upload cover letter if available
            if cover_letter_path:
                try:
                    self.logger.info("Uploading cover letter")
                    # Look for cover letter button
                    cover_letter_buttons = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        ".file-picker-wrapper.cover-letter button"
                    )
                    
                    if cover_letter_buttons:
                        self.logger.info("Found cover letter upload button")
                        self.click_with_retry(cover_letter_buttons[0])
                        
                        # Wait for file picker to appear
                        time.sleep(2)
                        try:
                            # Check if file picker modal appeared
                            file_picker = self.driver.find_elements(By.CSS_SELECTOR, ".fsp-modal__body")
                            if file_picker:
                                self.logger.info("File picker modal appeared for cover letter")
                                # Find file input in modal
                                file_input = self.driver.find_element(By.CSS_SELECTOR, "#fsp-fileUpload")
                                file_input.send_keys(str(cover_letter_path))
                                
                                # Wait for file to upload and click next/upload button
                                time.sleep(2)
                                upload_buttons = self.driver.find_elements(
                                    By.CSS_SELECTOR, 
                                    ".fsp-button.fsp-button--primary:not(.fsp-button--disabled)"
                                )
                                if upload_buttons:
                                    self.click_with_retry(upload_buttons[0])
                                    time.sleep(2)
                                
                                # Look for final upload button
                                final_upload = self.driver.find_elements(
                                    By.CSS_SELECTOR,
                                    ".fsp-button-upload"
                                )
                                if final_upload:
                                    self.click_with_retry(final_upload[0])
                                    time.sleep(2)
                        except Exception as e:
                            self.logger.warning(f"Error handling cover letter file picker: {str(e)}")
                    else:
                        self.logger.warning("No cover letter upload button found")
                except Exception as e:
                    self.logger.warning(f"Could not upload cover letter: {str(e)}")
            
            # Click through application steps
            self.logger.info("Clicking through application steps")
            
            # Initial next button on first page
            try:
                next_button = self.wait_for_element_with_retry(
                    By.CSS_SELECTOR,
                    ".navigation-buttons .btn-next",
                    timeout=10
                )
                
                if next_button and self.click_with_retry(next_button):
                    self.logger.info("Clicked Next button")
                    self.random_delay('between_actions')
                else:
                    self.logger.warning("Could not find or click Next button")
            except Exception as e:
                self.logger.warning(f"Error clicking Next button: {str(e)}")
                
            # Submit button on review page
            try:
                submit_button = self.wait_for_element_with_retry(
                    By.CSS_SELECTOR,
                    ".navigation-buttons .btn-next",
                    timeout=10
                )
                
                if submit_button and self.click_with_retry(submit_button):
                    self.logger.info("Clicked Submit button")
                    self.random_delay('between_actions')
                else:
                    self.logger.warning("Could not find or click Submit button")
            except Exception as e:
                self.logger.warning(f"Error clicking Submit button: {str(e)}")
            
            # Verify success
            try:
                success = self.wait_for_element_with_retry(
                    By.CSS_SELECTOR,
                    ".post-apply-banner",
                    timeout=15,
                    retries=3
                )
                
                if success:
                    self.logger.info("Application submitted successfully")
                    return True
                else:
                    self.logger.warning("No success banner found")
                    return False
            except Exception as e:
                self.logger.warning(f"Error verifying application success: {str(e)}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error submitting application: {str(e)}")
            return False

    def click_with_retry(self, element, retries=3) -> bool:
        """Click element with retries"""
        for attempt in range(retries + 1):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
                element.click()
                return True
            except Exception:
                try:
                    self.driver.execute_script(
                        "arguments[0].click();",
                        element
                    )
                    return True
                except Exception as e:
                    if attempt < retries:
                        self.logger.warning(f"Retry {attempt + 1} clicking element: {str(e)}")
                        self.random_delay('between_actions')
                    else:
                        self.logger.error(f"Failed to click element after {retries} retries")
                        return False
        return False

    def process_search_results(self):
        """Process all jobs on current page"""
        try:
            # Find all job cards
            job_cards = self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "dhi-search-card[data-cy='search-card']")
                )
            )
            
            self.logger.info(f"Found {len(job_cards)} job cards")
            
            for card in job_cards:
                if not self.is_already_applied(card):
                    # Extract job details and keep window open
                    result = self.extract_job_details(card)
                    if not result:
                        continue
                        
                    job_details, original_window = result
                    
                    # Submit application while on the detail page
                    application_result = self.submit_application(job_details)
                    
                    if application_result:
                        self.logger.info(
                            f"Successfully applied to {job_details['title']}"
                        )
                    else:
                        self.logger.warning(
                            f"Failed to apply to {job_details['title']}"
                        )
                    
                    # Now close the detail window and return to search results
                    self.logger.info("Closing job detail window")
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(original_window)
                        
                    self.random_delay('between_applications')
                else:
                    self.logger.info("Skipping already applied job")
                    
        except Exception as e:
            self.logger.error(f"Error processing search results: {str(e)}")

    def next_page_exists(self) -> bool:
        """Check if next page exists"""
        try:
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                "li.pagination-next:not(.disabled)"
            )
            return bool(next_button)
        except:
            return False

    def go_to_next_page(self) -> bool:
        """Go to next page of results"""
        try:
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                "li.pagination-next:not(.disabled) a"
            )
            if self.click_with_retry(next_button):
                self.random_delay('page_load')
                return True
            return False
        except:
            return False

    def search_jobs(self, title: str) -> bool:
        """Search for jobs with given title"""
        try:
            search_url = DICE_SEARCH_URL.format(quote(title))
            self.driver.get(search_url)
            self.random_delay('page_load')
            
            # Verify search results loaded
            results = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[id='searchDisplay-div']")
                )
            )
            return bool(results)
            
        except Exception as e:
            self.logger.error(f"Error searching jobs: {str(e)}")
            return False

    def run(self):
        """Main execution flow"""
        try:
            if not self.setup_driver():
                return
                
            # Randomize job titles
            random.shuffle(JOB_TITLES)
            
            for title in JOB_TITLES:
                self.logger.info(f"Processing job title: {title}")
                
                if not self.search_jobs(title):
                    continue
                    
                page = 1
                while True:
                    self.logger.info(f"Processing page {page}")
                    self.process_search_results()
                    
                    if not self.next_page_exists():
                        break
                        
                    if not self.go_to_next_page():
                        break
                        
                    page += 1
                    self.random_delay('between_pages')
                    
                self.random_delay('between_actions')
                
        except Exception as e:
            self.logger.error(f"Error in main execution: {str(e)}")
            
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Browser closed")

if __name__ == "__main__":
    bot = DiceBot()
    bot.run()