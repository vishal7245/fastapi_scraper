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
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector

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
        self.driver = None
        
    async def initialize(self):
        """Initialize the scraper components"""
        await self.proxy_manager.validate_all_proxies()
        
    def setup_driver(self):
        """Setup undetected-chromedriver"""
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--start-maximized')
        
        # Set random viewport size
        width, height = random.choice(self.browser_fingerprint.screen_resolutions)
        options.add_argument(f'--window-size={width},{height}')
        
        # Let undetected-chromedriver handle Chrome binary detection
        self.driver = uc.Chrome(
            options=options,
            driver_executable_path=None,  # Let it use the default path
            browser_executable_path=None  # Let it detect Chrome automatically
        )
        
    async def scrape_with_selenium(self, asin: str) -> Optional[Dict[str, Any]]:
        """Scrape using Selenium with undetected-chromedriver"""
        if not self.driver:
            self.setup_driver()
            
        url = f"https://www.amazon.in/dp/{asin}"
        
        try:
            self.driver.get(url)
            
            # Wait for page load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "productTitle"))
            )
            
            # Check for captcha
            if "captcha" in self.driver.page_source.lower():
                logger.warning("Captcha detected, retrying with different method")
                return await self.scrape_with_requests(asin)
            
            # Extract data using Selenium
            product_data = {}
            
            # Product Title
            title_element = self.driver.find_element(By.ID, "productTitle")
            product_data['title'] = title_element.text.strip()
            
            # Price
            try:
                price_element = self.driver.find_element(By.CLASS_NAME, "a-price-whole")
                product_data['price'] = price_element.text.strip()
            except:
                product_data['price'] = 'Not found'
            
            # MRP
            try:
                mrp_element = self.driver.find_element(By.CLASS_NAME, "a-price a-text-price")
                mrp = mrp_element.find_element(By.CLASS_NAME, "a-offscreen")
                product_data['mrp'] = mrp.text.strip()
            except:
                product_data['mrp'] = 'Not found'
            
            # ASIN
            asin_element = self.driver.find_element(By.NAME, 'ASIN')
            product_data['asin'] = asin_element.get_attribute('value') if asin_element else 'Not found'
            
            # SKU ID (Item model number)
            sku_id = None
            
            # Try multiple selectors for different page layouts
            sku_selectors = [
                # Product Details section
                (By.ID, 'productDetails_detailBullets_sections1'),
                # Product Specifications section
                (By.ID, 'productDetails_techSpec_section_1'),
                # Model number row
                (By.XPATH, '//tr[contains(@class, "model_number")]'),
                (By.XPATH, '//tr[contains(@class, "po-model_number")]'),
                # Direct model number span
                (By.XPATH, '//span[contains(text(), "Model Number")]/following-sibling::span'),
                (By.XPATH, '//span[contains(text(), "Item model number")]/following-sibling::span')
            ]
            
            for selector_type, selector in sku_selectors:
                try:
                    if selector_type == By.ID:
                        element = self.driver.find_element(selector_type, selector)
                        rows = element.find_elements(By.TAG_NAME, 'tr')
                        for row in rows:
                            if any(keyword in row.text.lower() for keyword in ['model number', 'item model number']):
                                sku_id = row.find_element(By.TAG_NAME, 'td').text.strip()
                                break
                    else:
                        element = self.driver.find_element(selector_type, selector)
                        if element:
                            sku_id = element.text.strip()
                            break
                except:
                    continue
                
                if sku_id:
                    break
            
            product_data['sku_id'] = sku_id if sku_id else 'Not found'
            
            # Percentage Discount
            discount_element = self.driver.find_element(By.CLASS_NAME, 'savingsPercentage')
            if discount_element:
                product_data['percentage_discount'] = discount_element.text.strip()
            else:
                # Calculate discount percentage if we have both price and MRP
                if product_data['price'] != 'Not found' and product_data['mrp'] != 'Not found':
                    try:
                        price = float(product_data['price'].replace(',', ''))
                        mrp = float(product_data['mrp'].replace('₹', '').replace(',', '').strip())
                        discount = ((mrp - price) / mrp) * 100
                        product_data['percentage_discount'] = f"{discount:.2f}%"
                    except (ValueError, ZeroDivisionError):
                        product_data['percentage_discount'] = 'Not found'
                else:
                    product_data['percentage_discount'] = 'Not found'
            
            # Rating
            rating_element = self.driver.find_element(By.CLASS_NAME, 'a-icon-alt')
            product_data['rating'] = rating_element.text.split()[0] if rating_element else 'Not found'
            
            # Number of ratings
            num_ratings_element = self.driver.find_element(By.ID, 'acrCustomerReviewText')
            product_data['num_ratings'] = num_ratings_element.text.strip() if num_ratings_element else 'Not found'
            
            # About this item
            about_items = []
            try:
                # Try multiple selectors for different page layouts
                selectors = [
                    'div#feature-bullets ul.a-unordered-list li span.a-list-item',
                    'div#feature-bullets ul.a-vertical-spacing-small li span.a-list-item',
                    'div#feature-bullets ul.a-spacing-small li span.a-list-item',
                    'div#feature-bullets ul.a-vertical li span.a-list-item',
                    'div#feature-bullets ul li span.a-list-item',
                    'div#feature-bullets ul li span.a-text-bold',
                    'div#feature-bullets ul li'
                ]
                
                for selector in selectors:
                    bullet_points = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if bullet_points:
                        for bullet in bullet_points:
                            text = bullet.text.strip()
                            if text and text not in about_items:  # Avoid duplicates
                                about_items.append(text)
                        if about_items:  # If we found items with this selector, break
                            break
                            
                # If still no items found, try alternative approach
                if not about_items:
                    feature_bullets = self.driver.find_element(By.ID, 'feature-bullets')
                    if feature_bullets:
                        # Get all text content and split by newlines
                        all_text = feature_bullets.text.strip()
                        items = [item.strip() for item in all_text.split('\n') if item.strip()]
                        about_items = items
                        
            except Exception as e:
                logger.warning(f"Error extracting About this item: {str(e)}")
                
            product_data['about_this_item'] = about_items if about_items else 'Not found'
            
            # Check for content type (A+ Content vs Regular Description)
            aplus_element = self.driver.find_element(By.ID, 'aplus')
            regular_desc_element = self.driver.find_element(By.ID, 'productDescription')
            
            if aplus_element:
                product_data['content_type'] = 'A+ Content'
            elif regular_desc_element:
                product_data['content_type'] = 'Regular Description'
            else:
                product_data['content_type'] = 'No Description'
            
            # Images
            product_data['images'] = []
            
            # Find the altImages div containing thumbnails
            alt_images_div = self.driver.find_element(By.ID, 'altImages')
            if alt_images_div:
                # Find all thumbnail images
                thumbnail_images = alt_images_div.find_elements(By.TAG_NAME, 'img')
                for img in thumbnail_images:
                    src = img.get_attribute('src')
                    if src and '/images/I/' in src:
                        try:
                            # Extract image ID from the thumbnail URL
                            image_id = src.split('/images/I/')[1].split('._')[0]
                            # Construct full size image URL
                            image_url = f"https://m.media-amazon.com/images/I/{image_id}._SY395_.jpg"
                            if image_url not in product_data['images']:  # Avoid duplicates
                                product_data['images'].append(image_url)
                        except IndexError:
                            continue
            
            logger.info(f"Successfully scraped product: {asin}")
            return product_data
            
        except TimeoutException:
            logger.error("Timeout while waiting for page load")
            return None
        except WebDriverException as e:
            logger.error(f"WebDriver error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return None
    
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
            (By.ID, 'productDetails_detailBullets_sections1'),
            # Product Specifications section
            (By.ID, 'productDetails_techSpec_section_1'),
            # Model number row
            (By.XPATH, '//tr[contains(@class, "model_number")]'),
            (By.XPATH, '//tr[contains(@class, "po-model_number")]'),
            # Direct model number span
            (By.XPATH, '//span[contains(text(), "Model Number")]/following-sibling::span'),
            (By.XPATH, '//span[contains(text(), "Item model number")]/following-sibling::span')
        ]
        
        for selector_type, selector in sku_selectors:
            try:
                if selector_type == By.ID:
                    element = self.driver.find_element(selector_type, selector)
                    rows = element.find_elements(By.TAG_NAME, 'tr')
                    for row in rows:
                        if any(keyword in row.text.lower() for keyword in ['model number', 'item model number']):
                            sku_id = row.find_element(By.TAG_NAME, 'td').text.strip()
                            break
                else:
                    element = self.driver.find_element(selector_type, selector)
                    if element:
                        sku_id = element.text.strip()
                        break
            except:
                continue
            
            if sku_id:
                break
        
        product_data['sku_id'] = sku_id if sku_id else 'Not found'
        
        # Percentage Discount
        discount_element = soup.find('span', {'class': 'savingsPercentage'})
        if discount_element:
            product_data['percentage_discount'] = discount_element.text.strip()
        else:
            # Calculate discount percentage if we have both price and MRP
            if product_data['price'] != 'Not found' and product_data['mrp'] != 'Not found':
                try:
                    price = float(product_data['price'].replace(',', ''))
                    mrp = float(product_data['mrp'].replace('₹', '').replace(',', '').strip())
                    discount = ((mrp - price) / mrp) * 100
                    product_data['percentage_discount'] = f"{discount:.2f}%"
                except (ValueError, ZeroDivisionError):
                    product_data['percentage_discount'] = 'Not found'
            else:
                product_data['percentage_discount'] = 'Not found'
        
        # Rating
        rating_element = soup.find('span', {'class': 'a-icon-alt'})
        product_data['rating'] = rating_element.text.split()[0] if rating_element else 'Not found'
        
        # Number of ratings
        num_ratings_element = soup.find('span', {'id': 'acrCustomerReviewText'})
        product_data['num_ratings'] = num_ratings_element.text.strip() if num_ratings_element else 'Not found'
        
        # About this item
        about_items = []
        try:
            # Try multiple selectors for different page layouts
            selectors = [
                'div#feature-bullets ul.a-unordered-list li span.a-list-item',
                'div#feature-bullets ul.a-vertical-spacing-small li span.a-list-item',
                'div#feature-bullets ul.a-spacing-small li span.a-list-item',
                'div#feature-bullets ul.a-vertical li span.a-list-item',
                'div#feature-bullets ul li span.a-list-item',
                'div#feature-bullets ul li span.a-text-bold',
                'div#feature-bullets ul li'
            ]
            
            for selector in selectors:
                bullet_points = soup.select(selector)
                if bullet_points:
                    for bullet in bullet_points:
                        text = bullet.text.strip()
                        if text and text not in about_items:  # Avoid duplicates
                            about_items.append(text)
                    if about_items:  # If we found items with this selector, break
                        break
                        
            # If still no items found, try alternative approach
            if not about_items:
                feature_bullets = soup.find('div', {'id': 'feature-bullets'})
                if feature_bullets:
                    # Get all text content and split by newlines
                    all_text = feature_bullets.text.strip()
                    items = [item.strip() for item in all_text.split('\n') if item.strip()]
                    about_items = items
                    
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
        
        # Find the altImages div containing thumbnails
        alt_images_div = soup.find('div', {'id': 'altImages'})
        if alt_images_div:
            # Find all thumbnail images
            thumbnail_images = alt_images_div.find_all('img', src=True)
            for img in thumbnail_images:
                src = img.get('src', '')
                if src and '/images/I/' in src:
                    try:
                        # Extract image ID from the thumbnail URL
                        image_id = src.split('/images/I/')[1].split('._')[0]
                        # Construct full size image URL
                        image_url = f"https://m.media-amazon.com/images/I/{image_id}._SY395_.jpg"
                        if image_url not in product_data['images']:  # Avoid duplicates
                            product_data['images'].append(image_url)
                    except IndexError:
                        continue
        
        return product_data
    
    async def scrape_product(self, asin: str) -> Optional[Dict[str, Any]]:
        """Main scraping method that tries different approaches"""
        # Try Selenium first
        result = await self.scrape_with_selenium(asin)
        if result:
            return result
            
        # If Selenium fails, try requests
        return await self.scrape_with_requests(asin)
    
    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            self.driver.quit()
            self.driver = None

# For backward compatibility
async def scrape_amazon_product(asin: str) -> Optional[Dict[str, Any]]:
    """Backward compatible function that uses the new scraper"""
    scraper = AmazonScraper()
    await scraper.initialize()
    try:
        return await scraper.scrape_product(asin)
    finally:
        scraper.cleanup() 