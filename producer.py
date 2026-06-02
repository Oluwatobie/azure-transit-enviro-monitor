import os
import json
import requests
import urllib3  
from datetime import datetime
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential

# --- Disable SSL warnings (for local testing behind firewalls) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# The Huxley2 API for Leicester (Station Code: LEI)
TRAIN_API_URL = "https://huxley2.azurewebsites.net/departures/LEI"
QUEUE_NAME = "leicester-trains"

# We grab the Service Bus URL that Terraform injected into our environment
FULLY_QUALIFIED_NAMESPACE = os.environ.get("SERVICE_BUS_NAMESPACE") 

def fetch_live_trains():
    """Calls the free UK Rail API for Leicester departures"""
    print(f"Fetching live departures for Leicester (LEI)...")
    
    # --- ADDED verify=False HERE ---
    response = requests.get(TRAIN_API_URL, verify=False)
    
    if response.status_code == 200:
        return response.json().get('trainServices', [])
    else:
        print(f"Error fetching data: {response.status_code}")
        return []

def send_to_queue(train_list):
    """Securely pushes the train data into the Azure Service Bus Queue"""
    if not FULLY_QUALIFIED_NAMESPACE:
        print("❌ Error: SERVICE_BUS_NAMESPACE environment variable not set.")
        return

    # THE MAGIC: DefaultAzureCredential automatically finds your login tokens.
    # NO PASSWORDS OR CONNECTION STRINGS NEEDED!
    credential = DefaultAzureCredential()

    print(f"Connecting to Service Bus securely: {FULLY_QUALIFIED_NAMESPACE}")
    
    # Create the client
    with ServiceBusClient(FULLY_QUALIFIED_NAMESPACE, credential=credential) as client:
        # Connect to our specific queue
        with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            
            messages_sent = 0
            for train in train_list:
                # 1. Format the data into a NoSQL-friendly JSON document
                document = {
                    "id": f"{train['std']}-{train['rsid']}", # Unique ID for Cosmos DB
                    "type": "train_departure",
                    "timestamp": datetime.utcnow().isoformat(),
                    "destination": train.get('destination', [{'locationName': 'Unknown'}])[0]['locationName'],
                    "scheduled_departure": train.get('std'),
                    "estimated_departure": train.get('etd'),
                    "platform": train.get('platform', 'TBC'),
                    "operator": train.get('operator'),
                    "is_cancelled": train.get('isCancelled', False)
                }

                # 2. Package it as a Service Bus Message
                message = ServiceBusMessage(json.dumps(document))
                
                # 3. Fire it into the queue
                sender.send_messages(message)
                messages_sent += 1
                
            print(f"✅ Successfully pushed {messages_sent} train updates to the Service Bus Queue!")

if __name__ == "__main__":
    trains = fetch_live_trains()
    
    if trains:
        send_to_queue(trains)
    else:
        print("No trains found or API error.")