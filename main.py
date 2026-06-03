import os
import time

if __name__ == "__main__":
    # Check what role Terraform assigned this container (defaults to CONSUMER)
    role = os.environ.get("APP_ROLE", "CONSUMER")
    
    print(f"Container starting up... Assigned Role: {role}")
    
    if role == "PRODUCER":
        # Import and run the producer loop
        import producer
    else:
        # Import and run the consumer loop
        import consumer