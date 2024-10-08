# Use the official Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that the app will run on
EXPOSE 8080

# Define environment variable
ENV FLASK_APP=cache.py

# Run the Flask application
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
