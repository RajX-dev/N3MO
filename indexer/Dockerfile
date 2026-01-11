FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY index_files_es.py .
CMD ["python", "index_files_es.py"]
