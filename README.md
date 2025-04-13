# Amazon Product Scraper API

A FastAPI-based web service that scrapes product information from Amazon using ASIN (Amazon Standard Identification Number).

## Features

- Scrape detailed product information from Amazon using ASIN
- Secure API with token-based authentication
- Returns comprehensive product data including:
  - Product title
  - Current price and MRP
  - ASIN and SKU ID
  - Discount percentage
  - Product ratings and review count
  - About this item section
  - Product images
  - Content type (A+ Content or Regular Description)

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd fastapi_scraper
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following variables:
```
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN=your_access_token_here
```

## Usage

1. Start the server:
```bash
python main.py
```

2. The API will be available at `http://localhost:8000`

3. Make requests to the API using the following endpoint:
```
GET /product/{asin}
```

### Example Request

```bash
curl -X GET "http://localhost:8000/product/B08N5KWB9H" \
     -H "Authorization: Bearer your_access_token_here"
```

### Example Response

```json
{
    "title": "Product Title",
    "price": "₹1,999",
    "mrp": "₹2,999",
    "asin": "B08N5KWB9H",
    "sku_id": "ABC123",
    "percentage_discount": "33.33%",
    "rating": "4.5",
    "num_ratings": "1,234 ratings",
    "about_this_item": ["Feature 1", "Feature 2", "Feature 3"],
    "content_type": "A+ Content",
    "images": ["https://m.media-amazon.com/images/I/image1.jpg", "https://m.media-amazon.com/images/I/image2.jpg"]
}
```

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Security

The API uses token-based authentication. Include your access token in the Authorization header for all requests:
```
Authorization: Bearer your_access_token_here
```

## Error Handling

The API returns appropriate HTTP status codes:
- 200: Successful request
- 401: Invalid or missing authentication token
- 404: Product not found or error during scraping

## Dependencies

- FastAPI: Web framework for building APIs
- Uvicorn: ASGI server
- Requests: HTTP library
- BeautifulSoup4: HTML parsing library
- Python-JOSE: JWT implementation
- Python-dotenv: Environment variable management
