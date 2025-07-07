import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

class ApplicationTracker:
    """Enhanced tracker for job applications with improved duplicate detection"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.tracking_file = base_dir / 'tracking' / 'applications.csv'
        self.stats_file = base_dir / 'tracking' / 'statistics.json'
        self.job_ids_file = base_dir / 'tracking' / 'job_ids.json'
        
        # Create tracking directory
        tracking_dir = base_dir / 'tracking'
        tracking_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize tracking file
        if not self.tracking_file.exists():
            with open(self.tracking_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'job_id', 
                    'title', 
                    'company', 
                    'location',
                    'applied_date', 
                    'resume_file', 
                    'cover_letter_file',
                    'status',
                    'notes'
                ])
        
        # Initialize stats file
        if not self.stats_file.exists():
            stats = {
                'total_jobs_found': 0,
                'total_applications': 0,
                'successful_applications': 0,
                'failed_applications': 0,
                'skipped_applications': 0,
                'daily_stats': {},
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
                
        # Initialize or load job IDs cache
        self.applied_job_ids = set()
        if self.job_ids_file.exists():
            try:
                with open(self.job_ids_file, 'r') as f:
                    self.applied_job_ids = set(json.load(f))
            except Exception as e:
                print(f"Error loading job IDs cache: {str(e)}")
        
        # If cache doesn't exist, build it from tracking file
        if not self.applied_job_ids and self.tracking_file.exists():
            self._rebuild_job_ids_cache()
    
    def _rebuild_job_ids_cache(self):
        """Rebuild the job IDs cache from the tracking file"""
        try:
            with open(self.tracking_file, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                self.applied_job_ids = set()
                for row in reader:
                    if row and row[0]:  # job_id is in first column
                        self.applied_job_ids.add(row[0])
            
            # Save the rebuilt cache
            with open(self.job_ids_file, 'w') as f:
                json.dump(list(self.applied_job_ids), f)
                
            print(f"Rebuilt job IDs cache with {len(self.applied_job_ids)} entries")
        except Exception as e:
            print(f"Error rebuilding job IDs cache: {str(e)}")
    
    def add_application(self, job_details: Dict, status: str, resume_file: Optional[str] = None, 
                        cover_letter_file: Optional[str] = None, notes: str = '') -> None:
        """Add a new application to the tracking file with enhanced caching"""
        job_id = job_details.get('job_id', '')
        
        # Add to tracking file
        with open(self.tracking_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                job_id,
                job_details.get('title', ''),
                job_details.get('company', ''),
                job_details.get('location', ''),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                os.path.basename(resume_file) if resume_file else '',
                os.path.basename(cover_letter_file) if cover_letter_file else '',
                status,
                notes
            ])
        
        # Update job IDs cache
        if job_id:
            self.applied_job_ids.add(job_id)
            try:
                with open(self.job_ids_file, 'w') as f:
                    json.dump(list(self.applied_job_ids), f)
            except Exception as e:
                print(f"Error updating job IDs cache: {str(e)}")
        
        # Update statistics
        self._update_statistics(status)
    
    def is_job_applied(self, job_id: str) -> bool:
        """Check if a job has already been applied to using optimized cache"""
        if not job_id:
            return False
            
        # First check the cached set for performance
        if job_id in self.applied_job_ids:
            return True
            
        # Fall back to CSV check if needed
        if self.tracking_file.exists():
            with open(self.tracking_file, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if row and row[0] == job_id:
                        # Update cache for future checks
                        self.applied_job_ids.add(job_id)
                        try:
                            with open(self.job_ids_file, 'w') as f:
                                json.dump(list(self.applied_job_ids), f)
                        except:
                            pass
                        return True
                        
        return False
    
    def get_application_stats(self) -> Dict:
        """Get application statistics"""
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                return json.load(f)
        return {}
    
    def get_recent_applications(self, limit: int = 10) -> List[Dict]:
        """Get the most recent applications"""
        applications = []
        if not self.tracking_file.exists():
            return applications
            
        with open(self.tracking_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                applications.append(dict(row))
                if len(applications) >= limit:
                    break
        
        return applications
    
    def get_daily_stats(self, date: Optional[str] = None) -> Dict:
        """Get stats for a specific day (YYYY-MM-DD format)"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
            
        stats = self.get_application_stats()
        daily_stats = stats.get('daily_stats', {})
        
        return daily_stats.get(date, {
            'jobs_found': 0,
            'applications': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        })
    
    def _update_statistics(self, status: str) -> None:
        """Update the statistics file with new application data"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                stats = json.load(f)
        else:
            stats = {
                'total_jobs_found': 0,
                'total_applications': 0,
                'successful_applications': 0,
                'failed_applications': 0,
                'skipped_applications': 0,
                'daily_stats': {},
                'last_updated': ''
            }
        
        # Update total counts
        stats['total_applications'] += 1
        
        if status == 'success':
            stats['successful_applications'] += 1
        elif status == 'failed':
            stats['failed_applications'] += 1
        elif status == 'skipped':
            stats['skipped_applications'] += 1
        
        # Update daily stats
        if today not in stats['daily_stats']:
            stats['daily_stats'][today] = {
                'jobs_found': 0,
                'applications': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
        
        stats['daily_stats'][today]['applications'] += 1
        
        if status == 'success':
            stats['daily_stats'][today]['successful'] += 1
        elif status == 'failed':
            stats['daily_stats'][today]['failed'] += 1
        elif status == 'skipped':
            stats['daily_stats'][today]['skipped'] += 1
        
        stats['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(self.stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
    
    def increment_jobs_found(self) -> None:
        """Increment the count of jobs found"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                stats = json.load(f)
        else:
            stats = {
                'total_jobs_found': 0,
                'total_applications': 0,
                'successful_applications': 0,
                'failed_applications': 0,
                'skipped_applications': 0,
                'daily_stats': {},
                'last_updated': ''
            }
        
        # Update total jobs found
        stats['total_jobs_found'] += 1
        
        # Update daily stats
        if today not in stats['daily_stats']:
            stats['daily_stats'][today] = {
                'jobs_found': 0,
                'applications': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
        
        stats['daily_stats'][today]['jobs_found'] += 1
        stats['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(self.stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
    
    def generate_report(self, output_path: Optional[str] = None) -> str:
        """Generate a detailed report of application activities"""
        stats = self.get_application_stats()
        today_stats = self.get_daily_stats()
        
        # Calculate job titles applied to
        job_titles = {}
        companies = {}
        
        with open(self.tracking_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', 'Unknown')
                company = row.get('company', 'Unknown')
                status = row.get('status', '')
                
                if title not in job_titles:
                    job_titles[title] = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}
                
                job_titles[title]['total'] += 1
                if status == 'success':
                    job_titles[title]['success'] += 1
                elif status == 'failed':
                    job_titles[title]['failed'] += 1
                elif status == 'skipped':
                    job_titles[title]['skipped'] += 1
                    
                if company not in companies:
                    companies[company] = 0
                companies[company] += 1
        
        # Sort titles by total applications
        sorted_titles = sorted(job_titles.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Sort companies by number of applications
        sorted_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)
        
        # Generate report
        report = []
        report.append("=======================================")
        report.append("SmartApplyPro Application Activity Report")
        report.append("=======================================")
        report.append("")
        report.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append("Overall Statistics:")
        report.append(f"- Total jobs found: {stats.get('total_jobs_found', 0)}")
        report.append(f"- Total applications: {stats.get('total_applications', 0)}")
        report.append(f"- Successful applications: {stats.get('successful_applications', 0)}")
        report.append(f"- Failed applications: {stats.get('failed_applications', 0)}")
        report.append(f"- Skipped applications: {stats.get('skipped_applications', 0)}")
        report.append(f"- Success rate: {(stats.get('successful_applications', 0) / max(1, stats.get('total_applications', 0))) * 100:.1f}%")
        report.append("")
        report.append("Today's Activity:")
        report.append(f"- Jobs found: {today_stats.get('jobs_found', 0)}")
        report.append(f"- Applications: {today_stats.get('applications', 0)}")
        report.append(f"- Successful: {today_stats.get('successful', 0)}")
        report.append(f"- Failed: {today_stats.get('failed', 0)}")
        report.append(f"- Skipped: {today_stats.get('skipped', 0)}")
        report.append("")
        
        # Weekly activity
        weekly_stats = self._get_weekly_stats()
        report.append("Weekly Activity:")
        report.append(f"- Jobs found: {weekly_stats.get('jobs_found', 0)}")
        report.append(f"- Applications: {weekly_stats.get('applications', 0)}")
        report.append(f"- Successful: {weekly_stats.get('successful', 0)}")
        report.append(f"- Failed: {weekly_stats.get('failed', 0)}")
        report.append(f"- Skipped: {weekly_stats.get('skipped', 0)}")
        report.append("")
        
        # Top job titles
        report.append("Top Job Titles Applied To:")
        for i, (title, counts) in enumerate(sorted_titles[:10], 1):
            report.append(f"{i}. {title}: {counts['total']} applications ({counts['success']} successful)")
        report.append("")
        
        # Top companies
        report.append("Top Companies Applied To:")
        for i, (company, count) in enumerate(sorted_companies[:10], 1):
            report.append(f"{i}. {company}: {count} applications")
        report.append("")
        
        # Recent applications
        recent = self.get_recent_applications(10)
        if recent:
            report.append("Recent Applications:")
            for app in recent:
                report.append(f"- {app.get('applied_date', '')}: {app.get('title', '')} at {app.get('company', '')} - {app.get('status', '')}")
        
        report_text = "\n".join(report)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_text)
        
        return report_text
        
    def _get_weekly_stats(self) -> Dict:
        """Calculate statistics for the past 7 days"""
        stats = self.get_application_stats()
        daily_stats = stats.get('daily_stats', {})
        
        weekly_stats = {
            'jobs_found': 0,
            'applications': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Get dates for the past 7 days
        today = datetime.now().date()
        past_dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        
        # Sum up stats for these dates
        for date in past_dates:
            if date in daily_stats:
                day_stats = daily_stats[date]
                weekly_stats['jobs_found'] += day_stats.get('jobs_found', 0)
                weekly_stats['applications'] += day_stats.get('applications', 0)
                weekly_stats['successful'] += day_stats.get('successful', 0)
                weekly_stats['failed'] += day_stats.get('failed', 0)
                weekly_stats['skipped'] += day_stats.get('skipped', 0)
        
        return weekly_stats
        
    def clean_duplicates(self) -> int:
        """Clean duplicate entries from tracking file"""
        if not self.tracking_file.exists():
            return 0
            
        # Read all entries
        entries = []
        seen_job_ids = set()
        duplicates = 0
        
        with open(self.tracking_file, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            for row in reader:
                if not row or not row[0]:  # Skip empty rows
                    continue
                    
                job_id = row[0]
                if job_id in seen_job_ids:
                    duplicates += 1
                    continue
                    
                seen_job_ids.add(job_id)
                entries.append(row)
        
        # Write back without duplicates
        if duplicates > 0:
            with open(self.tracking_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(entries)
            
            # Update job IDs cache
            self.applied_job_ids = seen_job_ids
            with open(self.job_ids_file, 'w') as f:
                json.dump(list(self.applied_job_ids), f)
        
        return duplicates