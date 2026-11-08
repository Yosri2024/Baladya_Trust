FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000 8501 50051
CMD ["streamlit", "run", "dashboard/streamlit_command_center.py", "--server.port=8501", "--server.address=0.0.0.0"]
