from browserforge.headers import HeaderGenerator
from browserforge.fingerprints import FingerprintGenerator
import random
from typing import Dict, Any

class BrowserFingerprint:
    def __init__(self):
        self.header_gen = HeaderGenerator(
            browser=('chrome', 'firefox', 'safari', 'edge'),
            os=('windows', 'macos', 'linux'),
            device='desktop',
            locale=('en-US', 'en'),
            http_version=2
        )
        self.fingerprint_gen = FingerprintGenerator()
        self.screen_resolutions = [
            (1920, 1080),
            (1366, 768),
            (1536, 864),
            (1440, 900),
            (1280, 720),
            (2560, 1440),
            (3840, 2160)
        ]
        
    def get_headers(self) -> Dict[str, str]:
        """Generate realistic browser headers"""
        return self.header_gen.generate()
        
    def get_browser_info(self) -> Dict[str, Any]:
        """Get comprehensive browser information"""
        fingerprint = self.fingerprint_gen.generate()
        screen_res = random.choice(self.screen_resolutions)
        
        return {
            'user_agent': fingerprint.user_agent,
            'platform': fingerprint.platform,
            'language': fingerprint.accept_language,
            'screen_resolution': screen_res,
            'color_depth': random.choice([24, 32]),
            'timezone': fingerprint.timezone,
            'webgl_vendor': fingerprint.webgl_vendor,
            'webgl_renderer': fingerprint.webgl_renderer,
            'touch_support': fingerprint.touch_support,
            'fonts': fingerprint.fonts,
            'plugins': fingerprint.plugins,
            'webrtc': fingerprint.webrtc
        } 