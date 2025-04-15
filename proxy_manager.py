import aiohttp
import asyncio
import random
import logging
from typing import List, Dict, Optional
from aiohttp_socks import ProxyConnector
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self):
        self.proxies: List[Dict] = []
        self.working_proxies: List[Dict] = []
        self.failed_proxies: List[Dict] = []
        self.proxy_timeouts: Dict[str, datetime] = {}
        self.load_proxies()
        
    def load_proxies(self):
        """Load proxies from environment variables or configuration"""
        # Load from environment variables
        proxy_list = os.getenv('PROXY_LIST', '').split(',')
        
        for proxy in proxy_list:
            if proxy.strip():
                self.proxies.append({
                    'proxy': proxy.strip(),
                    'last_used': None,
                    'failures': 0,
                    'successes': 0
                })
    
    async def validate_proxy(self, proxy: Dict) -> bool:
        """Validate if a proxy is working"""
        try:
            connector = ProxyConnector.from_url(proxy['proxy'])
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get('https://www.amazon.in', timeout=10) as response:
                    if response.status == 200:
                        return True
        except Exception as e:
            logger.error(f"Proxy validation failed for {proxy['proxy']}: {str(e)}")
            return False
        return False
    
    async def validate_all_proxies(self):
        """Validate all proxies asynchronously"""
        tasks = [self.validate_proxy(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)
        
        for proxy, is_valid in zip(self.proxies, results):
            if is_valid:
                self.working_proxies.append(proxy)
            else:
                self.failed_proxies.append(proxy)
    
    def get_proxy(self) -> Optional[Dict]:
        """Get a random working proxy with smart selection"""
        if not self.working_proxies:
            return None
            
        # Filter out proxies that are in timeout
        available_proxies = [
            p for p in self.working_proxies
            if p['proxy'] not in self.proxy_timeouts or
            datetime.now() > self.proxy_timeouts[p['proxy']]
        ]
        
        if not available_proxies:
            return None
            
        # Select proxy based on success rate and last used time
        proxy = max(available_proxies, key=lambda p: (
            p['successes'] / (p['successes'] + p['failures'] + 1) if (p['successes'] + p['failures']) > 0 else 1,
            -((datetime.now() - p['last_used']).total_seconds() if p['last_used'] else 0)
        ))
        
        proxy['last_used'] = datetime.now()
        return proxy
    
    def mark_proxy_failed(self, proxy: Dict):
        """Mark a proxy as failed and handle timeout"""
        proxy['failures'] += 1
        if proxy['failures'] >= 3:  # After 3 failures, timeout the proxy
            self.proxy_timeouts[proxy['proxy']] = datetime.now() + timedelta(minutes=30)
            self.working_proxies.remove(proxy)
            self.failed_proxies.append(proxy)
    
    def mark_proxy_success(self, proxy: Dict):
        """Mark a proxy as successful"""
        proxy['successes'] += 1
        if proxy['failures'] > 0:
            proxy['failures'] -= 1  # Reduce failure count on success
    
    def rotate_proxies(self):
        """Rotate the proxy list to prevent pattern detection"""
        random.shuffle(self.working_proxies)
        
    async def refresh_proxies(self):
        """Refresh the proxy list periodically"""
        # This could be implemented to fetch new proxies from a provider
        # or rotate through a larger pool of proxies
        pass 