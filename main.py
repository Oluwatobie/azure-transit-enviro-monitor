import os
import subprocess

if __name__ == "__main__":
    # Check what role Terraform assigned this container
    role = os.environ.get("APP_ROLE", "CONSUMER")
    
    # We added flush=True here earlier to force this print to show up!
    print(f"Container starting up... Assigned Role: {role}", flush=True)
    
    # Add the "-u" (unbuffered) flag to force Python to print all logs instantly
    if role == "PRODUCER":
        subprocess.run(["python", "-u", "producer.py"])
    else:
        subprocess.run(["python", "-u", "consumer.py"])