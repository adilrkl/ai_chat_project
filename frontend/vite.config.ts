import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Vite'e hangi adreslerden gelen isteklere izin vereceğini söylüyoruz.
    // '*' tüm adreslere izin verir, bu geliştirme için kolaylık sağlar.
    // Daha güvenli bir yaklaşım için ['aichat.talent14.com', 'www.aichat.talent14.com'] gibi bir liste de kullanabilirsiniz.
    allowedHosts: ['*','localhost','127.0.0.1',"aichat.talent14.com","http://localhost:5173/"],
  }
})