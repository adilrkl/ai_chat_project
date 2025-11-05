import React from 'react';
import type { ChatSession } from '../types'; // <- DEĞİŞİKLİK BURADA
interface SidebarProps {
  sessions: ChatSession[];
  onNewChat: () => void;
  onSelectSession: (id: number) => void;
  activeSessionId: number | null;
}

const Sidebar: React.FC<SidebarProps> = ({ sessions, onNewChat, onSelectSession, activeSessionId }) => {

    return (
    <div className="sidebar">
      <button onClick={onNewChat} className="new-chat-btn">
        + New Chat
      </button>
      <div className="session-list">
        {sessions.map(session => (
          <div 
            key={session.id}
            className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
            onClick={() => onSelectSession(session.id)}
          >
            Chat #{session.id}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Sidebar;