export interface Message {
  role: 'user' | 'assistant' | string;
  content: string;
  reasoning?: string; // Reasoning content (GPT-5 gibi reasoning modelleri için)
  images?: string[]; // Base64 data URLs
  isCached?: boolean;
  // opsiyonel: id, timestamp vb. isterseniz ekleyin
}

export interface ChatSession {
  id: number;
  created_at?: string;
  messages?: Message[];
}