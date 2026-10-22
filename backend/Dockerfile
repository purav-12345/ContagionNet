FROM python:3.11-slim

WORKDIR /app

# System deps for scipy/numpy wheels are bundled; keep image small.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
