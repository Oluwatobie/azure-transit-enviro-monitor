import os
import json
from pymongo import MongoClient
from azure.servicebus import ServiceBusClient
from azure.identity import DefaultAzureCredential

# --- CONFIGURATION ---
QUEUE_NAME = "leicester-trains"
DB_NAME = "TransitMonitorDB"
COLLECTION_NAME = "Departures"

# Grab our dynamic secrets injected by Terraform/Local Terminal
FULLY_QUALIFIED_NAMESPACE = os.environ.get("SERVICE_BUS_NAMESPACE")
COSMOS_CONNECTION_STRING = os.environ.get("COSMOS_CONNECTION_STRING")

def process_messages():
    """Listens to the Service Bus and saves messages to Cosmos DB (MongoDB API)"""
    if not FULLY_QUALIFIED_NAMESPACE or not COSMOS_CONNECTION_STRING:
        print("❌ Error: Missing Environment Variables.")
        return

    # 1. Connect to Cosmos DB
    print("Connecting to Cosmos DB...")
    mongo_client = MongoClient(COSMOS_CONNECTION_STRING)
    db = mongo_client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # 2. Connect to Service Bus (Using Zero-Trust Identity!)
    credential = DefaultAzureCredential()
    print(f"Connecting to Service Bus Queue '{QUEUE_NAME}'...")
    
    with ServiceBusClient(FULLY_QUALIFIED_NAMESPACE, credential=credential) as sb_client:
        # We create a receiver to constantly listen to the queue
        with sb_client.get_queue_receiver(queue_name=QUEUE_NAME, max_wait_time=5) as receiver:
            
            print("\n🎧 Listening for live train updates... (Press Ctrl+C to stop)")
            
            for msg in receiver:
                try:
                    # 3. Read the JSON document from the queue
                    train_data = json.loads(str(msg))
                    
                    # 4. Save to Cosmos DB
                    # We use 'update_one' with upsert=True so if a train delays/changes, 
                    # it updates the existing record instead of creating a duplicate!
                    collection.update_one(
                        {"_id": train_data["id"]}, 
                        {"$set": train_data}, 
                        upsert=True
                    )
                    
                    print(f"💾 Saved to DB: {train_data['scheduled_departure']} to {train_data['destination']}")
                    
                    # 5. Tell the Service Bus we are done, so it safely deletes the message
                    receiver.complete_message(msg)
                    
                except Exception as e:
                    print(f"⚠️ Error processing message: {e}")
                    # If it crashes, we abandon the message so it goes back to the queue to try again
                    receiver.abandon_message(msg)

if __name__ == "__main__":
    process_messages()