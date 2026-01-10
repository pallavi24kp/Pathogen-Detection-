import React, { useState, useEffect, useRef } from 'react';
import { BotIcon, SendIcon } from './Icons';

interface Message {
  role: 'user' | 'model';
  parts: { text: string }[];
}

// Simple markdown to HTML conversion
function markdownToHtml(text: string): string {
    // This is a very basic parser. For full markdown support, a library like 'marked' would be better.
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
        .replace(/\*(.*?)\*/g, '<em>$1</em>')     // Italic
        .replace(/`([^`]+)`/g, '<code>$1</code>') // Inline code
        .replace(/\n/g, '<br />');               // Newlines
}


export const Chatbot: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatHistoryRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to the bottom of the chat history when messages change
    if (chatHistoryRef.current) {
      chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: 'user', parts: [{ text: input }] };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    setError(null);
    
    // Add a placeholder for the model's response
    setMessages(prev => [...prev, { role: 'model', parts: [{ text: '' }] }]);

    try {
      // Use a configurable API base so the frontend can call the Python backend
      // even when the Vite proxy isn't used. You can set VITE_API_BASE in
      // your dev environment or leave it to the default below.
      const apiBase = (import.meta.env && import.meta.env.VITE_API_BASE) ? import.meta.env.VITE_API_BASE : 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Send all but the last message (the placeholder) as history
        body: JSON.stringify({
          prompt: input,
          history: newMessages.slice(0, -1), 
        }),
      });

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      const decoder = new TextDecoder();
      let modelResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        modelResponse += decoder.decode(value, { stream: true });
        
        setMessages(prev => {
            const updatedMessages = [...prev];
            updatedMessages[updatedMessages.length - 1].parts[0].text = modelResponse;
            return updatedMessages;
        });
      }

    } catch (e: any) {
      const errorMessage = "Sorry, something went wrong. Please try again.";
      setError(errorMessage);
       setMessages(prev => {
            const updatedMessages = [...prev];
            updatedMessages[updatedMessages.length - 1].parts[0].text = errorMessage;
            return updatedMessages;
       });
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-white dark:bg-gray-800 rounded-2xl shadow-2xl flex flex-col h-[70vh] border border-gray-200 dark:border-gray-700">
      <div ref={chatHistoryRef} className="flex-1 p-6 overflow-y-auto space-y-4">
        {messages.map((msg, index) => (
          <div key={index} className={`flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'model' && (
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900/50 text-blue-500 dark:text-blue-400 rounded-full flex items-center justify-center">
                <BotIcon className="w-5 h-5" />
              </div>
            )}
            <div className={`max-w-md p-3 rounded-2xl ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white rounded-bl-none'}`}>
              <p className="text-sm prose prose-sm dark:prose-invert" dangerouslySetInnerHTML={{ __html: markdownToHtml(msg.parts[0].text) }} />
            </div>
          </div>
        ))}
        {loading && messages[messages.length -1]?.role === 'user' && (
           <div className="flex items-start gap-3">
             <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900/50 text-blue-500 dark:text-blue-400 rounded-full flex items-center justify-center">
                <BotIcon className="w-5 h-5" />
              </div>
            <div className="max-w-md p-3 rounded-2xl bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white rounded-bl-none">
                <div className="flex items-center justify-center space-x-1">
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-pulse [animation-delay:-0.3s]"></div>
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-pulse [animation-delay:-0.15s]"></div>
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-pulse"></div>
                </div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        {error && <p className="text-red-500 text-xs mb-2 text-center">{error}</p>}
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
            placeholder="Type your message..."
            className="w-full p-3 pr-12 text-sm text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-700/50 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
            rows={1}
            disabled={loading}
            aria-label="Chat input"
          />
          <button
            onClick={handleSendMessage}
            disabled={loading || !input.trim()}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 disabled:dark:bg-blue-800 disabled:cursor-not-allowed transition-colors"
            aria-label="Send message"
          >
            <SendIcon className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};
