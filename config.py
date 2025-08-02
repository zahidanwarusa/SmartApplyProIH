import os
from pathlib import Path

# File paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RESUME_DIR = DATA_DIR / 'resumes'
JOBS_DIR = DATA_DIR / 'jobs'
TEMP_DIR = DATA_DIR / 'temp'

# Create directories if they don't exist
for directory in [DATA_DIR, RESUME_DIR, JOBS_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Default resume template
DEFAULT_RESUME = BASE_DIR / 'zahid_resume_v2.json'
if not DEFAULT_RESUME.exists():
    raise FileNotFoundError(f"Default resume template not found: {DEFAULT_RESUME}")

# API Keys - Support for multiple keys with rotation
# The system will use these keys in order and rotate when limits are reached
GEMINI_API_KEYS = [  # Primary key
    'AIzaSyB3g63kzoe9oKt6JxH8luvit3xS_GGIpBE',
    'AIzaSyA3-UQ3YWkv4xuG7yC3y0eyBwRR8edCX2I',
      
      # Secondary key
    # Add more keys as needed
]

BLACKLISTED_COMPANIES = [
    "ExampleCompany"  # Will match any company with this substring
]


# API limits and settings
API_DAILY_LIMIT = 800  # Maximum requests per day per key
API_WARNING_THRESHOLD = 0.85  # Warn when usage reaches 85% of limit

# Chrome Settings
CHROME_PROFILE = {
    'user_data_dir': 'C:\\Users\\ABC\\AppData\\Local\\Google\\Chrome\\User Data',
    'profile_directory': 'Profile 2'
}

DICE_LOGIN = {
    'email': 'zahidsdet@gmail.com',
    'password': 'Woodbridge@2023'
}

HEADLESS_MODE = True
# ChromeDriver path
CHROMEDRIVER_PATH = "webdriver\\chromedriver.exe"

# Chrome startup arguments
CHROME_ARGUMENTS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-blink-features=AutomationControlled'
]

# Application Settings
DELAYS = {
    'page_load': (4, 8),
    'between_actions': (2, 5),
    'between_applications': (8, 15),
    'between_pages': (5, 10),
    'status_check': (5, 10)  # New delay for status checks (Easy Apply, Already Applied)
}

MAX_RETRIES = {
    'click': 3,
    'form': 2,
    'page_load': 2,
    'status_check': 3  # New retry setting for status checks
}

# Job Search Settings
JOB_TITLES = [
  "SDET",
  "QA Automation",
  "Test Automation",
  "Senior SDET",
  "Lead SDET",
  "Quality Assurance Engineer",
  "QA Engineer", 
  "Test Engineer",
  "Software Test Engineer",
]
# Search URL template
DICE_SEARCH_URL = "https://www.dice.com/jobs?q={}&countryCode=US&pageSize=20&filters.workplaceTypes=Remote&filters.easyApply=true&language=en"

# Application Limits
MAX_APPLICATIONS_PER_DAY = 2
MAX_PAGES_PER_TITLE = 50  # How many pages to process before moving to next title

# Debug Mode - Set to True for additional debugging information
DEBUG_MODE = False

# Application Features
RANDOMIZE_TITLES = True  # Process job titles in random order
CYCLE_THROUGH_TITLES = True  # Cycle through all titles rather than exhausting one
VERIFY_APPLIED_JOBS = True  # Double-check if a job was already applied to


# ZipRecruiter Settings
ZIPRECRUITER_EMAIL = "zahidsdet@gmail.com"
ZIPRECRUITER_LOGIN_URL = "https://www.ziprecruiter.com/authn/login"
ZIPRECRUITER_SEARCH_URL = "https://www.ziprecruiter.com/jobs-search?search={}&location=Remote+%28USA%29&refine_by_location_type=&radius=5000&days=&page={}"

# ZipRecruiter Job Search Settings
ZIPRECRUITER_JOB_TITLES = [
    "SDET",
    "Software Development Engineer in Test",
    "QA Automation Engineer",
    "Test Automation Engineer",
    "Senior SDET",
    "Lead SDET",
    "Quality Assurance Automation",
    "Software Test Engineer",
    "Automation Test Engineer",
    "Senior QA Engineer"
]

# Gmail API Settings for verification codes
GMAIL_CREDENTIALS_FILE = "credentials/gmail_credentials.json"
GMAIL_TOKEN_FILE = "credentials/gmail_token.json"

# ZipRecruiter Delays (more conservative than Dice)
ZIPRECRUITER_DELAYS = {
    'page_load': (5, 10),
    'between_actions': (3, 6),
    'between_applications': (10, 20),
    'between_pages': (8, 15),
    'email_check': (10, 15),  # Time between email checks
    'verification_wait': (5, 10)  # Wait after entering verification code
}

# ZipRecruiter Limits
ZIPRECRUITER_MAX_APPLICATIONS_PER_DAY = 20
ZIPRECRUITER_MAX_PAGES_PER_TITLE = 5
ZIPRECRUITER_EMAIL_TIMEOUT = 300  # 5 minutes to wait for verification email

# ZipRecruiter Selectors (will be updated as we discover them)
ZIPRECRUITER_SELECTORS = {
    'email_input': 'input[type="email"]',
    'continue_button': 'button[type="submit"]',
    'otp_inputs': 'textarea[id^="otp-"]',
    'verify_button': 'button[type="submit"]',
    'job_cards': '[data-testid="job-card"]',
    'easy_apply_button': '[data-testid="easy-apply-button"]',
    'already_applied': '.already-applied',
    'next_page': '.pagination-next'
}

# Combined settings for main.py
SUPPORTED_PLATFORMS = ['dice', 'ziprecruiter']
DEFAULT_PLATFORM = 'dice'