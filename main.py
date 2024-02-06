import requests
from bs4 import BeautifulSoup
import pandas as pd
from termcolor import colored
import time
from datetime import datetime

def fetch_amazon_details(url, name):
    headers = {
       'User-Agent': 'Mozilla/5.0'
    }
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            current_price = soup.select_one('#priceblock_ourprice').get_text().strip().replace('$', '') if soup.select_one('#priceblock_ourprice') else 0.00

            # Initialise sale_price and previous_price with default value 0.00
            sale_price = current_price
            previous_price = 0.00

            # Calculate the difference and percent change
            difference = 0.00
            percent_change = 0.00
            print(f"{timestamp} [INFO] [200]: Success: {name[:30]} | Current Price: ${current_price}")
            return {'timestamp': timestamp, 'source': 'Amazon', 'name': name, 'current_price': current_price, 'sale_price': sale_price, 'previous_price': previous_price, 'difference': difference, 'percent_change': percent_change, 'url': url}
        else:
            print(f"{timestamp} [ERROR] [{response.status_code}]: Error fetching product: {name[:30]}")
            return None

    except Exception as e:
        print(f"{timestamp} [ERROR] [EXCEPTION]: Error fetching product: {name[:30]} | Exception: {str(e)}")
        return None

# Initialise an empty DataFrame with new columns including timestamp
columns = ['timestamp', 'source', 'name', 'current_price', 'sale_price', 'previous_price', 'difference', 'percent_change', 'url']
product_df = pd.DataFrame(columns=columns)

# Updated product data list
product_data = [
    {'name': 'Antank Switch TV Dock - Portable Docking Station Compatible with Nintendo Switch/Switch OLED with 4K/1080P HDMI USB 3.0 Port for Desktop and TV', 'url': 'https://amzn.eu/d/grFDKDv'},
    {'name': 'JoyHood Case for Switch & Switch OLED, Deluxe Protective Hard Shell Carry Bag, Travel Carrying Case with Storage for Switch Console & Accessories', 'url': 'https://amzn.eu/d/7MehY2r'},
    {'name': 'Orzly Glass Screen Protectors compatible with Nintendo Switch Premium Tempered Glass Screen Protector TWIN PACK [2x Screen Guards - 0.24mm] for Nintendo Switch', 'url': 'https://amzn.eu/d/geBmnZ7'},
    {'name': 'Hogwarts Legacy Nintendo Switch', 'url': 'https://amzn.eu/d/9wLyAND'},
    {'name': 'Silicon Power 1TB Superior Micro SDXC UHS-I (U3), V30 4K A2,High Speed MicroSD Card, Compatible with Nintendo-Switch', 'url': 'https://amzn.eu/d/f0QJcrl'}
]

for product in product_data:
    details = fetch_amazon_details(product['url'], product['name'])

    if details:
        new_row_df = pd.DataFrame([details])
        product_df = pd.concat([product_df, new_row_df], ignore_index=True)

    time.sleep(1)  # Respectful delay between requests

# Display or save the DataFrame
# print(product_df)

# Save the DataFrame to a CSV file
product_df.to_csv('product_price_checker.csv', index=False)
