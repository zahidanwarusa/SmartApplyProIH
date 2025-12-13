#!/usr/bin/env python3
"""
Quick Start Script for SmartApplyPro Dashboard

This script helps you quickly set up and start the dashboard.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   You are using Python {sys.version_info.major}.{sys.version_info.minor}")
        return False
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ['flask', 'flask_cors']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def create_directories():
    """Create necessary directories"""
    dirs = ['logs', 'data', 'templates', 'static/css', 'static/js']
    
    print("\n📁 Creating directories...")
    for dir_name in dirs:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
    print("✅ Directories created")

def check_files():
    """Check if all required files exist"""
    required_files = [
        'app.py',
        'logger.py',
        'status_manager.py',
        'templates/base.html',
        'templates/dashboard.html',
        'templates/logs.html',
        'templates/applications.html',
        'static/css/style.css',
        'static/js/dashboard.js'
    ]
    
    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(file)
    
    return missing

def start_dashboard():
    """Start the Flask dashboard"""
    print("\n🚀 Starting SmartApplyPro Dashboard...")
    print("=" * 60)
    print("Dashboard will be available at: http://localhost:5000")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the dashboard\n")
    
    try:
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped")

def run_example():
    """Run the example integration"""
    print("\n🤖 Running example bot...")
    print("=" * 60)
    print("This will demonstrate the dashboard integration")
    print("Start the dashboard in another terminal to see it in action")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")
    
    try:
        subprocess.run([sys.executable, 'example_integration.py'])
    except KeyboardInterrupt:
        print("\n\n👋 Example stopped")

def main():
    """Main function"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║        SmartApplyPro Dashboard - Quick Start              ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    print("✅ Python version is compatible\n")
    
    # Create directories
    create_directories()
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing_deps)}")
        response = input("Would you like to install them now? (y/n): ")
        if response.lower() == 'y':
            if not install_dependencies():
                sys.exit(1)
        else:
            print("❌ Cannot continue without dependencies")
            sys.exit(1)
    else:
        print("✅ All dependencies are installed")
    
    # Check files
    missing_files = check_files()
    if missing_files:
        print("\n⚠️  Warning: Some files are missing:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n   The dashboard may not work correctly.")
    
    # Menu
    while True:
        print("\n" + "=" * 60)
        print("What would you like to do?")
        print("=" * 60)
        print("1. Start the dashboard")
        print("2. Run example bot (demonstrates integration)")
        print("3. Show setup instructions")
        print("4. Exit")
        print("=" * 60)
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            start_dashboard()
        elif choice == '2':
            run_example()
        elif choice == '3':
            show_instructions()
        elif choice == '4':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")

def show_instructions():
    """Show setup instructions"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                   Setup Instructions                      ║
╚═══════════════════════════════════════════════════════════╝

1️⃣  INTEGRATE WITH YOUR BOT
   Add these imports to your bot code:
   
   from logger import DashboardLogger
   from status_manager import StatusManager

2️⃣  INITIALIZE IN YOUR BOT
   
   logger = DashboardLogger()
   status = StatusManager()

3️⃣  LOG MESSAGES
   
   logger.info("Bot started")
   logger.error("Error occurred")
   logger.log_application(job_data, 'success')

4️⃣  UPDATE STATUS
   
   status.set_status('running')
   status.track_application(job_id, job_data)
   status.set_current_job("Applying to Google")

5️⃣  START THE DASHBOARD
   
   python app.py
   
   Then open: http://localhost:5000

6️⃣  RUN YOUR BOT
   
   Your bot will now log to the dashboard!

📖 For more details, see README.md
    """)
    input("\nPress Enter to continue...")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Exited by user")
        sys.exit(0)