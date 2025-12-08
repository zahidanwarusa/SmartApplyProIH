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

# Inam Haq's resume template
DEFAULT_RESUME = RESUME_DIR / 'inam-haq-resume.json'
if not DEFAULT_RESUME.exists():
    raise FileNotFoundError(f"Resume template not found: {DEFAULT_RESUME}")

# API Keys - Support for multiple keys with rotation (same as main config)
GEMINI_API_KEYS = [
    'AIzaSyB3g63kzoe9oKt6JxH8luvit3xS_GGIpBE',  # Primary key
    'AIzaSyA3-UQ3YWkv4xuG7yC3y0eyBwRR8edCX2I',  # Secondary key
]

# API limits and settings
API_DAILY_LIMIT = 1500
API_WARNING_THRESHOLD = 0.85

# Chrome Settings for Inam Haq's Account
CHROME_PROFILE = {
    'user_data_dir': 'C:\\Users\\niqht\\AppData\\Local\\Google\\Chrome\\User Data',
    'profile_directory': 'Profile 3'  # Inam's dedicated profile
}

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
    'status_check': (5, 10)
}

MAX_RETRIES = {
    'click': 3,
    'form': 2,
    'page_load': 2,
    'status_check': 3
}

# Job Search Settings - Customized for Inam's Performance Testing & QA Leadership Background
JOB_TITLES = [
    "Performance Test Engineer",
    "Performance Tester",
    "Load Test Engineer",
    "Scrum Master",
    "QA Lead",
    "QA Manager",
    "Test Automation Engineer",
    "Automation Test Lead",
    "SDET",
    "Senior SDET",
    "Test Lead",
    "Quality Assurance Lead",
    "Automation Engineer"
]

# Search URL template
DICE_SEARCH_URL = "https://www.dice.com/jobs?q={}&countryCode=US&radius=30&radiusUnit=mi&pageSize=20&filters.workplaceTypes=Remote&filters.easyApply=true&language=en"

# Search settings
MAX_PAGES_PER_SEARCH = 3
MAX_APPLICATIONS_PER_SESSION = 50
JOBS_PER_PAGE = 20

# Application tracking file (separate for Inam)
TRACKING_DIR = DATA_DIR / 'tracking_inam'
TRACKING_DIR.mkdir(exist_ok=True)
APPLICATION_TRACKING_FILE = TRACKING_DIR / 'applications.json'

# Reports directory (separate for Inam)
REPORTS_DIR = BASE_DIR / 'reports_inam'
REPORTS_DIR.mkdir(exist_ok=True)

# Logs directory (separate for Inam)
LOGS_DIR = BASE_DIR / 'logs_inam'
LOGS_DIR.mkdir(exist_ok=True)

# User identifier for tracking
USER_ID = 'inam_haq'
USER_EMAIL = 'ihaq5565@gmail.com'
