# Use the official, lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python scripts into the container
COPY . .

# Tell the container to run the either producer or consumer script
CMD ["python", "main.py"]