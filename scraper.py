import requests
from bs4 import BeautifulSoup
import json
import random
import time
import logging
from typing import Optional, Dict, Any
from proxy_manager import ProxyManager
from browser_fingerprint import BrowserFingerprint
from delay_manager import DelayManager
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import os
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AmazonScraper:
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.browser_fingerprint = BrowserFingerprint()
        self.delay_manager = DelayManager()
        self.browserless_api_key = os.getenv('BROWSERLESS_API_KEY')
        
    async def initialize(self):
        """Initialize the scraper components"""
        await self.proxy_manager.validate_all_proxies()
        
    async def scrape_with_browserless(self, asin: str) -> Optional[Dict[str, Any]]:
        """Scrape using Browserless with captcha solving capability"""
        url = f"https://www.amazon.in/dp/{asin}"
        
        try:
            # Prepare the Browserless API request with token in URL
            browserless_url = f"https://browserless.tripxap.com/content?token={self.browserless_api_key}"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Enhanced payload with captcha solving capabilities
            payload = {
                "url": url,
                "waitForFunction": {
                    "fn": """async () => {
                    try {
                        const cdp = await page.createCDPSession();
                        // Wait for any captcha to appear
                        const captchaExists = await page.$('form[action*="/errors/validateCaptcha"]');
                        if (captchaExists) {
                            console.log('Captcha found, attempting to solve...');
                            const { solved, error } = await cdp.send('Browserless.solveCaptcha');
                            if (solved) {
                                console.log('Captcha solved successfully');
                                // Wait for navigation after captcha
                                await page.waitForNavigation({ waitUntil: 'networkidle0' });
                            } else {
                                console.error('Failed to solve captcha:', error);
                            }
                        }
                        // Wait for product title as indication of successful page load
                        await page.waitForSelector('#productTitle', { timeout: 10000 });
                        return true;
                    } catch (e) {
                        console.error('Error in waitForFunction:', e);
                        return false;
                    }
                }""",
                    "polling": 1000,  # Poll every second
                    "timeout": 30000  # 30 second timeout
                },
                "waitForTimeout": 15000  # Increased timeout to allow for captcha solving
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(browserless_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        if "To discuss automated access to Amazon data please contact" in html_content:
                            logger.error("Amazon blocked the request despite captcha solving attempt")
                            return None
                        soup = BeautifulSoup(html_content, 'html.parser')
                        return self._extract_product_data(soup)
                    else:
                        error_text = await response.text()
                        logger.error(f"Browserless API error: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error in Browserless scraping: {str(e)}")
            return None
    
    def _extract_product_data_from_browserless(self, browserless_result: Dict) -> Dict[str, Any]:
        """Extract product data from Browserless API response"""
        product_data = {}
        
        # Helper function to get text from element
        def get_text(element, default='Not found'):
            return element.get('text', default).strip() if element else default
        
        # Extract data from Browserless response
        elements = browserless_result.get('elements', [])
        element_map = {el.get('selector'): el for el in elements}
        
        # Product Title
        product_data['title'] = get_text(element_map.get('#productTitle'))
        
        # Price
        product_data['price'] = get_text(element_map.get('.a-price-whole'))
        
        # MRP
        mrp_element = element_map.get('.a-price.a-text-price')
        if mrp_element:
            mrp = mrp_element.get('text', '').strip()
            product_data['mrp'] = mrp if mrp else 'Not found'
        else:
            product_data['mrp'] = 'Not found'
        
        # ASIN
        asin_element = element_map.get("input[name='ASIN']")
        product_data['asin'] = asin_element.get('value', 'Not found') if asin_element else 'Not found'
        
        # SKU ID (Item model number)
        product_data['sku_id'] = 'Not found'  # This will need to be extracted from the page content
        
        # Percentage Discount
        discount_element = element_map.get('.savingsPercentage')
        product_data['percentage_discount'] = get_text(discount_element)
        
        # Rating
        rating_element = element_map.get('.a-icon-alt')
        product_data['rating'] = rating_element.get('text', 'Not found').split()[0] if rating_element else 'Not found'
        
        # Number of ratings
        num_ratings_element = element_map.get('#acrCustomerReviewText')
        product_data['num_ratings'] = get_text(num_ratings_element)
        
        # About this item
        about_items = []
        feature_bullets = element_map.get('#feature-bullets')
        if feature_bullets:
            # Extract bullet points from the feature bullets section
            # This will need to be adjusted based on the actual HTML structure
            pass
        product_data['about_this_item'] = about_items if about_items else 'Not found'
        
        # Content type
        aplus_element = element_map.get('#aplus')
        regular_desc_element = element_map.get('#productDescription')
        
        if aplus_element:
            product_data['content_type'] = 'A+ Content'
        elif regular_desc_element:
            product_data['content_type'] = 'Regular Description'
        else:
            product_data['content_type'] = 'No Description'
        
        # Images
        product_data['images'] = []
        alt_images_div = element_map.get('#altImages')
        if alt_images_div:
            # Extract image URLs from the altImages div
            # This will need to be adjusted based on the actual HTML structure
            pass
        
        return product_data
    
    async def scrape_with_requests(self, asin: str) -> Optional[Dict[str, Any]]:
        """Scrape using requests with advanced anti-detection"""
        url = f"https://www.amazon.in/dp/{asin}"
        
        for attempt in range(3):
            try:
                # Get delay and wait
                self.delay_manager.wait(url)
                
                # Get proxy
                proxy = self.proxy_manager.get_proxy()
                
                # Prepare headers with browser fingerprint
                headers = self.browser_fingerprint.get_headers()
                
                if proxy:
                    # Use proxy if available
                    connector = ProxyConnector.from_url(proxy['proxy'])
                    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                        async with session.get(url, timeout=30) as response:
                            if response.status == 200:
                                text = await response.text()
                                if "captcha" not in text.lower():
                                    self.proxy_manager.mark_proxy_success(proxy)
                                    return self._extract_product_data(BeautifulSoup(text, 'html.parser'))
                                else:
                                    self.proxy_manager.mark_proxy_failed(proxy)
                            else:
                                self.proxy_manager.mark_proxy_failed(proxy)
                else:
                    # Fallback to direct request if no proxies available
                    logger.warning("No proxies available, falling back to direct request")
                    async with aiohttp.ClientSession(headers=headers) as session:
                        async with session.get(url, timeout=30) as response:
                            if response.status == 200:
                                text = await response.text()
                                if "captcha" not in text.lower():
                                    return self._extract_product_data(BeautifulSoup(text, 'html.parser'))
                
                # If we get here, the request failed
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                if proxy:
                    self.proxy_manager.mark_proxy_failed(proxy)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        return None
    
    def _extract_product_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract product data from BeautifulSoup object"""
        product_data = {}
        
        # Product Title
        title_element = soup.find('span', {'id': 'productTitle'})
        product_data['title'] = title_element.text.strip() if title_element else 'Not found'
        
        # Price
        price_element = soup.find('span', {'class': 'a-price-whole'})
        product_data['price'] = price_element.text.strip() if price_element else 'Not found'
        
        # MRP
        mrp_element = soup.find('span', {'class': 'a-price a-text-price'})
        if mrp_element:
            mrp = mrp_element.find('span', {'class': 'a-offscreen'})
            product_data['mrp'] = mrp.text.strip() if mrp else 'Not found'
        else:
            product_data['mrp'] = 'Not found'
        
        # ASIN
        asin_element = soup.find('input', {'name': 'ASIN'})
        product_data['asin'] = asin_element['value'] if asin_element else 'Not found'
        
        # SKU ID (Item model number)
        sku_id = None
        # Try multiple selectors for different page layouts
        sku_selectors = [
            # Product Details section
            'div#productDetails_detailBullets_sections1',
            # Product Specifications section
            'div#productDetails_techSpec_section_1',
            # Model number row
            'tr.po-model_number',
            'tr.model_number',
            # Direct model number span
            'span:-soup-contains("Model Number") + span',
            'span:-soup-contains("Item model number") + span'
        ]
        
        for selector in sku_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    if selector.startswith('tr'):
                        sku_id = element.find('td').text.strip()
                    else:
                        sku_id = element.text.strip()
                    break
            except:
                continue
        
        product_data['sku_id'] = sku_id if sku_id else 'Not found'
        
        # Percentage Discount
        discount_element = soup.find('span', {'class': 'savingsPercentage'})
        product_data['percentage_discount'] = discount_element.text.strip() if discount_element else 'Not found'
        
        # Rating
        rating_element = soup.find('span', {'class': 'a-icon-alt'})
        product_data['rating'] = rating_element.text.split()[0] if rating_element else 'Not found'
        
        # Number of ratings
        num_ratings_element = soup.find('span', {'id': 'acrCustomerReviewText'})
        product_data['num_ratings'] = num_ratings_element.text.strip() if num_ratings_element else 'Not found'
        
        # About this item
        about_items = []
        try:
            feature_bullets = soup.find('div', {'id': 'feature-bullets'})
            if feature_bullets:
                bullet_points = feature_bullets.find_all('span', {'class': 'a-list-item'})
                about_items = [bullet.text.strip() for bullet in bullet_points if bullet.text.strip()]
        except Exception as e:
            logger.warning(f"Error extracting About this item: {str(e)}")
            
        product_data['about_this_item'] = about_items if about_items else 'Not found'
        
        # Check for content type (A+ Content vs Regular Description)
        aplus_element = soup.find('div', {'id': 'aplus'})
        regular_desc_element = soup.find('div', {'id': 'productDescription'})
        
        if aplus_element:
            product_data['content_type'] = 'A+ Content'
        elif regular_desc_element:
            product_data['content_type'] = 'Regular Description'
        else:
            product_data['content_type'] = 'No Description'
        
        # Images
        product_data['images'] = []
        alt_images_div = soup.find('div', {'id': 'altImages'})
        if alt_images_div:
            thumbnail_images = alt_images_div.find_all('img', src=True)
            for img in thumbnail_images:
                src = img.get('src', '')
                if src and '/images/I/' in src:
                    try:
                        image_id = src.split('/images/I/')[1].split('._')[0]
                        image_url = f"https://m.media-amazon.com/images/I/{image_id}._SY395_.jpg"
                        if image_url not in product_data['images']:
                            product_data['images'].append(image_url)
                    except IndexError:
                        continue
        
        return product_data
    
    async def scrape_product(self, asin: str) -> Optional[Dict[str, Any]]:
        """Main scraping method that tries different approaches"""
        # Try Browserless first
        result = await self.scrape_with_browserless(asin)
        if result:
            return result
            
        # If Browserless fails, try requests
        return await self.scrape_with_requests(asin)

# For backward compatibility
async def scrape_amazon_product(asin: str) -> Optional[Dict[str, Any]]:
    """Backward compatible function that uses the new scraper"""
    scraper = AmazonScraper()
    await scraper.initialize()
    return await scraper.scrape_product(asin) 