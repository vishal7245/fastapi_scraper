import requests
from bs4 import BeautifulSoup
import json

def scrape_amazon_product(asin):
    # Construct Amazon URL from ASIN
    url = f"https://www.amazon.in/dp/{asin}"
    
    # Set headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        # Send GET request to the URL
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product information
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
        
        # Try Product Details section first
        product_details = soup.find('div', {'id': 'productDetails_detailBullets_sections1'})
        if product_details:
            for row in product_details.find_all('tr'):
                if 'Item model number' in row.text:
                    sku_id = row.find('td').text.strip()
                    break
        
        # If not found, try Product Specifications section
        if not sku_id:
            specs_table = soup.find('table', {'id': 'productDetails_techSpec_section_1'})
            if specs_table:
                for row in specs_table.find_all('tr'):
                    if 'Model Number' in row.text:
                        sku_id = row.find('td').text.strip()
                        break
        
        # If still not found, try the po-model_number class
        if not sku_id:
            sku_element = soup.find('tr', {'class': 'po-model_number'})
            if sku_element:
                sku_value = sku_element.find('td', {'class': 'a-span9'})
                sku_id = sku_value.text.strip() if sku_value else None
        
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
        about_section = soup.find('ul', {'class': 'a-unordered-list a-vertical a-spacing-small'})
        if about_section:
            bullet_points = about_section.find_all('li')
            for bullet in bullet_points:
                span = bullet.find('span', {'class': 'a-list-item a-size-base a-color-base'})
                if span and span.text.strip():
                    about_items.append(span.text.strip())
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
        
    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None
    except Exception as e:
        print(f"Error processing the page: {e}")
        return None 