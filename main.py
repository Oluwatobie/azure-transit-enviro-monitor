import os
import subprocess

if __name__ == "__main__":
    # Check what role Terraform assigned this container
    role = os.environ.get("APP_ROLE", "CONSUMER")
    
    print(f"Container starting up... Assigned Role: {role}", flush=True)
    
    # Use subprocess to run the scripts exactly as if we typed them in the terminal
    if role == "PRODUCER":
        subprocess.run(["python", "producer.py"])
    else:
        subprocess.run(["python", "consumer.py"])