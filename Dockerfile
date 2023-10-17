FROM python:3.9

# Set the working directory to /app
WORKDIR /app

COPY ./user-service/requirements.txt .

COPY ./user-service/src ./src

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "./src/app.py"]

