from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal
import uuid


@dataclass
class ProductImage:
    url: str
    is_primary: bool = False


@dataclass
class PricePoint:
    price: Decimal
    timestamp: datetime
    currency: str = "USD"
    per_unit_price: Optional[Decimal] = None
    unit_measurement: Optional[str] = None  # e.g., "100g", "each", etc.


@dataclass
class Product:
    asin: str
    title: str
    category: str
    url: str
    brand: Optional[str] = None
    description: Optional[str] = None
    images: List[ProductImage] = None
    price_history: List[PricePoint] = None
    attributes: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.price_history is None:
            self.price_history = []
        if self.attributes is None:
            self.attributes = {}
    
    def add_price_point(self, price_point: PricePoint) -> None:
        self.price_history.append(price_point)
    
    def current_price(self) -> Optional[PricePoint]:
        if not self.price_history:
            return None
        return sorted(self.price_history, key=lambda p: p.timestamp, reverse=True)[0]
    
    def price_change(self) -> Dict[str, Any]:
        """Calculate price change metrics compared to previous records."""
        if len(self.price_history) < 2:
            return {"percentage": 0, "absolute": Decimal('0'), "has_changed": False}
            
        sorted_history = sorted(self.price_history, key=lambda p: p.timestamp)
        current = sorted_history[-1].price
        previous = sorted_history[-2].price
        
        if previous == 0:
            percentage = 0
        else:
            percentage = ((current - previous) / previous) * 100
            
        return {
            "percentage": percentage,
            "absolute": current - previous,
            "has_changed": current != previous,
            "current": current,
            "previous": previous,
            "currency": sorted_history[-1].currency
        }