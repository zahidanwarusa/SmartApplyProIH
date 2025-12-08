#!/usr/bin/env python3
"""
SmartApplyPro Web Interface Setup Script
This script helps initialize the web interface and verify dependencies
"""

import sys
import os
from pathlib import Path
import subprocess

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_success(text):
    """Print success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print error message"""
    print(f"✗ {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ {text}")

def check_python_version():
    """Check if Python version is 3.9 or higher"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
        return True
    else:
        print_error(f"Python 3.9+ required, but {version.major}.{version.minor}.{version.micro} detected")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    print_header("Checking Dependencies")
    
    required_packages = [
        'flask',
        'werkzeug',
        'PyPDF2',
        'docx',
        'google.generativeai'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is NOT installed")
            missing_packages.append(package)
    
    return len(missing_packages) == 0, missing_packages

def install_dependencies():
    """Install required dependencies"""
    print_header("Installing Dependencies")
    
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print_success("All dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies")
        return False

def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    directories = [
        'uploads',
        'data/resumes',
        'templates',
        'static/css',
        'static/js'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created directory: {directory}")
        else:
            print_info(f"Directory already exists: {directory}")
    
    return True

def check_backend_files():
    """Check if required backend files exist"""
    print_header("Checking Backend Files")
    
    required_files = [
        'resume_handler.py',
        'gemini_service.py',
        'config.py',
        'data/resumes/default-resume-main.json'
    ]
    
    all_exist = True
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print_success(f"Found: {file_path}")
        else:
            print_error(f"Missing: {file_path}")
            all_exist = False
    
    return all_exist

def check_web_interface_files():
    """Check if web interface files exist"""
    print_header("Checking Web Interface Files")
    
    required_files = [
        'app.py',
        'templates/index.html',
        'static/css/style.css',
        'static/js/main.js'
    ]
    
    all_exist = True
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print_success(f"Found: {file_path}")
        else:
            print_error(f"Missing: {file_path}")
            all_exist = False
    
    return all_exist

def check_config():
    """Check if config.py has necessary settings"""
    print_header("Checking Configuration")
    
    try:
        import config
        
        # Check for Gemini API key
        if hasattr(config, 'GEMINI_API_KEY') and config.GEMINI_API_KEY:
            if config.GEMINI_API_KEY == 'your-api-key-here':
                print_error("GEMINI_API_KEY is not set in config.py")
                print_info("Please update config.py with your actual Gemini API key")
                return False
            else:
                print_success("GEMINI_API_KEY is configured")
        else:
            print_error("GEMINI_API_KEY not found in config.py")
            return False
        
        # Check for default resume path
        if hasattr(config, 'DEFAULT_RESUME'):
            print_success("DEFAULT_RESUME path is configured")
        else:
            print_error("DEFAULT_RESUME not found in config.py")
            return False
        
        return True
        
    except ImportError:
        print_error("config.py not found or cannot be imported")
        return False

def main():
    """Main setup process"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         SmartApplyPro Web Interface Setup                 ║")
    print("║         AI-Powered Career Accelerator                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    # Track overall success
    setup_successful = True
    
    # Step 1: Check Python version
    if not check_python_version():
        setup_successful = False
        print_info("Please upgrade to Python 3.9 or higher")
        return
    
    # Step 2: Check dependencies
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        print_info(f"\nMissing packages: {', '.join(missing)}")
        print_info("Attempting to install dependencies...")
        
        if not install_dependencies():
            setup_successful = False
            print_error("Failed to install dependencies. Please install manually:")
            print_info("pip install -r requirements.txt")
            return
    
    # Step 3: Create directories
    if not create_directories():
        setup_successful = False
    
    # Step 4: Check backend files
    if not check_backend_files():
        setup_successful = False
        print_info("\nBackend files are required for the web interface to work.")
        print_info("Please ensure SmartApplyPro backend is properly set up.")
    
    # Step 5: Check web interface files
    if not check_web_interface_files():
        setup_successful = False
        print_info("\nWeb interface files are missing.")
        print_info("Please ensure all template and static files are present.")
    
    # Step 6: Check configuration
    if not check_config():
        setup_successful = False
        print_info("\nConfiguration issues detected.")
        print_info("Please update config.py with your settings.")
    
    # Final summary
    print_header("Setup Summary")
    
    if setup_successful:
        print_success("Setup completed successfully!")
        print("\n" + "─" * 60)
        print("Next Steps:")
        print("─" * 60)
        print("1. Ensure your Gemini API key is set in config.py")
        print("2. Verify default-resume-main.json exists and is properly formatted")
        print("3. Run the application:")
        print("   python app.py")
        print("4. Open your browser to:")
        print("   http://localhost:5000")
        print("─" * 60 + "\n")
    else:
        print_error("Setup completed with issues")
        print_info("Please resolve the issues above before running the application")
    
    return setup_successful

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
