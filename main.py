import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from bot import DiceBot
from resume_handler import ResumeHandler
from gemini_service import GeminiService
from config import JOBS_DIR, RESUME_DIR

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def run_auto_apply():
    """Run automated job application bot"""
    bot = DiceBot()
    bot.run()

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
            # Save cover letter
            cover_letter_path = Path(job_description_file).parent / "cover_letter.txt"
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
        applications = []
        
        # Get all job files
        for job_file in JOBS_DIR.glob("*.json"):
            with open(job_file, 'r') as f:
                job_data = json.load(f)
                
            # Check for resume and cover letter
            resume_path = RESUME_DIR / f"{job_data['job_id']}_resume.docx"
            cover_letter_path = JOBS_DIR / f"{job_data['job_id']}_cover_letter.txt"
            
            applications.append({
                'title': job_data['title'],
                'company': job_data['company'],
                'applied_date': job_data.get('applied_date', 'Unknown'),
                'has_resume': resume_path.exists(),
                'has_cover_letter': cover_letter_path.exists()
            })
            
        # Print applications
        print("\nJob Applications:")
        print("-" * 80)
        for app in applications:
            print(f"\nTitle: {app['title']}")
            print(f"Company: {app['company']}")
            print(f"Applied: {app['applied_date']}")
            print(f"Resume: {'Yes' if app['has_resume'] else 'No'}")
            print(f"Cover Letter: {'Yes' if app['has_cover_letter'] else 'No'}")
            print("-" * 80)
            
    except Exception as e:
        print(f"\nError listing applications: {str(e)}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Job Application Automation System"
    )
    
    parser.add_argument(
        '--mode',
        choices=['auto', 'resume', 'cover', 'list'],
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
    
    args = parser.parse_args()
    
    setup_logging()
    
    if args.mode == 'auto':
        print("\nStarting automated job applications...")
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

if __name__ == "__main__":
    main()