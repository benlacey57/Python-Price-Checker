from typing import List, Dict, Any, Optional
from decimal import Decimal
import re

from core.models import Product


class ProductComparison:
    """Utility class for comparing products."""
    
    @staticmethod
    def normalize_unit(unit_measurement: str) -> tuple:
        """Normalize unit measurement to standard form.
        
        Returns:
            tuple: (value, unit) - e.g., (100, 'g')
        """
        if not unit_measurement:
            return (1, 'item')
        
        # Extract numeric value and unit
        match = re.match(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', unit_measurement)
        if not match:
            return (1, unit_measurement)
        
        value = float(match.group(1))
        unit = match.group(2).lower()
        
        # Normalize units
        # Weight
        if unit in ('g', 'gram', 'grams'):
            return (value, 'g')
        elif unit in ('kg', 'kilo', 'kilos', 'kilogram', 'kilograms'):
            return (value * 1000, 'g')
        elif unit in ('oz', 'ounce', 'ounces'):
            return (value * 28.35, 'g')
        elif unit in ('lb', 'lbs', 'pound', 'pounds'):
            return (value * 453.59, 'g')
        
        # Volume
        elif unit in ('ml', 'milliliter', 'milliliters'):
            return (value, 'ml')
        elif unit in ('l', 'liter', 'liters'):
            return (value * 1000, 'ml')
        elif unit in ('fl oz', 'fluid ounce', 'fluid ounces'):
            return (value * 29.57, 'ml')
        
        # Length
        elif unit in ('cm', 'centimeter', 'centimeters'):
            return (value, 'cm')
        elif unit in ('m', 'meter', 'meters'):
            return (value * 100, 'cm')
        elif unit in ('in', 'inch', 'inches'):
            return (value * 2.54, 'cm')
        
        # Default
        return (value, unit)
    
    @staticmethod
    def calculate_unit_price(product: Product) -> Optional[Dict[str, Any]]:
        """Calculate unit price for a product."""
        current_price = product.current_price()
        if not current_price:
            return None
        
        # Use existing per unit price if available
        if current_price.per_unit_price and current_price.unit_measurement:
            normalized_unit = ProductComparison.normalize_unit(current_price.unit_measurement)
            return {
                'price': current_price.per_unit_price,
                'unit_value': normalized_unit[0],
                'unit': normalized_unit[1],
                'original_unit': current_price.unit_measurement,
                'currency': current_price.currency
            }
        
        # Try to extract from attributes
        unit_keys = ['size', 'weight', 'quantity', 'volume', 'dimensions']
        for key in unit_keys:
            if key in product.attributes:
                # Try to extract a numeric value and unit
                value = product.attributes[key]
                match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', value)
                if match:
                    quantity = float(match.group(1))
                    unit = match.group(2)
                    normalized = ProductComparison.normalize_unit(f"{quantity} {unit}")
                    
                    if normalized[0] > 0:
                        unit_price = float(current_price.price) / normalized[0]
                        return {
                            'price': Decimal(str(unit_price)),
                            'unit_value': normalized[0],
                            'unit': normalized[1],
                            'original_unit': f"{quantity} {unit}",
                            'currency': current_price.currency
                        }
        
        # Default to price per item
        return {
            'price': current_price.price,
            'unit_value': 1,
            'unit': 'item',
            'original_unit': 'each',
            'currency': current_price.currency
        }
    
    @staticmethod
    def compare_products(products: List[Product], target_unit: str = None) -> List[Dict[str, Any]]:
        """Compare products and calculate unit prices."""
        result = []
        
        # Calculate unit prices for all products
        for product in products:
            unit_price_info = ProductComparison.calculate_unit_price(product)
            if not unit_price_info:
                continue
            
            current_price = product.current_price()
            
            result.append({
                'product': product,
                'unit_price_info': unit_price_info,
                'total_price': current_price.price if current_price else None,
                'currency': current_price.currency if current_price else None
            })
        
        # If target unit is specified, convert all prices to that unit
        if target_unit and result:
            # Find unit conversion factors
            units = set(item['unit_price_info']['unit'] for item in result)
            
            # For now, only support comparison within same unit type
            if len(units) == 1 and list(units)[0] == target_unit:
                # Sort by unit price
                return sorted(result, key=lambda x: float(x['unit_price_info']['price']))
        
        # Default sorting by total price
        return sorted(result, key=lambda x: float(x['total_price']) if x['total_price'] else float('inf'))
    
    @staticmethod
    def generate_comparison_table(products: List[Product], target_unit: str = None) -> str:
        """Generate an HTML comparison table for products."""
        comparison = ProductComparison.compare_products(products, target_unit)
        
        html = """
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Brand</th>
                    <th>Price</th>
                    <th>Unit Price</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for item in comparison:
            product = item['product']
            unit_price_info = item['unit_price_info']
            total_price = item['total_price']
            
            html += f"""
            <tr>
                <td>{product.title}</td>
                <td>{product.brand or 'N/A'}</td>
                <td>{item['currency']} {total_price}</td>
                <td>{item['currency']} {unit_price_info['price']} per {unit_price_info['original_unit']}</td>
            </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
        
        return html