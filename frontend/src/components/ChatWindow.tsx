import { useState, useEffect, useRef } from 'react';
import type { FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import axios from 'axios';
import type { ChatSession, Message } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat';

interface ChatWindowProps {
  activeSessionId: number | null;
  onSessionCreated: (newSession: ChatSession) => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ activeSessionId, onSessionCreated }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const [isNewSessionCreating, setIsNewSessionCreating] = useState(false);
  const currentSocketSessionId = useRef<number | null>(null);
  
  // Her mesaj eklendiğinde en alta kaydır
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Aktif sohbet ID'si değiştiğinde geçmiş mesajları yükle
  useEffect(() => {
    if (activeSessionId && !isNewSessionCreating) {
      setIsLoading(true);
      axios.get(`${API_URL}/sessions/${activeSessionId}`)
        .then(response => {
          setMessages(response.data.messages || []);
        })
        .catch(error => {
          console.error("Error fetching messages:", error);
          setMessages([]);
        })
        .finally(() => setIsLoading(false));
    } else if (activeSessionId === null && !isNewSessionCreating) {
      setMessages([]); // Yeni sohbet için ekranı temizle
    }
  }, [activeSessionId, isNewSessionCreating]);

  // WebSocket bağlantısını yöneten ana useEffect
  useEffect(() => {
    // Bu useEffect, activeSessionId değiştiğinde çalışır.
    // Yani ya yeni bir sohbete geçildiğinde ya da "new chat" butonuna basıldığında.
    
    // "Yeni sohbet" modundaysak (kullanıcı henüz mesaj göndermedi), bağlantı kurma.
    if (activeSessionId === null) {
      // Önceki bağlantıyı kapat
      if (socketRef.current) {
        socketRef.current.onclose = null;
        socketRef.current.close();
        socketRef.current = null;
      }
      currentSocketSessionId.current = null;
      return;
    }

    // Eğer mevcut bağlantı zaten bu session_id için açıksa, yeni bağlantı açma
    if (currentSocketSessionId.current === activeSessionId && 
        socketRef.current && 
        socketRef.current.readyState === WebSocket.OPEN) {
      console.log(`WebSocket already connected for session ${activeSessionId}, reusing connection`);
      return;
    }
    
    // Önceki bağlantıyı kapat (eğer farklı bir session için açıksa)
    if (socketRef.current) {
      socketRef.current.onclose = null; // Reconnect döngüsünü engellemek için
      socketRef.current.close();
    }

    // Mevcut bir sohbet için yeni bağlantı kur
    const socket = new WebSocket(`${WS_BASE_URL}/${activeSessionId}`);
    socketRef.current = socket;
    currentSocketSessionId.current = activeSessionId;

    socket.onopen = () => console.log(`WebSocket connected for session ${activeSessionId}`);

    socket.onmessage = (event) => {
      // Mesaj işleme mantığını buraya taşıyoruz, useCallback'den çıkarıyoruz
      try {
        const data = JSON.parse(event.data);
        
        // Bu session'a ait geçmiş mesajlar ilk bağlantıda gönderilir
        if (data.type === 'chat_history') {
            setMessages(data.messages || []);
            setIsLoading(false);
            return;
        }

        if (data.type === 'chat_message') {
          if (!isLoading) setIsLoading(true); // Bunu onmessage içinde yönetmek daha güvenli
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === 'assistant') {
              return [...prev.slice(0, -1), { ...lastMessage, content: lastMessage.content + data.content }];
            }
            return [...prev, { role: 'assistant', content: data.content }];
          });
        } else if (data.type === 'reasoning') {
          // Reasoning içeriği (GPT-5 gibi reasoning modelleri için)
          if (!isLoading) setIsLoading(true);
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === 'assistant') {
              const existingReasoning = lastMessage.reasoning || '';
              return [...prev.slice(0, -1), { ...lastMessage, reasoning: existingReasoning + data.content }];
            }
            return [...prev, { role: 'assistant', content: '', reasoning: data.content }];
          });
        } else if (data.type === 'image') {
          // Görsel mesajı ekle
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === 'assistant') {
              const existingImages = lastMessage.images || [];
              if (!existingImages.includes(data.image_url)) {
                return [...prev.slice(0, -1), { ...lastMessage, images: [...existingImages, data.image_url] }];
              }
              return prev;
            }
            return [...prev, { role: 'assistant', content: '', images: [data.image_url] }];
          });
        } else if (data.type === 'stream_end') {
          setIsLoading(false);
        } else if (data.type === 'error') {
          console.error("Backend Error:", data.message);
          setIsLoading(false);
        }
      } catch (e) {
        console.error("Failed to parse message or process chunk:", e, event.data);
        setIsLoading(false);
      }
    };

    socket.onerror = (error) => console.error('WebSocket error:', error);
    socket.onclose = () => console.log(`WebSocket for session ${activeSessionId} disconnected`);

    // Component unmount olduğunda veya ID değiştiğinde bu cleanup fonksiyonu çalışır
    return () => {
      socket.onclose = null; // Reconnect döngüsünü engellemek için
      socket.close();
    };
  }, [activeSessionId]); // Sadece activeSessionId değiştiğinde çalışsın

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: 'user', content: input };
    const newMessages = [...messages, userMessage];

    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    // Eğer bu yeni bir sohbetse (activeSessionId null ise), /new adresine bağlan ve ilk mesajı gönder
    if (activeSessionId === null) {
      const newSocket = new WebSocket(`${WS_BASE_URL}/new`);
      socketRef.current = newSocket;

      newSocket.onopen = () => {
        newSocket.send(JSON.stringify(newMessages));
      };

      // Bu yeni soketin de mesajları işlemesi lazım
      newSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'session_created') {
            // Backend'den yeni session ID'si geldi, App.tsx'i bilgilendir
            // Ancak mevcut WebSocket bağlantısını KAPATMIYORUZ!
            // Backend aynı bağlantıyı kullanmaya devam edecek
            currentSocketSessionId.current = data.session_id;
            setIsNewSessionCreating(true);
            onSessionCreated({ id: data.session_id, created_at: new Date().toISOString() });
            setIsNewSessionCreating(false);
            console.log(`Session created with ID: ${data.session_id}, keeping WebSocket connection open`);
            return;
          }
          
          // Normal mesaj işleme mantığı
          if (data.type === 'chat_message') {
            if (!isLoading) setIsLoading(true);
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage?.role === 'assistant') {
                return [...prev.slice(0, -1), { ...lastMessage, content: lastMessage.content + data.content }];
              }
              return [...prev, { role: 'assistant', content: data.content }];
            });
          } else if (data.type === 'reasoning') {
            // Reasoning içeriği (GPT-5 gibi reasoning modelleri için)
            if (!isLoading) setIsLoading(true);
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage?.role === 'assistant') {
                const existingReasoning = lastMessage.reasoning || '';
                return [...prev.slice(0, -1), { ...lastMessage, reasoning: existingReasoning + data.content }];
              }
              return [...prev, { role: 'assistant', content: '', reasoning: data.content }];
            });
          } else if (data.type === 'image') {
            // Görsel mesajı ekle
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage?.role === 'assistant') {
                const existingImages = lastMessage.images || [];
                if (!existingImages.includes(data.image_url)) {
                  return [...prev.slice(0, -1), { ...lastMessage, images: [...existingImages, data.image_url] }];
                }
                return prev;
              }
              return [...prev, { role: 'assistant', content: '', images: [data.image_url] }];
            });
          } else if (data.type === 'stream_end') {
            setIsLoading(false);
          } else if (data.type === 'error') {
            console.error("Backend Error:", data.message);
            setIsLoading(false);
          }
        } catch (e) {
          console.error("Failed to parse message or process chunk:", e, event.data);
          setIsLoading(false);
        }
      };

      newSocket.onerror = (error) => console.error('New chat WebSocket error:', error);
      newSocket.onclose = () => console.log('New chat WebSocket disconnected');
    } 
    // Mevcut sohbetse, açık olan bağlantıdan gönder
    else if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(newMessages));
    } else {
      console.error("WebSocket is not open. Reconnecting might be in progress.");
      setIsLoading(false);
    }
    
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
  };

  return (
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index}>
              {/* Cache sınırını göstermek için renkli çizgi */}
              {index === 9 && messages.length >= 10 && (
                <div className="cache-separator">
                  <div className="cache-line"></div>
                  <span className="cache-label">📦 Buradan sonrası önbellekte</span>
                </div>
              )}
              <div className={`message ${msg.role}`}>
                {msg.images && msg.images.length > 0 && (
                  <div className="message-images">
                    {msg.images.map((imageUrl, imgIndex) => (
                      <img 
                        key={imgIndex} 
                        src={imageUrl} 
                        alt={`Generated image ${imgIndex + 1}`}
                        style={{ maxWidth: '100%', height: 'auto', marginBottom: '10px', borderRadius: '8px' }}
                      />
                    ))}
                  </div>
                )}
                {msg.reasoning && (
                  <div className="reasoning-content" style={{ 
                    backgroundColor: '#f5f5f5', 
                    padding: '10px', 
                    borderRadius: '8px', 
                    marginBottom: '10px',
                    fontSize: '0.9em',
                    fontStyle: 'italic',
                    color: '#666'
                  }}>
                    <strong>💭 Reasoning:</strong>
                    <ReactMarkdown
                      rehypePlugins={[rehypeHighlight]}
                      components={{ a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
                    >
                      {msg.reasoning}
                    </ReactMarkdown>
                  </div>
                )}
                {msg.content && (
                  <ReactMarkdown
                    rehypePlugins={[rehypeHighlight]}
                    components={{ a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <form onSubmit={handleSubmit} className="message-form">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Bir mesaj yazın..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? '...' : 'Gönder'}
          </button>
        </form>
      </div>
  );
};

export default ChatWindow;