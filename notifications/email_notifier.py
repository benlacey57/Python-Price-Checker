import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime

from core.interfaces import NotifierInterface
from core.models import Product


class EmailNotifier(NotifierInterface):
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str, sender: str, recipients: List[str]):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender
        self.recipients = recipients
    
    def _send_email(self, subject: str, html_content: str) -> bool:
        """Send an email with HTML content."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def notify_price_change(self, product: Product, price_change: Dict[str, Any]) -> bool:
        """Send notification about price change."""
        if not price_change['has_changed']:
            return False
        
        # Format price change
        percentage = round(price_change['percentage'], 2)
        absolute = price_change['absolute']
        direction = "decreased" if absolute < 0 else "increased"
        
        # Create email content
        subject = f"Price {direction} for {product.title}"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .price-change {{ font-weight: bold; color: {'green' if absolute < 0 else 'red'}; }}
                .product-image {{ max-width: 200px; }}
                .details {{ margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h2>Price Change Alert</h2>
            <p>The price of <strong>{product.title}</strong> has {direction}:</p>
            
            <div class="price-change">
                <p>Previous price: {price_change['currency']} {abs(price_change['previous'])}</p>
                <p>Current price: {price_change['currency']} {abs(price_change['current'])}</p>
                <p>Change: {price_change['currency']} {abs(price_change['absolute'])} ({percentage}%)</p>
            </div>
            
            <div class="details">
                <p><strong>ASIN:</strong> {product.asin}</p>
                <p><strong>Category:</strong> {product.category}</p>
                <p><a href="{product.url}">View on Amazon</a></p>
            </div>
            
            {f'<img class="product-image" src="{product.images[0].url}" alt="{product.title}" />' if product.images else ''}
        </body>
        </html>
        """
        
        return self._send_email(subject, html_content)
    
    def send_summary(self, products: List[Product]) -> bool:
        """Send a summary of tracked products and their prices."""
        if not products:
            return False
        
        # Create email content
        subject = f"Amazon Price Tracker - Summary of {len(products)} Products"
        
        products_html = ""
        for product in products:
            current_price = product.current_price()
            price_info = f"{current_price.currency} {current_price.price}" if current_price else "N/A"
            
            price_change = product.price_change()
            change_html = ""
            if price_change['has_changed']:
                direction = "▼" if price_change['absolute'] < 0 else "▲"
                percentage = round(price_change['percentage'], 2)
                change_html = f'<span style="color: {"green" if price_change["absolute"] < 0 else "red"}">({direction} {abs(percentage)}%)</span>'
            
            products_html += f"""
            <tr>
                <td>{product.title}</td>
                <td>{product.category}</td>
                <td>{price_info} {change_html}</td>
                <td><a href="{product.url}">View</a></td>
            </tr>
            """
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <h2>Amazon Price Tracker Summary</h2>
            <p>Here's a summary of the {len(products)} products you're tracking:</p>
            
            <table>
                <tr>
                    <th>Product</th>
                    <th>Category</th>
                    <th>Current Price</th>
                    <th>Link</th>
                </tr>
                {products_html}
            </table>
            
            <p>This summary was generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body>
        </html>
        """
        
        return self._send_email(subject, html_content)