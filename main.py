import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib
from bot import DiceBot
from resume_handler import ResumeHandler
from gemini_service import GeminiService
from application_tracker import ApplicationTracker
from config import JOBS_DIR, RESUME_DIR, DATA_DIR, DEBUG_MODE

def setup_logging():
    """Configure logging"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO if not DEBUG_MODE else logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / f'smartapplypro_{datetime.now():%Y%m%d_%H%M%S}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers to WARNING to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)

def run_auto_apply():
    """Run automated job application bot with API key monitoring"""
    print("\nStarting SmartApplyPro automated job applications...")
    print("Press Ctrl+C at any time to stop the process.\n")
    
    # Initialize Gemini service to check API keys
    gemini = GeminiService()
    
    # Check if any API keys are available
    if gemini.are_all_keys_exhausted():
        print("\n⚠️ ERROR: All API keys have reached their daily limit!")
        print("Please try again tomorrow or add new API keys to config.py.")
        return
        
    # Show current API usage
    api_stats = gemini.get_api_usage_stats()
    print("\nCurrent API Key Usage:")
    print(f"Date: {api_stats['date']}")
    print(f"Total API calls today: {api_stats['total_usage']}")
    
    for key_id, stats in api_stats['keys'].items():
        status = "CURRENT" if stats['is_current'] else "STANDBY"
        usage_bar = generate_progress_bar(stats['percentage'])
        print(f"{key_id}: {stats['usage']}/{stats['limit']} ({stats['percentage']:.1f}%) {usage_bar} [{status}]")
    
    print("\n")
    
    # Create bot and run
    bot = DiceBot()
    bot.run()
    
def generate_progress_bar(percentage, width=20):
    """Generate a text-based progress bar"""
    filled_width = int(width * percentage / 100)
    empty_width = width - filled_width
    
    if percentage < 50:
        color = "GREEN"
    elif percentage < 85:
        color = "YELLOW"
    else:
        color = "RED"
        
    bar = "█" * filled_width + "░" * empty_width
    return bar

def monitor_api_usage():
    """Display current API key usage statistics"""
    try:
        gemini = GeminiService()
        api_stats = gemini.get_api_usage_stats()
        
        print("\n=======================================")
        print("Gemini API Key Usage Statistics")
        print("=======================================")
        print(f"Date: {api_stats['date']}")
        print(f"Total API calls today: {api_stats['total_usage']}")
        print("")
        
        print("API Key Usage:")
        print("-" * 60)
        print(f"{'API Key':<20} {'Usage':<10} {'Limit':<10} {'Status':<15}")
        print("-" * 60)
        
        for key_id, stats in api_stats['keys'].items():
            status = "ACTIVE" if stats['is_current'] else "STANDBY"
            if stats['usage'] >= stats['limit']:
                status = "EXHAUSTED"
                
            print(f"{key_id:<20} {stats['usage']:<10} {stats['limit']:<10} {status:<15}")
            
            # Progress bar
            percentage = stats['percentage']
            bar_width = 40
            filled_width = int(bar_width * percentage / 100)
            empty_width = bar_width - filled_width
            
            bar = "█" * filled_width + "░" * empty_width
            print(f"[{bar}] {percentage:.1f}%")
            print("")
        
        # Check if all keys are exhausted
        if gemini.are_all_keys_exhausted():
            print("\n⚠️ WARNING: All API keys have reached their daily limit!")
            print("Please try again tomorrow or add new API keys to config.py.")
        
    except Exception as e:
        print(f"\nError monitoring API usage: {str(e)}")

def generate_resume(job_description_file: str) -> Optional[str]:
    """Generate optimized resume from job description file"""
    try:
        # Read job description
        with open(job_description_file, 'r') as f:
            job_details = json.load(f)
            
        # Generate resume
        handler = ResumeHandler()
        resume_path = handler.generate_resume(job_details)
        
        if resume_path:
            print(f"\nResume generated successfully: {resume_path}")
            return resume_path
        else:
            print("\nError generating resume")
            return None
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        return None

def process_job_description(job_description_file: str, job_title: str, 
                           company_name: str, output_type: str) -> None:
    """Process a job description file and generate requested output"""
    try:
        # Set up debug directory
        debug_dir = Path('debug')
        debug_dir.mkdir(exist_ok=True)
        
        # Verify the file exists
        if not os.path.exists(job_description_file):
            print(f"\nError: Job description file not found: {job_description_file}")
            return
        
        # Read job description from file
        try:
            with open(job_description_file, 'r', encoding='utf-8') as f:
                description_text = f.read()
                
            # Save the input for debugging
            with open(debug_dir / "job_description_input.txt", 'w', encoding='utf-8') as f:
                f.write(description_text)
        except Exception as e:
            print(f"\nError reading job description file: {str(e)}")
            return
        
        print(f"\nProcessing job description for {job_title} at {company_name}...")
        
        # Initialize Gemini service
        gemini = GeminiService()
        
        # Convert to JSON using Gemini
        job_json = gemini.convert_job_description_to_json(description_text, job_title, company_name)
        
        if not job_json:
            print("\nError: Failed to convert job description to JSON")
            return
        
        # Create a unique ID for this job
        content = f"{job_json['title']}{job_json['company']}{job_json['description'][:100]}"
        job_id = hashlib.md5(content.encode()).hexdigest()
        job_json['job_id'] = job_id
        
        # Save job details
        job_file = JOBS_DIR / f"{job_id}.json"
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_json, f, indent=2)
        
        print(f"\nJob details extracted and saved to: {job_file}")
        
        # Generate requested output
        if output_type == 'save_json_only':
            print(f"\nJSON file created successfully. You can find it at: {job_file}")
            return
        
        elif output_type == 'generate_resume':
            # Generate resume
            handler = ResumeHandler()
            resume_path = handler.generate_resume(job_json)
            
            if resume_path:
                print(f"\nResume generated successfully: {resume_path}")
            else:
                print("\nError generating resume")
        
        elif output_type == 'generate_cover_letter':
            # First generate a resume (required for cover letter)
            handler = ResumeHandler()
            resume_path = handler.generate_resume(job_json)
            
            if not resume_path:
                print("\nError: Resume generation failed, which is required for cover letter")
                return
            
            # Then generate cover letter
            cover_letter = gemini.generate_cover_letter(job_json, resume_path)
            
            if cover_letter:
                # Create a professional filename for the cover letter
                resume_filename = os.path.basename(resume_path)
                base_name = os.path.splitext(resume_filename)[0]
                cover_letter_base = base_name.replace("Resume", "Cover_Letter")
                cover_letter_path = RESUME_DIR / f"{cover_letter_base}.txt"
                
                # Check for existing file
                counter = 1
                while cover_letter_path.exists():
                    cover_letter_path = RESUME_DIR / f"{cover_letter_base}_v{counter}.txt"
                    counter += 1
                    
                with open(cover_letter_path, 'w') as f:
                    f.write(cover_letter)
                    
                print(f"\nCover letter generated successfully: {cover_letter_path}")
            else:
                print("\nError generating cover letter")
                
        elif output_type == 'generate_both':
            # First generate resume
            handler = ResumeHandler()
            resume_path = handler.generate_resume(job_json)
            
            if not resume_path:
                print("\nError generating resume")
                return
                
            print(f"\nResume generated successfully: {resume_path}")
            
            # Then generate cover letter
            cover_letter = gemini.generate_cover_letter(job_json, resume_path)
            
            if cover_letter:
                # Create a professional filename for the cover letter
                resume_filename = os.path.basename(resume_path)
                base_name = os.path.splitext(resume_filename)[0]
                cover_letter_base = base_name.replace("Resume", "Cover_Letter")
                cover_letter_path = RESUME_DIR / f"{cover_letter_base}.txt"
                
                # Check for existing file
                counter = 1
                while cover_letter_path.exists():
                    cover_letter_path = RESUME_DIR / f"{cover_letter_base}_v{counter}.txt"
                    counter += 1
                    
                with open(cover_letter_path, 'w') as f:
                    f.write(cover_letter)
                    
                print(f"\nCover letter generated successfully: {cover_letter_path}")
            else:
                print("\nError generating cover letter")
        
    except Exception as e:
        print(f"\nError processing job description: {str(e)}")
        import traceback
        traceback.print_exc()

def generate_cover_letter(job_description_file: str, resume_path: str) -> Optional[str]:
    """Generate cover letter from job description and resume"""
    try:
        # Read job description
        with open(job_description_file, 'r') as f:
            job_details = json.load(f)
            
        # Generate cover letter
        gemini = GeminiService()
        cover_letter = gemini.generate_cover_letter(job_details, resume_path)
        
        if cover_letter:
            # Create a professional filename for the cover letter
            resume_filename = os.path.basename(resume_path)
            base_name = os.path.splitext(resume_filename)[0]
            cover_letter_base = base_name.replace("Resume", "Cover_Letter")
            cover_letter_path = RESUME_DIR / f"{cover_letter_base}.txt"
            
            # Check for existing file
            counter = 1
            while cover_letter_path.exists():
                cover_letter_path = RESUME_DIR / f"{cover_letter_base}_v{counter}.txt"
                counter += 1
                
            with open(cover_letter_path, 'w') as f:
                f.write(cover_letter)
                
            print(f"\nCover letter generated successfully: {cover_letter_path}")
            return str(cover_letter_path)
        else:
            print("\nError generating cover letter")
            return None
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        return None

def list_applications():
    """List all tracked job applications"""
    try:
        tracker = ApplicationTracker(DATA_DIR)
        
        # Clean duplicates first
        duplicates = tracker.clean_duplicates()
        if duplicates > 0:
            print(f"\nCleaned {duplicates} duplicate application entries.")
        
        # Get statistics
        stats = tracker.get_application_stats()
        applications = tracker.get_recent_applications(limit=50)
        
        # Print statistics
        print("\n=======================================")
        print("SmartApplyPro Application Statistics")
        print("=======================================")
        print(f"Total jobs found: {stats.get('total_jobs_found', 0)}")
        print(f"Total applications: {stats.get('total_applications', 0)}")
        print(f"Successful applications: {stats.get('successful_applications', 0)}")
        print(f"Failed applications: {stats.get('failed_applications', 0)}")
        print(f"Skipped applications: {stats.get('skipped_applications', 0)}")
        
        # Success rate
        total_apps = stats.get('total_applications', 0)
        success_apps = stats.get('successful_applications', 0)
        if total_apps > 0:
            success_rate = (success_apps / total_apps) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        # Get today's stats
        today = datetime.now().strftime("%Y-%m-%d")
        today_stats = stats.get('daily_stats', {}).get(today, {})
        
        print("\nToday's Activity:")
        print(f"Jobs found: {today_stats.get('jobs_found', 0)}")
        print(f"Applications: {today_stats.get('applications', 0)}")
        print(f"Successful: {today_stats.get('successful', 0)}")
        print(f"Failed: {today_stats.get('failed', 0)}")
        print(f"Skipped: {today_stats.get('skipped', 0)}")
        
        # Print recent applications
        if applications:
            print("\nRecent Applications:")
            print("-" * 100)
            print(f"{'Date':<20} {'Status':<10} {'Title':<30} {'Company':<30}")
            print("-" * 100)
            
            for app in applications:
                applied_date = app.get('applied_date', 'Unknown')
                status = app.get('status', 'Unknown')
                title = app.get('title', 'Unknown')[:30]
                company = app.get('company', 'Unknown')[:30]
                
                print(f"{applied_date:<20} {status:<10} {title:<30} {company:<30}")
            
            print("-" * 100)
        else:
            print("\nNo applications found.")
            
    except Exception as e:
        print(f"\nError listing applications: {str(e)}")

def generate_report():
    """Generate comprehensive application report"""
    try:
        tracker = ApplicationTracker(DATA_DIR)
        report_path = Path('reports') / f'application_report_{datetime.now():%Y%m%d_%H%M%S}.txt'
        
        # Create reports directory if needed
        report_path.parent.mkdir(exist_ok=True)
        
        # Generate the report
        report_text = tracker.generate_report(str(report_path))
        
        print(f"\nReport generated successfully: {report_path}")
        print("\nReport preview:")
        print("-" * 50)
        
        # Print preview (first 20 lines)
        preview_lines = report_text.split('\n')[:20]
        print('\n'.join(preview_lines))
        if len(preview_lines) < len(report_text.split('\n')):
            print("...")
        
        print(f"\nFull report available at: {report_path}")
        
    except Exception as e:
        print(f"\nError generating report: {str(e)}")

def debug_mode():
    """Run system in debug mode with extended diagnostics"""
    try:
        print("\n*** DEBUG MODE ACTIVATED ***")
        print("This mode will provide detailed diagnostics and verbose logging.")
        
        # Create debug directory
        debug_dir = Path('debug')
        debug_dir.mkdir(exist_ok=True)
        
        # Initialize application tracker
        tracker = ApplicationTracker(DATA_DIR)
        
        # Check for applied jobs
        job_count = len(tracker.applied_job_ids)
        print(f"\nFound {job_count} previously applied jobs in tracker.")
        
        # Test Gemini API
        print("\nTesting Gemini API connection...")
        gemini = GeminiService()
        test_result = gemini.test_connection()
        if test_result:
            print("✓ Gemini API connection successful.")
        else:
            print("✗ Gemini API connection failed. Check your API key.")
        
        # Initialize bot for diagnostic checks only
        print("\nInitializing browser for diagnostics...")
        bot = DiceBot()
        if bot.setup_driver():
            print("✓ Browser initialization successful.")
            
            # Test a search query
            print("\nTesting search functionality...")
            if bot.search_jobs("SDET"):
                print("✓ Search functionality working.")
                
                # Analyze page structure
                print("\nAnalyzing Dice.com page structure...")
                bot.analyze_page_structure()
                print("✓ Page structure analysis completed. Check debug directory for details.")
                
                # Clean up
                bot.driver.quit()
            else:
                print("✗ Search functionality failed.")
        else:
            print("✗ Browser initialization failed.")
        
        print("\nDebug diagnostics completed. Check the logs directory for detailed information.")
        
    except Exception as e:
        print(f"\nError in debug mode: {str(e)}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="SmartApplyPro - AI-Powered Job Application Automation System"
    )
    
    parser.add_argument(
        '--mode',
        choices=['auto', 'resume', 'cover', 'list', 'report', 'debug', 'process-description'],
        default='auto',
        help='Operation mode'
    )
    
    parser.add_argument(
        '--job-file',
        help='Job description JSON file for resume/cover letter generation'
    )
    
    parser.add_argument(
        '--resume',
        help='Resume file for cover letter generation'
    )
    
    parser.add_argument(
        '--job-description',
        help='Path to a text file containing a job description to process'
    )
    
    parser.add_argument(
        '--job-title',
        default='Software Engineer',
        help='Job title for the provided description (optional)'
    )
    
    parser.add_argument(
        '--company',
        default='Unknown Company',
        help='Company name for the provided description (optional)'
    )
    
    parser.add_argument(
        '--output-type',
        default='generate_resume',
        choices=['generate_resume', 'generate_cover_letter', 'save_json_only', 'generate_both'],
        help='Output type for process-description mode'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable verbose debug output'
    )
    
    args = parser.parse_args()
    
    # Set up logging with debug if requested
    global DEBUG_MODE
    if args.debug:
        DEBUG_MODE = True
    
    setup_logging()
    
    if args.mode == 'auto':
        run_auto_apply()
        
    elif args.mode == 'resume':
        if not args.job_file:
            print("\nError: Job description file required for resume generation")
            return
        generate_resume(args.job_file)
        
    elif args.mode == 'cover':
        if not args.job_file or not args.resume:
            print("\nError: Job file and resume required for cover letter generation")
            return
        generate_cover_letter(args.job_file, args.resume)
        
    elif args.mode == 'list':
        list_applications()
        
    elif args.mode == 'report':
        generate_report()
        
    elif args.mode == 'debug':
        debug_mode()
        
    elif args.mode == 'process-description':
        if not args.job_description:
            print("\nError: Job description file required for processing")
            print("Example usage: python main.py --mode process-description --job-description job_desc.txt")
            return
            
        # Ensure output directories exist
        os.makedirs(JOBS_DIR, exist_ok=True)
        os.makedirs(RESUME_DIR, exist_ok=True)
        os.makedirs(Path('debug'), exist_ok=True)
            
        try:
            process_job_description(args.job_description, args.job_title, args.company, args.output_type)
        except Exception as e:
            print(f"\nError in process-description mode: {str(e)}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()