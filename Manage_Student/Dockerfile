# Use python 3.12.10 base image
FROM python:3.12.10-slim

# Set working directory
WORKDIR /Manage_Students

# copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy rest of application code
COPY . .

# expose the application port
EXPOSE 8000

# command to start FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# docker image name
# prashantkumar011/paitent-management-fastapi-simple-apis