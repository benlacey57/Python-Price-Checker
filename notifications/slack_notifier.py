import json
import requests
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime

from core.interfaces import NotifierInterface
from core.models import Product


class SlackNotifier(NotifierInterface):
    def __init__(self, webhook_url: str, channel: str = "#amazon-price-alerts", username: str = "Amazon Price Tracker"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
    
    def _send_slack_message(self, blocks: List[Dict]) -> bool:
        """Send a message to Slack using blocks."""
        try:
            payload = {
                "channel": self.channel,
                "username": self.username,
                "blocks": blocks
            }
            
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                print(f"Error sending Slack message: {response.status_code} {response.text}")
                return False
            
            return True
        except Exception as e:
            print(f"Error sending Slack message: {e}")
            return False
    
    def notify_price_change(self, product: Product, price_change: Dict[str, Any]) -> bool:
        """Send notification about price change to Slack."""
        if not price_change['has_changed']:
            return False
        
        # Format price change
        percentage = round(price_change['percentage'], 2)
        absolute = price_change['absolute']
        direction = "decreased" if absolute < 0 else "increased"
        
        # Create emoji based on direction
        emoji = ":arrow_down:" if absolute < 0 else ":arrow_up:"
        
        # Create blocks for Slack message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Price {direction} for {product.title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Price Change {emoji}*\n"
                           f"Previous price: {price_change['currency']} {abs(price_change['previous'])}\n"
                           f"Current price: {price_change['currency']} {abs(price_change['current'])}\n"
                           f"Change: {price_change['currency']} {abs(price_change['absolute'])} ({percentage}%)"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*ASIN:*\n{product.asin}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:*\n{product.category}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View on Amazon",
                            "emoji": True
                        },
                        "url": product.url
                    }
                ]
            }
        ]
        
        # Add image if available
        if product.images:
            primary_image = next((img for img in product.images if img.is_primary), product.images[0])
            blocks.insert(1, {
                "type": "image",
                "image_url": primary_image.url,
                "alt_text": product.title
            })
        
        return self._send_slack_message(blocks)
    
    def send_summary(self, products: List[Product]) -> bool:
        """Send a summary of tracked products to Slack."""
        if not products:
            return False
        
        # Create blocks for Slack message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Amazon Price Tracker - Summary of {len(products)} Products",
                    "emoji": True
                }
            }
        ]
        
        # Group products by category
        categories = {}
        for product in products:
            if product.category not in categories:
                categories[product.category] = []
            categories[product.category].append(product)
        
        # Add each category
        for category, category_products in categories.items():
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{category}*"
                }
            })
            
            for product in category_products:
                current_price = product.current_price()
                price_info = f"{current_price.currency} {current_price.price}" if current_price else "N/A"
                
                price_change = product.price_change()
                change_text = ""
                if price_change['has_changed']:
                    direction = ":arrow_down:" if price_change['absolute'] < 0 else ":arrow_up:"
                    percentage = round(price_change['percentage'], 2)
                    change_text = f" {direction} {abs(percentage)}%"
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{product.url}|{product.title}>\n"
                               f"Price: {price_info}{change_text}"
                    }
                })
        
        return self._send_slack_message(blocks)