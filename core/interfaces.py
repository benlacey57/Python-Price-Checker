from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import Product, PricePoint


class StorageInterface(ABC):
    @abstractmethod
    def save_product(self, product: Product) -> bool:
        """Save product to storage."""
        pass
    
    @abstractmethod
    def get_product(self, asin: str) -> Optional[Product]:
        """Get product by ASIN."""
        pass
    
    @abstractmethod
    def list_products(self, category: Optional[str] = None) -> List[Product]:
        """List all products, optionally filtered by category."""
        pass
    
    @abstractmethod
    def add_price_point(self, asin: str, price_point: PricePoint) -> bool:
        """Add a price point to a product's history."""
        pass


class ScraperInterface(ABC):
    @abstractmethod
    def scrape_product(self, url: str) -> Product:
        """Scrape product information from URL."""
        pass
    
    @abstractmethod
    def scrape_category(self, category_url: str, max_products: int = 20) -> List[Product]:
        """Scrape products from a category page."""
        pass
    
    @abstractmethod
    def extract_table_data(self, soup) -> Dict[str, str]:
        """Extract key-value data from an HTML table."""
        pass


class NotifierInterface(ABC):
    @abstractmethod
    def notify_price_change(self, product: Product, price_change: Dict[str, Any]) -> bool:
        """Send notification about price change."""
        pass
    
    @abstractmethod
    def send_summary(self, products: List[Product]) -> bool:
        """Send a summary of tracked products and their prices."""
        pass