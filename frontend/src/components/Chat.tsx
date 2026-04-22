import { useState, useRef, useEffect, useCallback } from 'react';
import Markdown from 'react-markdown';
import { useWebSocket } from '../hooks/useWebSocket';
import { Message } from '../types';

/**
 * Chat component props
 */
interface ChatProps {
  /** Optional WebSocket URL override (defaults to /ws/game) */
  wsUrl?: string;
}

/**
 * Main chat interface component
 *
 * Displays message history between player and DM, with real-time streaming responses.
 * Uses WebSocket for bi-directional communication.
 *
 * @example
 * ```tsx
 * <Chat />
 * ```
 */
export function Chat({ wsUrl = '/ws/game' }: ChatProps) {
  // WebSocket connection
  const { messages: rawMessages, sendMessage, connectionStatus } = useWebSocket(wsUrl);

  // Message history as structured Message objects
  const [messageHistory, setMessageHistory] = useState<Message[]>([]);

  // Current input value
  const [inputValue, setInputValue] = useState('');

  // Auto-scroll reference
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const streamingMessageIndexRef = useRef<number | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (rawMessages.length === 0) return;

    const latestChunk = rawMessages[rawMessages.length - 1];

    // Try to parse as JSON
    try {
      const parsed = JSON.parse(latestChunk);

      if (parsed.type === 'activity') {
        streamingMessageIndexRef.current = null;
        setMessageHistory(prev => [...prev, { role: 'assistant' as const, content: `%%ACTIVITY%%${parsed.content}`, timestamp: Date.now() }]);
        return;
      }

      if (parsed.type === 'history' && Array.isArray(parsed.messages)) {
        setMessageHistory(parsed.messages.map((m: any) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.timestamp ? new Date(m.timestamp).getTime() : Date.now()
        })));
        return;
      }

      if (parsed.type === 'done') {
        streamingMessageIndexRef.current = null;
        setIsGenerating(false);
        return;
      }

      if (parsed.type === 'text') {
        if (!isGenerating) setIsGenerating(true);
        setMessageHistory(prev => {
          if (streamingMessageIndexRef.current !== null && streamingMessageIndexRef.current < prev.length) {
            const updated = [...prev];
            updated[streamingMessageIndexRef.current].content += parsed.content;
            return updated;
          } else {
            streamingMessageIndexRef.current = prev.length;
            return [...prev, { role: 'assistant', content: parsed.content, timestamp: Date.now() }];
          }
        });
        return;
      }
    } catch {
      // Non-JSON fallback — treat as raw text
      if (!isGenerating) setIsGenerating(true);
      setMessageHistory(prev => {
        if (streamingMessageIndexRef.current !== null) {
          const updated = [...prev];
          updated[streamingMessageIndexRef.current].content += latestChunk;
          return updated;
        } else {
          streamingMessageIndexRef.current = prev.length;
          return [...prev, { role: 'assistant', content: latestChunk, timestamp: Date.now() }];
        }
      });
    }
  }, [rawMessages]);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messageHistory]);

  // Handle message send
  const handleSend = useCallback(() => {
    if (!inputValue.trim()) return;
    if (connectionStatus !== 'connected') {
      console.warn('Cannot send message: WebSocket not connected');
      return;
    }

    // Add user message to history
    const userMessage: Message = {
      role: 'user',
      content: inputValue.trim(),
      timestamp: Date.now()
    };
    setMessageHistory(prev => [...prev, userMessage]);

    streamingMessageIndexRef.current = null;
    setIsGenerating(true);

    // Send to backend
    sendMessage(inputValue.trim());

    // Clear input
    setInputValue('');
  }, [inputValue, sendMessage, connectionStatus]);

  // Handle Enter key press
  const handleKeyPress = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div className="chat-container">
      {/* Connection status indicator */}
      <div className="connection-status">
        <div className={`status-indicator status-${connectionStatus}`} />
        <span className="status-text">
          {connectionStatus === 'connecting' && 'Подключение к DM...'}
          {connectionStatus === 'connected' && 'Подключено'}
          {connectionStatus === 'disconnected' && 'Отключено'}
          {connectionStatus === 'error' && 'Ошибка подключения'}
        </span>
      </div>

      {/* Message history */}
      <div className="messages-container">
        {messageHistory.length === 0 ? (
          <div className="empty-state">
            <p>Добро пожаловать! Напишите что-нибудь для начала приключения...</p>
          </div>
        ) : (
          messageHistory.map((msg, idx) => (
            msg.content.startsWith('%%ACTIVITY%%') ? (
              <div key={idx} className="message-activity">{msg.content.replace('%%ACTIVITY%%', '')}</div>
            ) : (
              <div key={idx} className={`message message-${msg.role}`}>
                <div className="message-role">
                  {msg.role === 'user' ? 'Игрок' : 'DM'}
                </div>
                <div className="message-content">
                  {msg.role === 'assistant' ? <Markdown>{msg.content}</Markdown> : msg.content}
                </div>
              </div>
            )
          ))
        )}
        {isGenerating && (
          <div className="generating-indicator">
            <div className="generating-bar" />
            <span>DM печатает...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message input */}
      <div className="input-container">
        <input
          type="text"
          className="message-input"
          placeholder="Введите сообщение..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={connectionStatus !== 'connected'}
        />
        <button
          className="send-button"
          onClick={handleSend}
          disabled={connectionStatus !== 'connected' || !inputValue.trim()}
        >
          Отправить
        </button>
      </div>

      <style>{`
        .chat-container {
          display: flex;
          flex-direction: column;
          height: 100%;
          width: 100%;
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 16px;
          background-color: rgba(0, 0, 0, 0.2);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .status-indicator {
          width: 10px;
          height: 10px;
          border-radius: 50%;
        }

        .status-connecting {
          background-color: #fbbf24;
          animation: pulse 2s infinite;
        }

        .status-connected {
          background-color: #10b981;
        }

        .status-disconnected {
          background-color: #6b7280;
        }

        .status-error {
          background-color: #ef4444;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .status-text {
          font-size: 14px;
          color: rgba(255, 255, 255, 0.7);
        }

        .messages-container {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: rgba(255, 255, 255, 0.5);
          font-style: italic;
        }

        .message {
          display: flex;
          flex-direction: column;
          gap: 4px;
          max-width: 80%;
        }

        .message-user {
          align-self: flex-end;
          align-items: flex-end;
        }

        .message-assistant {
          align-self: flex-start;
          align-items: flex-start;
        }

        .message-role {
          font-size: 12px;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.6);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .message-content {
          padding: 12px 16px;
          border-radius: 12px;
          line-height: 1.5;
          white-space: pre-wrap;
          word-wrap: break-word;
          word-break: break-word;
          overflow-wrap: break-word;
          overflow-x: hidden;
          max-width: 100%;
        }

        .message-content p { margin: 0 0 8px 0; }
        .message-content p:last-child { margin: 0; }
        .message-content ul, .message-content ol { margin: 4px 0; padding-left: 20px; }
        .message-content strong { color: rgba(255,255,255,1); }

        .message-user .message-content {
          background-color: #3b82f6;
          color: white;
        }

        .message-assistant .message-content {
          background-color: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.87);
        }

        .input-container {
          display: flex;
          gap: 8px;
          padding: 16px;
          background-color: rgba(0, 0, 0, 0.2);
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .message-input {
          flex: 1;
          padding: 12px 16px;
          background-color: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 8px;
          color: rgba(255, 255, 255, 0.87);
          font-size: 14px;
          outline: none;
          transition: border-color 0.2s;
        }

        .message-input:focus {
          border-color: #3b82f6;
        }

        .message-input:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .message-input::placeholder {
          color: rgba(255, 255, 255, 0.4);
        }

        .send-button {
          padding: 12px 24px;
          background-color: #3b82f6;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .send-button:hover:not(:disabled) {
          background-color: #2563eb;
        }

        .send-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .message-activity {
          align-self: flex-start;
          font-size: 12px;
          font-family: monospace;
          color: rgba(255, 255, 255, 0.35);
          padding: 2px 12px;
          max-width: 90%;
          word-break: break-all;
          white-space: pre-wrap;
        }

        .generating-indicator {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 16px;
          color: rgba(255, 255, 255, 0.5);
          font-size: 13px;
        }

        .generating-bar {
          width: 40px;
          height: 3px;
          background: rgba(59, 130, 246, 0.3);
          border-radius: 2px;
          overflow: hidden;
          position: relative;
        }

        .generating-bar::after {
          content: '';
          position: absolute;
          top: 0;
          left: -40px;
          width: 40px;
          height: 100%;
          background: #3b82f6;
          border-radius: 2px;
          animation: generating-slide 1s ease-in-out infinite;
        }

        @keyframes generating-slide {
          0% { left: -40px; }
          100% { left: 40px; }
        }

      `}</style>
    </div>
  );
}
