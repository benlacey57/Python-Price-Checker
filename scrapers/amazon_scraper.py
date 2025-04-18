import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any
import time
import random
from urllib.parse import urlparse, parse_qs

from core.interfaces import ScraperInterface
from core.models import Product, PricePoint, ProductImage


class AmazonScraper(ScraperInterface):
    def __init__(self, cache_expiry: int = 3600):
        """
        Initialize Amazon scraper
        
        Args:
            cache_expiry: Cache expiry time in seconds (default: 1 hour)
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.cache = {}
        self.cache_expiry = cache_expiry
    
    def _get_with_cache(self, url: str) -> Optional[BeautifulSoup]:
        """Get URL content with caching."""
        current_time = time.time()
        
        # Check cache
        if url in self.cache:
            cache_time, content = self.cache[url]
            if current_time - cache_time < self.cache_expiry:
                return content
        
        # Add jitter to avoid being detected as a bot
        time.sleep(random.uniform(1, 3))
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"Error fetching {url}: Status {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            self.cache[url] = (current_time, soup)
            return soup
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_asin(self, url: str) -> Optional[str]:
        """Extract ASIN from Amazon URL."""
        # Try to extract from URL path
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        
        # Handle dp/ASIN format
        if 'dp' in path_parts:
            idx = path_parts.index('dp')
            if idx + 1 < len(path_parts):
                return path_parts[idx + 1]
        
        # Handle /ASIN/product format
        for part in path_parts:
            if re.match(r'^[A-Z0-9]{10}$', part):
                return part
        
        # Check query parameters
        query_params = parse_qs(parsed_url.query)
        if 'ASIN' in query_params:
            return query_params['ASIN'][0]
        
        return None
    
    def extract_price(self, soup) -> Optional[PricePoint]:
        """Extract price from product page."""
        try:
            # Try different price selectors
            price_whole = soup.select_one('span.a-price-whole')
            price_fraction = soup.select_one('span.a-price-fraction')
            
            if price_whole and price_fraction:
                price_str = f"{price_whole.text.strip()}{price_fraction.text.strip()}"
                price_str = re.sub(r'[^\d.]', '', price_str)
                price = Decimal(price_str)
                
                # Try to find currency symbol
                currency_symbol = soup.select_one('span.a-price-symbol')
                currency = currency_symbol.text.strip() if currency_symbol else "USD"
                
                # Look for price per unit
                per_unit_elem = soup.select_one('span.a-size-small.a-color-price')
                per_unit_price = None
                unit_measurement = None
                
                if per_unit_elem and '/' in per_unit_elem.text:
                    per_unit_text = per_unit_elem.text.strip()
                    # Pattern like "$1.25 / 100g"
                    match = re.search(r'[\d,.]+\s*/\s*([^\s]+)', per_unit_text)
                    if match:
                        unit_measurement = match.group(1)
                        price_part = re.search(r'([\d,.]+)', per_unit_text)
                        if price_part:
                            per_unit_price = Decimal(price_part.group(1))
                
                return PricePoint(
                    price=price,
                    currency=currency,
                    timestamp=datetime.now(),
                    per_unit_price=per_unit_price,
                    unit_measurement=unit_measurement
                )
            
            return None
        except Exception as e:
            print(f"Error extracting price: {e}")
            return None
    
    def extract_images(self, soup) -> List[ProductImage]:
        """Extract product images."""
        images = []
        try:
            # Try to find image gallery
            img_gallery = soup.select('img.a-dynamic-image')
            
            if img_gallery:
                for i, img in enumerate(img_gallery):
                    if 'src' in img.attrs:
                        images.append(ProductImage(
                            url=img['src'],
                            is_primary=(i == 0)
                        ))
            
            # Fallback to main product image
            if not images:
                main_img = soup.select_one('#landingImage') or soup.select_one('#imgBlkFront')
                if main_img and 'src' in main_img.attrs:
                    images.append(ProductImage(
                        url=main_img['src'],
                        is_primary=True
                    ))
            
            return images
        except Exception as e:
            print(f"Error extracting images: {e}")
            return []
    
    def extract_table_data(self, soup) -> Dict[str, str]:
        """Extract key-value data from product detail tables."""
        table_data = {}
        try:
            # Product details table
            detail_rows = soup.select('table.a-keyvalue tr') or soup.select('div.a-section.a-spacing-small table tr')
            
            for row in detail_rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    key = cells[0].text.strip().rstrip(':')
                    value = cells[1].text.strip()
                    table_data[key] = value
            
            # Product information section
            info_rows = soup.select('div.a-section.a-spacing-small > div.a-row')
            for row in info_rows:
                label = row.select_one('span.a-text-bold')
                if label:
                    key = label.text.strip().rstrip(':')
                    value = row.text.replace(label.text, '').strip()
                    if key and value:
                        table_data[key] = value
            
            return table_data
        except Exception as e:
            print(f"Error extracting table data: {e}")
            return {}
    
    def scrape_product(self, url: str) -> Optional[Product]:
        """Scrape product information from Amazon URL."""
        try:
            soup = self._get_with_cache(url)
            if not soup:
                return None
            
            asin = self.extract_asin(url)
            if not asin:
                print("Could not extract ASIN from URL")
                return None
            
            # Extract basic product info
            title_elem = soup.select_one('#productTitle')
            title = title_elem.text.strip() if title_elem else "Unknown Title"
            
            # Extract brand
            brand_elem = soup.select_one('#bylineInfo') or soup.select_one('a#bylineInfo')
            brand = None
            if brand_elem:
                brand_text = brand_elem.text.strip()
                brand_match = re.search(r'by\s+(.+?)$', brand_text)
                brand = brand_match.group(1) if brand_match else brand_text
            
            # Extract category
            category = "Unknown"
            breadcrumbs = soup.select('#wayfinding-breadcrumbs_feature_div ul li')
            if breadcrumbs and len(breadcrumbs) > 0:
                # Use the last meaningful category
                for crumb in reversed(breadcrumbs):
                    text = crumb.text.strip()
                    if text and text != "›":
                        category = text
                        break
            
            # Extract description
            description_elem = soup.select_one('#productDescription')
            description = description_elem.text.strip() if description_elem else None
            
            # Extract price
            price_point = self.extract_price(soup)
            price_history = [price_point] if price_point else []
            
            # Extract images
            images = self.extract_images(soup)
            
            # Extract additional attributes
            attributes = self.extract_table_data(soup)
            
            return Product(
                asin=asin,
                title=title,
                category=category,
                url=url,
                brand=brand,
                description=description,
                images=images,
                price_history=price_history,
                attributes=attributes
            )
        except Exception as e:
            print(f"Error scraping product: {e}")
            return None
    
    def scrape_category(self, category_url: str, max_products: int = 20) -> List[Product]:
        """Scrape products from a category page."""
        products = []
        try:
            soup = self._get_with_cache(category_url)
            if not soup:
                return []
            
            # Find product links
            product_cards = soup.select('div.s-result-item[data-asin]')
            
            count = 0
            for card in product_cards:
                if count >= max_products:
                    break
                
                asin = card.get('data-asin')
                if not asin or len(asin) != 10:  # ASINs are 10 characters
                    continue
                
                link_elem = card.select_one('a.a-link-normal.s-no-outline')
                if not link_elem or 'href' not in link_elem.attrs:
                    continue
                
                product_url = f"https://www.amazon.com{link_elem['href']}" if link_elem['href'].startswith('/') else link_elem['href']
                
                # Scrape the product
                product = self.scrape_product(product_url)
                if product:
                    products.append(product)
                    count += 1
            
            return products
        except Exception as e:
            print(f"Error scraping category: {e}")
            return []