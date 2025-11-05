# Python'un resmi imajını temel al
FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# requirements.txt dosyasını kopyala ve paketleri kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarının geri kalanını kopyala
COPY . .

# Uygulamayı 8000 portunda çalıştır
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]