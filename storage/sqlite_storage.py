import sqlite3
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from core.interfaces import StorageInterface
from core.models import Product, PricePoint, ProductImage


class SQLiteStorage(StorageInterface):
    def __init__(self, db_path: str = "amazon_tracker.db"):
        self.db_path = db_path
        self._initialize_db()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _initialize_db(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Products table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT NOT NULL,
                brand TEXT,
                description TEXT,
                attributes TEXT
            )
            ''')
            
            # Product images
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT NOT NULL,
                url TEXT NOT NULL,
                is_primary INTEGER DEFAULT 0,
                FOREIGN KEY (asin) REFERENCES products (asin) ON DELETE CASCADE
            )
            ''')
            
            # Price history
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                timestamp TEXT NOT NULL,
                per_unit_price REAL,
                unit_measurement TEXT,
                FOREIGN KEY (asin) REFERENCES products (asin) ON DELETE CASCADE
            )
            ''')
            
            conn.commit()
    
    def save_product(self, product: Product) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Insert or update product
                cursor.execute('''
                INSERT OR REPLACE INTO products (asin, title, category, url, brand, description, attributes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product.asin,
                    product.title,
                    product.category,
                    product.url,
                    product.brand,
                    product.description,
                    json.dumps(product.attributes)
                ))
                
                # Handle images - delete old ones first
                cursor.execute('DELETE FROM product_images WHERE asin = ?', (product.asin,))
                for image in product.images:
                    cursor.execute('''
                    INSERT INTO product_images (asin, url, is_primary)
                    VALUES (?, ?, ?)
                    ''', (product.asin, image.url, 1 if image.is_primary else 0))
                
                # Add price points if they're new
                for price_point in product.price_history:
                    # Check if this exact price point exists
                    cursor.execute('''
                    SELECT id FROM price_history
                    WHERE asin = ? AND timestamp = ?
                    ''', (product.asin, price_point.timestamp.isoformat()))
                    
                    if cursor.fetchone() is None:
                        cursor.execute('''
                        INSERT INTO price_history 
                        (asin, price, currency, timestamp, per_unit_price, unit_measurement)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            product.asin,
                            float(price_point.price),
                            price_point.currency,
                            price_point.timestamp.isoformat(),
                            float(price_point.per_unit_price) if price_point.per_unit_price else None,
                            price_point.unit_measurement
                        ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving product: {e}")
            return False
    
    def get_product(self, asin: str) -> Optional[Product]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get product
                cursor.execute('SELECT * FROM products WHERE asin = ?', (asin,))
                product_row = cursor.fetchone()
                
                if not product_row:
                    return None
                
                # Get images
                cursor.execute('SELECT * FROM product_images WHERE asin = ?', (asin,))
                images = [ProductImage(
                    url=row['url'],
                    is_primary=bool(row['is_primary'])
                ) for row in cursor.fetchall()]
                
                # Get price history
                cursor.execute('SELECT * FROM price_history WHERE asin = ? ORDER BY timestamp', (asin,))
                price_history = [PricePoint(
                    price=Decimal(str(row['price'])),
                    currency=row['currency'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    per_unit_price=Decimal(str(row['per_unit_price'])) if row['per_unit_price'] else None,
                    unit_measurement=row['unit_measurement']
                ) for row in cursor.fetchall()]
                
                # Create product object
                product = Product(
                    asin=product_row['asin'],
                    title=product_row['title'],
                    category=product_row['category'],
                    url=product_row['url'],
                    brand=product_row['brand'],
                    description=product_row['description'],
                    attributes=json.loads(product_row['attributes']),
                    images=images,
                    price_history=price_history
                )
                
                return product
        except Exception as e:
            print(f"Error getting product: {e}")
            return None
    
    def list_products(self, category: Optional[str] = None) -> List[Product]:
        products = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if category:
                    cursor.execute('SELECT asin FROM products WHERE category = ?', (category,))
                else:
                    cursor.execute('SELECT asin FROM products')
                
                for row in cursor.fetchall():
                    product = self.get_product(row['asin'])
                    if product:
                        products.append(product)
                
                return products
        except Exception as e:
            print(f"Error listing products: {e}")
            return []
    
    def add_price_point(self, asin: str, price_point: PricePoint) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if product exists
                cursor.execute('SELECT asin FROM products WHERE asin = ?', (asin,))
                if not cursor.fetchone():
                    return False
                
                # Check if this exact price point exists
                cursor.execute('''
                SELECT id FROM price_history
                WHERE asin = ? AND timestamp = ?
                ''', (asin, price_point.timestamp.isoformat()))
                
                if cursor.fetchone() is None:
                    cursor.execute('''
                    INSERT INTO price_history 
                    (asin, price, currency, timestamp, per_unit_price, unit_measurement)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        asin,
                        float(price_point.price),
                        price_point.currency,
                        price_point.timestamp.isoformat(),
                        float(price_point.per_unit_price) if price_point.per_unit_price else None,
                        price_point.unit_measurement
                    ))
                    
                    conn.commit()
                return True
        except Exception as e:
            print(f"Error adding price point: {e}")
            return False