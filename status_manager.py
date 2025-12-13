import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

class StatusManager:
    """
    Manages bot status for dashboard integration
    """
    
    def __init__(self, data_dir='data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.status_file = self.data_dir / 'bot_status.json'
        self.tracking_file = self.data_dir / 'applications_tracking.json'
        
        # Initialize status file if it doesn't exist
        if not self.status_file.exists():
            self._initialize_status()
        
        # Initialize tracking file if it doesn't exist
        if not self.tracking_file.exists():
            self._initialize_tracking()
    
    def _initialize_status(self):
        """Initialize status file with default values"""
        initial_status = {
            'status': 'idle',
            'last_updated': datetime.now().isoformat(),
            'total_applications': 0,
            'successful_applications': 0,
            'failed_applications': 0,
            'current_job': None,
            'uptime_start': None,
            'errors': []
        }
        self._write_status(initial_status)
    
    def _initialize_tracking(self):
        """Initialize tracking file"""
        self._write_tracking({})
    
    def _read_status(self) -> Dict[str, Any]:
        """Read current status from file"""
        try:
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading status: {e}")
            return {}
    
    def _write_status(self, status: Dict[str, Any]):
        """Write status to file"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            print(f"Error writing status: {e}")
    
    def _read_tracking(self) -> Dict[str, Any]:
        """Read tracking data from file"""
        try:
            with open(self.tracking_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading tracking data: {e}")
            return {}
    
    def _write_tracking(self, tracking: Dict[str, Any]):
        """Write tracking data to file"""
        try:
            with open(self.tracking_file, 'w') as f:
                json.dump(tracking, f, indent=2)
        except Exception as e:
            print(f"Error writing tracking data: {e}")
    
    def set_status(self, status: str):
        """
        Set bot status
        
        Args:
            status: One of 'idle', 'running', 'paused', 'error'
        """
        current = self._read_status()
        current['status'] = status
        current['last_updated'] = datetime.now().isoformat()
        
        # Set uptime start when starting
        if status == 'running' and not current.get('uptime_start'):
            current['uptime_start'] = datetime.now().isoformat()
        
        # Clear uptime when stopping
        if status == 'idle':
            current['uptime_start'] = None
            current['current_job'] = None
        
        self._write_status(current)
    
    def set_current_job(self, job_info: Optional[str]):
        """
        Set the current job being processed
        
        Args:
            job_info: String describing the current job or None
        """
        current = self._read_status()
        current['current_job'] = job_info
        current['last_updated'] = datetime.now().isoformat()
        self._write_status(current)
    
    def add_error(self, error_message: str, max_errors: int = 10):
        """
        Add an error to the error list
        
        Args:
            error_message: The error message
            max_errors: Maximum number of errors to keep
        """
        current = self._read_status()
        errors = current.get('errors', [])
        
        # Add new error with timestamp
        errors.insert(0, {
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only the latest errors
        current['errors'] = errors[:max_errors]
        current['last_updated'] = datetime.now().isoformat()
        self._write_status(current)
    
    def clear_errors(self):
        """Clear all errors"""
        current = self._read_status()
        current['errors'] = []
        current['last_updated'] = datetime.now().isoformat()
        self._write_status(current)
    
    def track_application(self, job_id: str, job_data: Dict[str, Any]):
        """
        Track a job application
        
        Args:
            job_id: Unique identifier for the job
            job_data: Dictionary containing application details
                Required keys: company, position, status
                Optional keys: job_url, location, applied_date, error, notes
        """
        tracking = self._read_tracking()
        
        # Add timestamp if not provided
        if 'timestamp' not in job_data:
            job_data['timestamp'] = datetime.now().isoformat()
        
        # Store the application
        tracking[job_id] = job_data
        self._write_tracking(tracking)
        
        # Update status counts
        self._update_counts()
    
    def _update_counts(self):
        """Update application counts in status"""
        tracking = self._read_tracking()
        current = self._read_status()
        
        total = len(tracking)
        successful = sum(1 for app in tracking.values() if app.get('status') == 'success')
        failed = sum(1 for app in tracking.values() if app.get('status') == 'failed')
        
        current['total_applications'] = total
        current['successful_applications'] = successful
        current['failed_applications'] = failed
        current['last_updated'] = datetime.now().isoformat()
        
        self._write_status(current)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return self._read_status()
    
    def get_tracking_data(self) -> Dict[str, Any]:
        """Get all tracking data"""
        return self._read_tracking()
    
    def get_application(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific application"""
        tracking = self._read_tracking()
        return tracking.get(job_id)
    
    def update_application_status(self, job_id: str, status: str, error: Optional[str] = None):
        """
        Update the status of an existing application
        
        Args:
            job_id: The job identifier
            status: New status ('success', 'failed', 'pending')
            error: Error message if failed
        """
        tracking = self._read_tracking()
        
        if job_id in tracking:
            tracking[job_id]['status'] = status
            tracking[job_id]['last_updated'] = datetime.now().isoformat()
            
            if error:
                tracking[job_id]['error'] = error
            
            self._write_tracking(tracking)
            self._update_counts()
    
    def clear_tracking(self):
        """Clear all tracking data (use with caution!)"""
        self._write_tracking({})
        self._update_counts()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get application statistics"""
        tracking = self._read_tracking()
        
        stats = {
            'total': len(tracking),
            'successful': 0,
            'failed': 0,
            'pending': 0,
            'today': 0,
            'this_week': 0
        }
        
        today = datetime.now().date()
        
        for app in tracking.values():
            status = app.get('status', 'unknown')
            
            if status == 'success':
                stats['successful'] += 1
            elif status == 'failed':
                stats['failed'] += 1
            elif status == 'pending':
                stats['pending'] += 1
            
            # Count today's and this week's applications
            app_date_str = app.get('applied_date', app.get('timestamp', ''))
            if app_date_str:
                try:
                    app_date = datetime.fromisoformat(app_date_str.replace('Z', '+00:00')).date()
                    if app_date == today:
                        stats['today'] += 1
                    if (today - app_date).days <= 7:
                        stats['this_week'] += 1
                except:
                    pass
        
        return stats


# Example usage
if __name__ == '__main__':
    manager = StatusManager()
    
    # Set bot status
    manager.set_status('running')
    
    # Track an application
    job_data = {
        'company': 'Tech Corp',
        'position': 'Performance Test Engineer',
        'status': 'success',
        'job_url': 'https://example.com/job/123',
        'location': 'Remote',
        'applied_date': datetime.now().isoformat()
    }
    manager.track_application('JOB123456', job_data)
    
    # Set current job
    manager.set_current_job('Applying to Software Engineer at Google')
    
    # Add an error
    manager.add_error('Failed to submit application - form validation error')
    
    # Get status
    status = manager.get_status()
    print(f"Current status: {status}")
    
    # Get statistics
    stats = manager.get_statistics()
    print(f"Statistics: {stats}")
    
    # Update application status
    manager.update_application_status('JOB123456', 'failed', 'Application rejected')
    
    # Set to idle
    manager.set_status('idle')