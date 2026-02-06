# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.9-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup.
# Streamlit runs on port 8501 by default, but Cloud Run expects $PORT (usually 8080).
# We instruct streamlit to use $PORT
CMD sh -c "streamlit run vix_fix_dashboard.py --server.port=8080 --server.address=0.0.0.0"
