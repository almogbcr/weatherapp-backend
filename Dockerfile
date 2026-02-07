#Get image of python 3.12
FROM python:3.12-slim

#metadata
LABEL maintainer="almog"
LABEL description="FastAPI backend with Uvicorn"
LABEL version="1.0.0"
LABEL env="dev"

#Install necessary packages for the application
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

#Set the working directory
WORKDIR /opt/weatherapp/backend
#Copy the requirements file to the working directory
COPY requirements.txt .
#Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt
#Copy the rest of the application code to the working directory
COPY . .
#Expose the port that the application will run on
EXPOSE 8000
#Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]