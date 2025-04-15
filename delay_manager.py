import random
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

class DelayManager:
    def __init__(self):
        self.request_history: Dict[str, List[datetime]] = {}
        self.base_delays = {
            'normal': (2, 5),  # (min, max) seconds
            'aggressive': (1, 3),
            'conservative': (5, 10)
        }
        self.current_mode = 'normal'
        self.mode_history: List[str] = []
        self.last_mode_change = datetime.now()
        
    def get_delay(self, url: str) -> float:
        """Get appropriate delay based on request history and current mode"""
        now = datetime.now()
        
        # Clean up old history
        self._cleanup_history(now)
        
        # Update request history
        if url not in self.request_history:
            self.request_history[url] = []
        self.request_history[url].append(now)
        
        # Calculate request frequency
        frequency = self._calculate_frequency(url)
        
        # Adjust mode based on frequency
        self._adjust_mode(frequency)
        
        # Get base delay for current mode
        min_delay, max_delay = self.base_delays[self.current_mode]
        
        # Add jitter
        jitter = random.uniform(-0.5, 0.5)
        
        # Calculate final delay
        delay = random.uniform(min_delay, max_delay) + jitter
        
        # Add exponential backoff if too many recent requests
        if frequency > 3:  # More than 3 requests in the last minute
            delay *= (1.5 ** (frequency - 3))
        
        logger.debug(f"Delay for {url}: {delay:.2f}s (mode: {self.current_mode})")
        return delay
    
    def _cleanup_history(self, now: datetime):
        """Clean up request history older than 5 minutes"""
        cutoff = now - timedelta(minutes=5)
        for url in list(self.request_history.keys()):
            self.request_history[url] = [
                timestamp for timestamp in self.request_history[url]
                if timestamp > cutoff
            ]
            if not self.request_history[url]:
                del self.request_history[url]
    
    def _calculate_frequency(self, url: str) -> int:
        """Calculate request frequency for a URL in the last minute"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        return sum(1 for timestamp in self.request_history[url] if timestamp > one_minute_ago)
    
    def _adjust_mode(self, frequency: int):
        """Adjust delay mode based on request frequency"""
        now = datetime.now()
        
        # Don't change mode too frequently
        if (now - self.last_mode_change).total_seconds() < 60:
            return
        
        if frequency > 5:  # Too many requests
            new_mode = 'conservative'
        elif frequency < 2:  # Very few requests
            new_mode = 'aggressive'
        else:
            new_mode = 'normal'
        
        if new_mode != self.current_mode:
            self.current_mode = new_mode
            self.mode_history.append(new_mode)
            self.last_mode_change = now
            logger.info(f"Switched to {new_mode} mode due to frequency {frequency}")
    
    def wait(self, url: str):
        """Wait for the appropriate delay"""
        delay = self.get_delay(url)
        time.sleep(delay)
    
    def get_mode_history(self) -> List[str]:
        """Get the history of mode changes"""
        return self.mode_history 