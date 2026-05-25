FROM python:3.11-slim

WORKDIR /app

# Install CPU-only PyTorch first to avoid pulling the CUDA variant
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8070

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8070"]
