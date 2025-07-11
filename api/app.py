
from flask import Flask, request
import requests
import logging
import time
from threading import Lock
import os
from dotenv import load_dotenv

load_dotenv()
print("Current working directory:", os.getcwd())
print("Env vars after load_dotenv:", os.environ.get("BITRIX24_WEBHOOK_URL"))

app = Flask(__name__)

# Get Bitrix24 URL from environment variable
BITRIX24_WEBHOOK_URL = os.getenv("BITRIX24_WEBHOOK_URL")
if not BITRIX24_WEBHOOK_URL:
    raise ValueError("BITRIX24_WEBHOOK_URL not set in environment variables")

# Set up logging (file-based locally, stdout on Vercel)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Mapping for the Graphics Kit Collection
FIELD_MAPPING = {
    "bike model": "UF_CRM_1742489085",
    "bike year": "UF_CRM_1742489103",
    "rider number": "UF_CRM_1742489121",
    "rider name": "UF_CRM_1742832390",
    "background colour": "UF_CRM_1742832460",
    "number/name colour": "UF_CRM_1742832499",
    "number outline colour": "UF_CRM_1742832564",
    "select font style": "UF_CRM_1742832637",
    "want clear swingarms?": "UF_CRM_1742832690",
    "add upperforks/miniplates": "UF_CRM_1742832740",
    "add miniplates": "UF_CRM_1742832824",
    "add upper forks stickers": "UF_CRM_1742833157",
    "add plastic kit & fitting": "UF_CRM_1742833192",
    "choose your plastic colour": "UF_CRM_1742833240",
    "want us to fit your graphics to plastics": "UF_CRM_1742833298",
    "add a second set": "UF_CRM_1742833405",
    "additional comments": "UF_CRM_1742835224",
}

# Mapping for the Background Collection
BACKGROUND_FIELD_MAPPING = {
    "bike model": "UF_CRM_1743064150",
    "bike year": "UF_CRM_1743064240",
    "number": "UF_CRM_1743064259",
    "name": "UF_CRM_1743064287",
    "background colour": "UF_CRM_1743064308",
    "number/name colour": "UF_CRM_1743064327",
    "number outline colour": "UF_CRM_1743064351",
    "select font style": "UF_CRM_1743064369",
    "additional comments": "UF_CRM_1743064390",
    "add a free design proof": "UF_CRM_1743064487",
    "add plastic": "UF_CRM_1743064506",
    "want us to fit your graphics to plastics": "UF_CRM_1743064530",
}

# Mapping for Individual Graphics Collection
INDIVIDUAL_GRAPHICS_FIELD_MAPPING = {
    "bike model": "UF_CRM_1743860304",
    "bike year": "UF_CRM_1743860338"
}

# Valid Bitrix24 currency codes (based on Postman test)
VALID_CURRENCIES = 'USD'  # Update based on Bitrix24 settings

# Thread lock to prevent race conditions
lock = Lock()

# Add a health check endpoint for browser access
@app.route('/', methods=['GET'])
def health_check():
    return "Flask app is running! This app is designed to handle Shopify webhooks at /webhook (POST requests only).", 200

@app.route('/webhook', methods=['POST'])
def shopify_webhook():
    try:
        # Log webhook headers for debugging
        logging.info(f"Received webhook with headers: {dict(request.headers)}")
        topic = request.headers.get('X-Shopify-Topic', 'unknown')
        print(f"Webhook topic: {topic}")
        logging.info(f"Webhook topic: {topic}")
        if topic != 'orders/create':
            print(f"Ignoring non-create webhook: {topic}")
            logging.info(f"Ignoring non-create webhook: {topic}")
            return '', 200

        receipt_time = time.time()
        print(f"Webhook received at {receipt_time}")
        logging.info(f"Webhook received at {receipt_time}")

        try:
            data = request.json
            if data is None:
                print("Error: Invalid JSON payload received")
                logging.error("Invalid JSON payload received")
                return "Invalid JSON payload", 400
        except ValueError as e:
            print(f"Error: Failed to parse JSON payload: {e}")
            logging.error("Failed to parse JSON payload: %s", e)
            return f"Failed to parse JSON payload: {str(e)}", 400

        print("Full Shopify Webhook Payload:", data)
        logging.info(f"Received Shopify webhook payload: {data}")

        order_id = data.get('id', 'Unknown Order ID')
        if order_id == 'Unknown Order ID':
            print("Error: 'id' key missing in Shopify payload")
            logging.error("'id' key missing in Shopify payload: %s", data)
            return "Invalid Shopify payload: 'id' key missing", 400

        order_title = data.get('name', 'Unknown Order Title')
        print(f"Order Title: {order_title}")
        logging.info(f"Order Title for order {order_id}: {order_title}")

        email = data.get('email', 'No email provided')
        customer = data.get('customer', {})
        first_name = customer.get('first_name', 'Unknown')
        last_name = customer.get('last_name', 'Unknown')

        shipping_address = data.get('shipping_address', {})
        address_name = shipping_address.get('address1', 'No address provided')
        address2 = shipping_address.get('address2', '')
        city = shipping_address.get('city', '')
        country = shipping_address.get('country', '')
        postal_code = shipping_address.get('zip', '')
        full_address = f"{address_name}, {address2}, {city}, {country}, {postal_code}".strip(', ')
        print(f"Shipping Address: {full_address}")
        logging.info(f"Shipping Address for order {order_id}: {full_address}")

        # Extract and validate currency
        try:
            total_price = float(data.get('total_price', '0.00'))
        except (ValueError, TypeError):
            print(f"Warning: Invalid total_price value: {data.get('total_price')}. Defaulting to 0.00.")
            logging.warning(f"Invalid total_price value for order {order_id}: {data.get('total_price')}. Defaulting to 0.00.")
            total_price = 0.00
        currency = data.get('currency', 'USD').upper()
        print(f"Extracted currency for order {order_id}: {currency}")
        logging.info(f"Extracted currency for order {order_id}: {currency}")
        if currency not in VALID_CURRENCIES:
            print(f"Warning: Unsupported currency '{currency}' for order {order_id}. Defaulting to USD.")
            logging.warning(f"Unsupported currency '{currency}' for order {order_id}. Defaulting to USD.")
            currency = 'USD'
        print(f"Order Total Price: {total_price} {currency}")
        logging.info(f"Order Total Price for order {order_id}: {total_price} {currency}")

        # Prepare the Bitrix24 payload
        bitrix_payload = {
            "fields": {
                "TITLE": f"Custom Solution-{order_title}",
                "NAME": first_name,
                "LAST_NAME": last_name,
                "EMAIL": [{"VALUE": email, "VALUE_TYPE": "WORK"}],
                "SOURCE_ID": "STORE",
                "OPPORTUNITY": total_price,
                "CURRENCY_ID": currency,
                "ADDRESS": full_address,
                "ADDRESS_2": address2,
                "ADDRESS_CITY": city,
                "ADDRESS_COUNTRY": country,
                "ADDRESS_POSTAL_CODE": postal_code,
                "UF_CRM_FACTORYMOTO62": str(order_id)
            }
        }

        # Process each line item to determine its collection and map fields
        collections_used = set()
        product_details = []
        for item in data.get('line_items', []):
            product_name = item.get('name', '').lower()
            product_title = item.get('title', 'Unknown Product')
            variant_title = item.get('variant_title', '')
            quantity = item.get('quantity', 1)

            # Collect product details for UF_CRM_1744466600
            product_info = f"Product: {product_title}"
            if variant_title and variant_title.lower() != 'default title':
                product_info += f" ({variant_title})"
            product_info += f", Quantity: {quantity}"
            product_details.append(product_info)
            print(f"Collected product detail: {product_info}")
            logging.info(f"Collected product detail for order {order_id}: {product_info}")

            # Determine the collection based on product name
            if "graphics kit" in product_name:
                collection_name = "Graphics Kit"
                field_mapping = FIELD_MAPPING
            elif "background" in product_name:
                collection_name = "Background"
                field_mapping = BACKGROUND_FIELD_MAPPING
            elif "graphics" in product_name and "kit" not in product_name:
                collection_name = "Individual Graphics"
                field_mapping = INDIVIDUAL_GRAPHICS_FIELD_MAPPING
            else:
                collection_name = "Uncategorized"
                field_mapping = None

            if collection_name != "Uncategorized":
                collections_used.add(collection_name)

            if field_mapping:
                print(f"Processing line item: {product_name} (Collection: {collection_name})")
                logging.info(f"Processing line item for order {order_id}: {product_name} (Collection: {collection_name})")
                print("Custom Fields from Shopify (Raw):", [(prop.get('name'), prop.get('value')) for prop in item.get('properties', [])])
                logging.info(f"Custom Fields from Shopify (Raw) for {product_name}: %s", [(prop.get('name'), prop.get('value')) for prop in item.get('properties', [])])
                custom_fields = {}
                for prop in item.get('properties', []):
                    field_name = prop.get('name', '').lstrip('_').replace('_', ' ').strip().lower()
                    field_value = prop.get('value')
                    if field_name and field_value and not field_name.startswith('__'):
                        custom_fields[field_name] = field_value
                print(f"Custom Fields after Normalization for {product_name}:", custom_fields)
                logging.info(f"Custom Fields after Normalization for {product_name}: %s", custom_fields)

                # Map non-file custom fields
                for shopify_field, value in custom_fields.items():
                    if shopify_field in field_mapping:
                        bitrix_field = field_mapping[shopify_field]
                        bitrix_payload["fields"][bitrix_field] = value
                    else:
                        print(f"Warning: Shopify field '{shopify_field}' not mapped to Bitrix24 for {collection_name} collection. Skipping.")
                        logging.warning(f"Shopify field '{shopify_field}' not mapped to Bitrix24 for {collection_name} collection in order {order_id}")

        # Store product details in UF_CRM_1744466600
        bitrix_payload["fields"]["UF_CRM_1744466600"] = product_details or ["No products found"]
        print(f"Stored product details in UF_CRM_1744466600: {product_details}")
        logging.info(f"Stored product details in UF_CRM_1744466600 for order {order_id}: {product_details}")

        # Finalize COMMENTS
        collections_comment = f"Collections in this order: {', '.join(collections_used)}"
        bitrix_payload["fields"]["COMMENTS"] = collections_comment
        print(f"Set COMMENTS to: {collections_comment}")
        logging.info(f"Set COMMENTS for order {order_id}: {collections_comment}")

        # Debug: Print the Bitrix24 payload
        print("Bitrix24 Payload:", bitrix_payload)
        logging.info("Bitrix24 Payload for order %s: %s", order_id, bitrix_payload)

        # Synchronize to prevent race conditions
        with lock:
            # Check if a lead already exists for this order ID
            check_payload = {
                "filter": {"UF_CRM_FACTORYMOTO62": str(order_id)},
                "select": ["ID"]
            }
            check_url = BITRIX24_WEBHOOK_URL + "crm.lead.list"
            check_response = requests.post(check_url, json=check_payload)
            logging.info(f"crm.lead.list response for order {order_id}: Status {check_response.status_code}, Body {check_response.text}")
            check_response.raise_for_status()
            existing_leads = check_response.json().get('result', [])
            print(f"Existing leads for order {order_id}: {existing_leads}")
            logging.info(f"Existing leads for order {order_id}: {existing_leads}")

            # Decide whether to create or update the lead
            if existing_leads:
                lead_id = existing_leads[0]['ID']
                print(f"Lead already exists for order {order_id}. Updating lead ID {lead_id}...")
                logging.info(f"Lead already exists for order {order_id}. Updating lead ID {lead_id}")
                update_url = BITRIX24_WEBHOOK_URL + "crm.lead.update"
                update_payload = {
                    "id": lead_id,
                    "fields": bitrix_payload["fields"]
                }
                logging.info(f"Sending update payload for lead {lead_id}: {update_payload}")
                response = requests.post(update_url, json=update_payload)
                logging.info(f"crm.lead.update response for lead {lead_id}: Status {response.status_code}, Body {response.text}")
                response.raise_for_status()
                print(f"Successfully updated lead {lead_id} in Bitrix24: {response.json()}")
                logging.info(f"Payload for order {order_id} successfully updated lead {lead_id} in Bitrix24: {response.json()}")
            else:
                print(f"Creating new lead for order {order_id}...")
                logging.info(f"Creating new lead for order {order_id}")
                create_url = BITRIX24_WEBHOOK_URL + "crm.lead.add"
                logging.info(f"Sending create payload for order {order_id}: {bitrix_payload}")
                response = requests.post(create_url, json=bitrix_payload)
                logging.info(f"crm.lead.add response for order {order_id}: Status {response.status_code}, Body {response.text}")
                response.raise_for_status()
                lead_id = response.json().get('result')
                print(f"Successfully created lead {lead_id} in Bitrix24: {response.json()}")
                logging.info(f"Payload for order {order_id} successfully created lead {lead_id} in Bitrix24: {response.json()}")

        return '', 200

    except requests.exceptions.RequestException as e:
        error_message = f"Failed to process payload for order {order_id} to Bitrix24: {e}"
        print(error_message)
        logging.error(error_message, exc_info=True)
        if hasattr(e, 'response') and e.response is not None:
            error_response = f"Bitrix24 Response: {e.response.status_code} - {e.response.text}"
            print(error_response)
            logging.error(error_response)
        return f"Failed to send data to Bitrix24: {str(e)}", 500
    except Exception as e:
        error_message = f"Error processing webhook for order {order_id}: {e}"
        print(error_message)
        logging.error(error_message, exc_info=True)
        return f"Error processing webhook: {str(e)}", 500

if __name__ == '__main__':
    print("Starting Flask app on http://127.0.0.1:5000")
    app.run(port=5000, debug=True)