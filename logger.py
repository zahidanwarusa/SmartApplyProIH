import logging
import os
from pathlib import Path
from datetime import datetime
import json

class DashboardLogger:
    """
    Custom logger for SmartApplyPro that writes to both console and log files
    for dashboard integration
    """
    
    def __init__(self, name='SmartApplyPro', log_dir='logs'):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler for main log
        main_log_file = self.log_dir / 'bot.log'
        file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # File handler for errors only
        error_log_file = self.log_dir / 'errors.log'
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        self.info(f"Logger initialized - Logs directory: {self.log_dir.absolute()}")
    
    def debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
    
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message, exc_info=False):
        """Log error message"""
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message, exc_info=False):
        """Log critical message"""
        self.logger.critical(message, exc_info=exc_info)
    
    def log_application(self, job_data, status, error=None):
        """
        Log application attempt with structured data
        
        Args:
            job_data: Dictionary with job information (company, position, job_id, etc.)
            status: 'success', 'failed', or 'pending'
            error: Error message if failed
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'company': job_data.get('company', 'Unknown'),
            'position': job_data.get('position', 'Unknown'),
            'job_id': job_data.get('job_id', 'Unknown'),
            'status': status,
            'error': error
        }
        
        message = f"Application {status.upper()} - {job_data.get('company')} - {job_data.get('position')}"
        
        if status == 'success':
            self.info(message)
        elif status == 'failed':
            self.error(f"{message} - Error: {error}")
        else:
            self.info(message)
        
        # Write to applications log
        app_log_file = self.log_dir / 'applications.log'
        with open(app_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def close(self):
        """Close all handlers"""
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)


# Example usage
if __name__ == '__main__':
    logger = DashboardLogger()
    
    logger.info("Bot started")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    # Log an application
    job_data = {
        'company': 'Tech Corp',
        'position': 'Performance Test Engineer',
        'job_id': 'JOB123456',
        'location': 'Remote'
    }
    
    logger.log_application(job_data, 'success')
    logger.log_application(job_data, 'failed', error='Application form not found')
    
    logger.info("Bot stopped")
