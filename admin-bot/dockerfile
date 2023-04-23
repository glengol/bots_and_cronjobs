# Base image
FROM python:3.9-slim-buster

# Copy application code
COPY ./Src /src
COPY ./templates /templates
WORKDIR /src

# Install dependencies
RUN pip install -r requirements.txt


# Run application
CMD ["python", "main.py"]
