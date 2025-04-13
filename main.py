from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from scraper import scrape_amazon_product
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

if not SECRET_KEY or not ACCESS_TOKEN:
    raise ValueError("SECRET_KEY and ACCESS_TOKEN must be set in .env file")

security = HTTPBearer()

app = FastAPI(
    title="Amazon Product Scraper API",
    description="API to scrape product information from Amazon using ASIN",
    version="1.0.0"
)

class ProductResponse(BaseModel):
    title: str
    price: str
    mrp: str
    asin: str
    sku_id: str
    percentage_discount: str
    rating: str
    num_ratings: str
    about_this_item: list | str
    content_type: str
    images: list[str]

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verify the bearer token
    """
    if credentials.credentials != ACCESS_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

@app.get("/product/{asin}", response_model=ProductResponse)
async def get_product_info(asin: str, token: str = Depends(verify_token)):
    """
    Get product information from Amazon using ASIN
    
    - **asin**: Amazon Standard Identification Number (ASIN)
    """
    product_data = scrape_amazon_product(asin)
    
    if product_data is None:
        raise HTTPException(status_code=404, detail="Product not found or error occurred while scraping")
    
    return product_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 