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
DEFAULT_RESUME = BASE_DIR / 'default-resume-main.json'
if not DEFAULT_RESUME.exists():
    raise FileNotFoundError(f"Default resume template not found: {DEFAULT_RESUME}")

# API Keys - Support for multiple keys with rotation
# The system will use these keys in order and rotate when limits are reached
GEMINI_API_KEYS = [
    'AIzaSyB3g63kzoe9oKt6JxH8luvit3xS_GGIpBE',  # Primary key
    'AIzaSyA3-UQ3YWkv4xuG7yC3y0eyBwRR8edCX2I',  # Secondary key
    # Add more keys as needed
]

# API limits and settings
API_DAILY_LIMIT = 1500  # Maximum requests per day per key
API_WARNING_THRESHOLD = 0.85  # Warn when usage reaches 85% of limit

# Chrome Settings
CHROME_PROFILE = {
    'user_data_dir': 'C:\\Users\\ABC\\AppData\\Local\\Google\\Chrome\\User Data',
    'profile_directory': 'Profile 1'
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
  "Software Development Engineer in Test",
  "Automation Engineer",
  "QA Automation Engineer",
  "Test Automation Engineer",
  "Senior SDET",
  "Lead SDET",
  "Healthcare SDET",
  "Medical Device SDET",
  "Clinical Systems SDET",
  "Healthcare Test Engineer",
  "Medical Device Test Engineer",
  "Clinical Systems Test Engineer",
  "Healthcare Software Test Engineer",
  "Medical Software Test Engineer",
  "Healthcare Quality Engineer",
  "Medical Device Quality Engineer",
  "SDET (Test Automation)",
  "Software Test Automation Engineer",
  "Quality Automation Engineer",
  "Test Engineer (Automation)",
  "Senior Test Automation Engineer",
  "Lead Test Automation Engineer",
  "SDET II",
  "SDET III",
  "Automation Test Lead",
  "Quality Engineer (Automation)",
  "Software Test Engineer (Automation)",
  "Test Automation Developer",
  "Senior Quality Automation Engineer",
  "Lead Quality Automation Engineer",
  "Test Automation Specialist",
  "Senior Test Automation Specialist",
  "Automation Architect",
  "Test Automation Architect",
  "HL7 Testing Engineer",
  "FHIR Testing Engineer",
  "EHR Testing Engineer",
  "Cloud SDET",
  "Cloud Test Engineer",
  "Security SDET",
  "Security Test Engineer",
  "Performance Test Engineer",
  "Mobile Test Automation Engineer",
  "API Test Automation Engineer",
  "DevOps Test Engineer",
  "AI Test Engineer",
  "Machine Learning Test Engineer",
  "Data Quality Engineer",
  "Accessibility Test Engineer",
  "Embedded Systems Test Engineer",
  "Digital Health Test Engineer",
  "Usability Test Engineer",
  "Integration Test Engineer",
  "Regression Test Engineer",
  "System Test Engineer",
  "Acceptance Test Engineer",
  "Exploratory Test Engineer",
  "Test Manager",
  "Quality Assurance Manager",
  "Test Lead",
  "Quality Lead",
  "Software Tester",
  "Manual Tester",
  "Test Analyst",
  "Quality Analyst"
]

# Search URL template
DICE_SEARCH_URL = "https://www.dice.com/jobs?q={}&countryCode=US&radius=30&radiusUnit=mi&pageSize=20&filters.workplaceTypes=Remote&filters.easyApply=true&language=en"

# Application Limits
MAX_APPLICATIONS_PER_DAY = 2
MAX_PAGES_PER_TITLE = 3  # How many pages to process before moving to next title

# Debug Mode - Set to True for additional debugging information
DEBUG_MODE = False

# Application Features
RANDOMIZE_TITLES = True  # Process job titles in random order
CYCLE_THROUGH_TITLES = True  # Cycle through all titles rather than exhausting one
VERIFY_APPLIED_JOBS = True  # Double-check if a job was already applied to