# Node.js'in resmi imajını temel al
FROM node:20-alpine

# Çalışma dizinini ayarla
WORKDIR /app

# package.json ve package-lock.json dosyalarını kopyala
COPY package*.json ./

# Paketleri kur
RUN npm install

# Proje dosyalarının geri kalanını kopyala
COPY . .

# Geliştirme sunucusunu 5173 portunda dışarıya açık şekilde başlat
CMD ["npm", "run", "dev", "--", "--host"]