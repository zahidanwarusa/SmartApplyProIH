import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Set

class APIKeyManager:
    """Manages multiple API keys with usage tracking and rotation"""
    
    def __init__(self, api_keys: List[str], data_dir: Path, 
                daily_limit: int = 1500, warning_threshold: float = 0.95):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.daily_limit = daily_limit
        self.warning_threshold = warning_threshold  # Percentage threshold for warning (e.g., 95%)
        self.data_dir = data_dir
        self.usage_file = data_dir / 'tracking' / 'api_usage.json'
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Ensure the tracking directory exists
        (data_dir / 'tracking').mkdir(parents=True, exist_ok=True)
        
        # Load or initialize usage data
        self.usage_data = self._load_usage_data()
        
        # Find the first available key that hasn't reached its limit
        self._find_available_key()
    
    def _load_usage_data(self) -> Dict:
        """Load API usage data from file or initialize if not exists"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    usage_data = json.load(f)
                
                # Check if today's date matches, otherwise reset counts
                today = datetime.now().strftime("%Y-%m-%d")
                if usage_data.get('date') != today:
                    self.logger.info(f"New day detected ({today}). Resetting API usage counts.")
                    usage_data = {
                        'date': today,
                        'keys': {key: 0 for key in self.api_keys}
                    }
                    
                # Check for any new keys not in the usage data
                for key in self.api_keys:
                    if key not in usage_data['keys']:
                        usage_data['keys'][key] = 0
                        
                # Save the updated usage data
                self._save_usage_data(usage_data)
                return usage_data
            except Exception as e:
                self.logger.error(f"Error loading API usage data: {e}")
        
        # Initialize new usage data
        today = datetime.now().strftime("%Y-%m-%d")
        usage_data = {
            'date': today,
            'keys': {key: 0 for key in self.api_keys}
        }
        self._save_usage_data(usage_data)
        return usage_data
    
    def _save_usage_data(self, usage_data: Dict) -> None:
        """Save API usage data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(usage_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving API usage data: {e}")
    
    def _find_available_key(self) -> bool:
        """Find the next API key that hasn't reached its limit"""
        original_index = self.current_key_index
        
        while True:
            current_key = self.api_keys[self.current_key_index]
            current_usage = self.usage_data['keys'].get(current_key, 0)
            
            if current_usage < self.daily_limit:
                return True
            
            # Move to the next key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            
            # If we've checked all keys and returned to the original, all keys are at limit
            if self.current_key_index == original_index:
                self.logger.warning("All API keys have reached their daily limit")
                return False
    
    def get_current_key(self) -> str:
        """Get the current API key"""
        return self.api_keys[self.current_key_index]
    
    def increment_usage(self) -> bool:
        """Increment usage counter for the current key and rotate if needed
        
        Returns:
            bool: True if a key is available, False if all keys are at limit
        """
        current_key = self.get_current_key()
        self.usage_data['keys'][current_key] += 1
        
        # Check if we're approaching the limit
        current_usage = self.usage_data['keys'][current_key]
        if current_usage >= self.daily_limit * self.warning_threshold and current_usage < self.daily_limit:
            self.logger.warning(f"API key is at {(current_usage / self.daily_limit) * 100:.1f}% of its daily limit")
        
        # If we've reached the limit, try to find another key
        if current_usage >= self.daily_limit:
            self.logger.warning(f"API key has reached its daily limit of {self.daily_limit}")
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            available = self._find_available_key()
            if available:
                self.logger.info(f"Switched to another API key")
            
            # Save updated usage data
            self._save_usage_data(self.usage_data)
            return available
        
        # Save updated usage data
        self._save_usage_data(self.usage_data)
        return True
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics for all keys"""
        result = {
            'date': self.usage_data['date'],
            'total_usage': sum(self.usage_data['keys'].values()),
            'keys': {}
        }
        
        for i, key in enumerate(self.api_keys):
            masked_key = f"{key[:5]}...{key[-4:]}"
            usage = self.usage_data['keys'].get(key, 0)
            percentage = (usage / self.daily_limit) * 100
            is_current = (i == self.current_key_index)
            
            result['keys'][masked_key] = {
                'usage': usage,
                'limit': self.daily_limit,
                'percentage': percentage,
                'is_current': is_current
            }
        
        return result
    
    def all_keys_exhausted(self) -> bool:
        """Check if all API keys have reached their daily limit"""
        for key in self.api_keys:
            if self.usage_data['keys'].get(key, 0) < self.daily_limit:
                return False
        return True