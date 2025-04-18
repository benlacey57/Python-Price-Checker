import argparse
import logging
import sys
from datetime import datetime, timedelta
import configparser
import os
from typing import List, Dict

from core.models import Product, PricePoint
from scrapers.amazon_scraper import AmazonScraper
from storage.sqlite_storage import SQLiteStorage
from notifications.email_notifier import EmailNotifier
from notifications.slack_notifier import SlackNotifier


def load_config(config_path: str = 'config.ini') -> Dict:
    """Load configuration from file."""
    config = configparser.ConfigParser()
    
    if os.path.exists(config_path):
        config.read(config_path)
    else:
        # Create default config
        config['DEFAULT'] = {
            'DatabasePath': 'amazon_tracker.db',
            'CacheExpiry': '3600',  # 1 hour
            'NotificationThreshold': '5.0',  # 5% price change
        }
        
        config['Email'] = {
            'SMTPServer': 'smtp.gmail.com',
            'SMTPPort': '587',
            'Username': 'your_email@gmail.com',
            'Password': '',
            'Sender': 'Amazon Price Tracker <your_email@gmail.com>',
            'Recipients': 'your_email@gmail.com',
        }

        config['Slack'] = {
            'WebhookUrl': '',
            'Channel': '#amazon-price-alerts',
            'Username': 'Amazon Price Tracker',
        }
        
        # Save default config
        with open(config_path, 'w') as config_file:
            config.write(config_file)
    
    return config


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('amazon_tracker.log')
        ]
    )
    return logging.getLogger('amazon_tracker')


def create_notifier(config):
    """Create notifier based on configuration."""
    notifiers = []
    
    # Set up email notifier if configured
    if config.has_section('Email') and config['Email'].get('Password'):
        email_notifier = EmailNotifier(
            smtp_server=config['Email']['SMTPServer'],
            smtp_port=int(config['Email']['SMTPPort']),
            username=config['Email']['Username'],
            password=config['Email']['Password'],
            sender=config['Email']['Sender'],
            recipients=config['Email']['Recipients'].split(',')
        )
        notifiers.append(email_notifier)
    
    # Set up Slack notifier if configured
    if config.has_section('Slack') and config['Slack'].get('WebhookURL'):
        slack_notifier = SlackNotifier(
            webhook_url=config['Slack']['WebhookURL'],
            channel=config['Slack']['Channel'],
            username=config['Slack']['Username']
        )
        notifiers.append(slack_notifier)
    
    return notifiers


def update_product(asin_or_url, storage, scraper, notifiers, threshold=5.0):
    """Update product information and notify if price changed."""
    logger = logging.getLogger('amazon_tracker')
    
    # Determine if input is ASIN or URL
    if asin_or_url.startswith('http'):
        url = asin_or_url
        asin = scraper.extract_asin(url)
        if not asin:
            logger.error(f"Could not extract ASIN from URL: {url}")
            return None
    else:
        asin = asin_or_url
        url = f"https://www.amazon.com/dp/{asin}"
    
    # Get existing product
    existing_product = storage.get_product(asin)
    
    # Scrape current product data
    product = scraper.scrape_product(url)
    if not product:
        logger.error(f"Failed to scrape product: {url}")
        return None
    
    # Determine if price has changed
    price_changed = False
    price_change = None
    
    if existing_product:
        # Copy existing price history
        product.price_history = existing_product.price_history + product.price_history
        price_change = product.price_change()
        
        # Only consider it changed if above threshold
        if price_change['has_changed'] and abs(price_change['percentage']) >= threshold:
            price_changed = True
    
    # Save updated product
    if storage.save_product(product):
        logger.info(f"Successfully updated product: {product.title}")
        
        # Send notifications if price changed
        if price_changed and notifiers:
            for notifier in notifiers:
                if notifier.notify_price_change(product, price_change):
                    logger.info(f"Sent price change notification for {product.title}")
    
    return product


def main():
    """Main application entry point."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Amazon Price Tracker')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Add command: track product
    track_parser = subparsers.add_parser('track', help='Track a product')
    track_parser.add_argument('url', help='Amazon product URL or ASIN')
    
    # Add command: list products
    list_parser = subparsers.add_parser('list', help='List tracked products')
    list_parser.add_argument('--category', help='Filter by category')
    
    # Add command: update all
    update_parser = subparsers.add_parser('update', help='Update all tracked products')
    
    # Add command: summary
    summary_parser = subparsers.add_parser('summary', help='Send summary of all tracked products')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    
    # Load configuration
    config = load_config()
    
    # Initialize components
    storage = SQLiteStorage(config['DEFAULT']['DatabasePath'])
    scraper = AmazonScraper(int(config['DEFAULT']['CacheExpiry']))
    notifiers = create_notifier(config)
    threshold = float(config['DEFAULT']['NotificationThreshold'])
    
    # Execute command
    if args.command == 'track':
        product = update_product(args.url, storage, scraper, notifiers, threshold)
        if product:
            logger.info(f"Now tracking: {product.title} (ASIN: {product.asin})")
    
    elif args.command == 'list':
        products = storage.list_products(args.category)
        if products:
            print(f"Tracking {len(products)} products:")
            for product in products:
                current_price = product.current_price()
                price_info = f"{current_price.currency} {current_price.price}" if current_price else "N/A"
                print(f"- {product.title} ({product.asin}) - {price_info}")
        else:
            print("No products being tracked.")
    
    elif args.command == 'update':
        products = storage.list_products()
        if products:
            print(f"Updating {len(products)} products...")
            for product in products:
                update_product(product.asin, storage, scraper, notifiers, threshold)
            print("Update complete.")
        else:
            print("No products to update.")
    
    elif args.command == 'summary':
        products = storage.list_products()
        if products and notifiers:
            for notifier in notifiers:
                if notifier.send_summary(products):
                    logger.info(f"Sent summary of {len(products)} products")
            print(f"Summary of {len(products)} products sent.")
        else:
            print("No products to summarize or no notifiers configured.")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()