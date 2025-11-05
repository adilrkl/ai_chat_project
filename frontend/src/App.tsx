import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar'; // <- DEĞİŞİKLİK 1
import ChatWindow from './components/ChatWindow';
import axios from 'axios';
import './App.css';
import type { ChatSession } from './types'; // <- DEĞİŞİKLİK BURADA
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
interface ModelsResponse {
  available_models: Record<string, string>;
  current_model: string;
}

function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [models, setModels] = useState<Record<string, string>>({});
  const [currentModel, setCurrentModel] = useState<string>('');
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  // Modelleri yükle
  useEffect(() => {
    setIsLoadingModels(true);
    axios.get<ModelsResponse>(`${API_URL}/models`)
      .then(response => {
        setModels(response.data.available_models);
        setCurrentModel(response.data.current_model);
      })
      .catch(error => console.error("Error fetching models:", error))
      .finally(() => setIsLoadingModels(false));
  }, []);

  useEffect(() => {
    axios.get(`${API_URL}/sessions`)
      .then(response => {
        setSessions(response.data);
      })
      .catch(error => console.error("Error fetching sessions:", error));
  }, []);

  // Model seç
  const handleModelChange = (modelId: string) => {
    axios.post(`${API_URL}/models/select/${modelId}`)
      .then(response => {
        setCurrentModel(response.data.current_model);
        console.log(`Model changed to: ${response.data.model_name}`);
      })
      .catch(error => console.error("Error changing model:", error));
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
  };
  
  const handleSessionCreated = (newSession: ChatSession) => {
    setSessions(prevSessions => [newSession, ...prevSessions]);
    setActiveSessionId(newSession.id);
  };

  return (
    <div className="app-container">
      {/* Model Selection Bar */}
      <div className="model-selector-bar">
        <label htmlFor="model-select">Model Seç:</label>
        <select 
          id="model-select"
          value={currentModel} 
          onChange={(e) => handleModelChange(e.target.value)}
          disabled={isLoadingModels}
        >
          {Object.entries(models).map(([modelId, modelName]) => (
            <option key={modelId} value={modelId}>
              {modelName}
            </option>
          ))}
        </select>
      </div>

      <div className="main-layout">
        <Sidebar 
          sessions={sessions}
          onNewChat={handleNewChat}
          onSelectSession={setActiveSessionId}
          activeSessionId={activeSessionId}
        />
        <ChatWindow 
          activeSessionId={activeSessionId}
          onSessionCreated={handleSessionCreated}
        />
      </div>
    </div>
  );
}

export default App;