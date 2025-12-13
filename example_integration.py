"""
Example Integration Script for SmartApplyPro Dashboard

This script demonstrates how to integrate the dashboard logging and status
tracking into your SmartApplyPro bot.
"""

from logger import DashboardLogger
from status_manager import StatusManager
import time
from datetime import datetime

class ExampleBot:
    """
    Example bot showing dashboard integration
    """
    
    def __init__(self):
        # Initialize logger and status manager
        self.logger = DashboardLogger(name='SmartApplyPro')
        self.status = StatusManager()
        
        self.logger.info("=" * 60)
        self.logger.info("SmartApplyPro Bot Initialized")
        self.logger.info("=" * 60)
    
    def start(self):
        """Start the bot"""
        self.logger.info("Starting job application bot...")
        self.status.set_status('running')
        
        try:
            # Main bot loop
            self.run()
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Bot encountered an error: {str(e)}", exc_info=True)
            self.status.add_error(str(e))
            self.status.set_status('error')
        finally:
            self.cleanup()
    
    def run(self):
        """Main bot execution"""
        # Example: Find and apply to jobs
        jobs = self.find_jobs()
        
        self.logger.info(f"Found {len(jobs)} job postings to process")
        
        for i, job in enumerate(jobs, 1):
            self.logger.info(f"Processing job {i}/{len(jobs)}")
            self.process_job(job)
            
            # Simulate processing time
            time.sleep(2)
        
        self.logger.info("All jobs processed successfully")
    
    def find_jobs(self):
        """
        Simulate finding jobs
        Replace this with your actual job finding logic
        """
        self.logger.info("Searching for relevant job postings...")
        
        # Example jobs
        jobs = [
            {
                'id': 'JOB001',
                'company': 'Tech Solutions Inc',
                'position': 'Performance Test Engineer',
                'url': 'https://example.com/jobs/001',
                'location': 'Remote'
            },
            {
                'id': 'JOB002',
                'company': 'Innovation Labs',
                'position': 'Scrum Master',
                'url': 'https://example.com/jobs/002',
                'location': 'New York, NY'
            },
            {
                'id': 'JOB003',
                'company': 'Global Systems',
                'position': 'Load Testing Specialist',
                'url': 'https://example.com/jobs/003',
                'location': 'San Francisco, CA'
            },
            {
                'id': 'JOB004',
                'company': 'Cloud Dynamics',
                'position': 'QA Automation Engineer',
                'url': 'https://example.com/jobs/004',
                'location': 'Remote'
            }
        ]
        
        return jobs
    
    def process_job(self, job):
        """
        Process a single job application
        Replace this with your actual application logic
        """
        job_id = job['id']
        company = job['company']
        position = job['position']
        
        # Update current job in status
        self.status.set_current_job(f"Applying to {position} at {company}")
        self.logger.info(f"Processing: {company} - {position}")
        
        try:
            # Simulate application process
            self.logger.debug(f"Opening job posting: {job['url']}")
            self.logger.debug("Filling out application form...")
            
            # Simulate random success/failure
            import random
            success_chance = random.random()
            
            if success_chance > 0.2:  # 80% success rate
                # Success
                self.logger.info(f"✓ Successfully applied to {company}")
                
                # Track the application
                self.status.track_application(job_id, {
                    'company': company,
                    'position': position,
                    'status': 'success',
                    'job_url': job['url'],
                    'location': job['location'],
                    'applied_date': datetime.now().isoformat()
                })
                
                # Log to applications log
                self.logger.log_application(job, 'success')
                
            else:
                # Failure
                error_msg = "Application form validation failed"
                self.logger.warning(f"✗ Failed to apply to {company}: {error_msg}")
                
                # Track the failed application
                self.status.track_application(job_id, {
                    'company': company,
                    'position': position,
                    'status': 'failed',
                    'error': error_msg,
                    'job_url': job['url'],
                    'location': job['location'],
                    'applied_date': datetime.now().isoformat()
                })
                
                # Log to applications log
                self.logger.log_application(job, 'failed', error=error_msg)
                
                # Add to error list
                self.status.add_error(f"Failed to apply to {company}: {error_msg}")
        
        except Exception as e:
            # Handle unexpected errors
            error_msg = str(e)
            self.logger.error(f"Error processing {company}: {error_msg}")
            
            # Track the failed application
            self.status.track_application(job_id, {
                'company': company,
                'position': position,
                'status': 'failed',
                'error': error_msg,
                'job_url': job['url'],
                'location': job['location'],
                'applied_date': datetime.now().isoformat()
            })
            
            # Log to applications log
            self.logger.log_application(job, 'failed', error=error_msg)
            
            # Add to error list
            self.status.add_error(f"Exception in {company}: {error_msg}")
    
    def cleanup(self):
        """Cleanup and shutdown"""
        self.logger.info("Shutting down bot...")
        
        # Set status to idle
        self.status.set_status('idle')
        self.status.set_current_job(None)
        
        # Get final statistics
        stats = self.status.get_statistics()
        
        self.logger.info("=" * 60)
        self.logger.info("Session Summary:")
        self.logger.info(f"  Total Applications: {stats['total']}")
        self.logger.info(f"  Successful: {stats['successful']}")
        self.logger.info(f"  Failed: {stats['failed']}")
        self.logger.info(f"  Pending: {stats['pending']}")
        self.logger.info("=" * 60)
        
        self.logger.info("Bot shutdown complete")


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("SmartApplyPro Example Bot with Dashboard Integration")
    print("=" * 60)
    print("\nThis example demonstrates:")
    print("  • Logging to dashboard")
    print("  • Status tracking")
    print("  • Application tracking")
    print("  • Error handling")
    print("\nWhile this runs, you can:")
    print("  1. Start the dashboard: python app.py")
    print("  2. Open http://localhost:5000 in your browser")
    print("  3. Watch the logs and statistics update in real-time")
    print("\n" + "=" * 60 + "\n")
    
    # Create and start the bot
    bot = ExampleBot()
    bot.start()


if __name__ == '__main__':
    main()