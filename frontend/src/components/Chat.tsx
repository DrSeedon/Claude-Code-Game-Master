import { useState, useRef, useEffect, useCallback } from 'react';
import Markdown from 'react-markdown';
import { useWebSocket } from '../hooks/useWebSocket';
import { useStreamingBuffer } from '../hooks/useStreamingBuffer';
import { Message, WsServerEvent } from '../types';

const MAX_MESSAGES = 500;
const AUTO_SCROLL_THRESHOLD_PX = 80;

/**
 * Chat component props
 */
interface ChatProps {
  /** Campaign this chat streams — becomes the `campaign` query param on the WS connection */
  campaign: string;
  /** Optional WebSocket base path override (defaults to /ws/game) */
  wsPath?: string;
}

type ChatMessage = Message & {
  /** 'activity' renders as an inline tool-call line, 'error' as a red banner message */
  kind?: 'activity' | 'error';
};

function bounded(messages: ChatMessage[]): ChatMessage[] {
  return messages.length > MAX_MESSAGES ? messages.slice(messages.length - MAX_MESSAGES) : messages;
}

/**
 * Main chat interface component
 *
 * Displays message history between player and DM, with real-time token-by-token
 * streaming responses (via useStreamingBuffer) over a per-campaign WebSocket.
 *
 * @example
 * ```tsx
 * <Chat campaign="my-campaign" />
 * ```
 */
export function Chat({ campaign, wsPath = '/ws/game' }: ChatProps) {
  const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const localEchoRef = useRef<Set<string>>(new Set());
  const afterIdRef = useRef(0);

  const stream = useStreamingBuffer();

  const handleEvent = useCallback((event: WsServerEvent) => {
    switch (event.type) {
      case 'stream':
        setIsGenerating(true);
        stream.push(event.content);
        break;

      case 'text': {
        const finalText = stream.active ? stream.finalize(event.content) : event.content;
        setMessageHistory(prev => bounded([...prev, { role: 'assistant', content: finalText, timestamp: Date.now() }]));
        break;
      }

      case 'activity':
        stream.finalize();
        setMessageHistory(prev => bounded([...prev, { role: 'assistant', kind: 'activity', content: event.content, timestamp: Date.now() }]));
        break;

      case 'error':
        stream.reset();
        setIsGenerating(false);
        setMessageHistory(prev => bounded([...prev, { role: 'assistant', kind: 'error', content: event.content, timestamp: Date.now() }]));
        break;

      case 'history':
        stream.reset();
        setMessageHistory(bounded(event.messages
          .filter(m => !localEchoRef.current.has(`${m.role}:${m.content}`))
          .map(m => ({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp ?? Date.now()
          }))));
        break;

      case 'done':
        setIsGenerating(false);
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.active, stream.push, stream.finalize, stream.reset]);

  const { sendMessage, connectionStatus } = useWebSocket(wsPath, campaign, { onEvent: handleEvent, afterIdRef });

  // Track whether the user is scrolled near the bottom (Orchestra's 80px gate)
  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < AUTO_SCROLL_THRESHOLD_PX;
  }, []);

  // Auto-scroll to latest message, but only if the user hasn't scrolled up
  useEffect(() => {
    if (atBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messageHistory, stream.display]);

  // Handle message send
  const handleSend = useCallback(() => {
    if (!inputValue.trim()) return;
    if (connectionStatus !== 'connected') {
      console.warn('Cannot send message: WebSocket not connected');
      return;
    }

    const content = inputValue.trim();
    localEchoRef.current.add(`user:${content}`);
    const userMessage: ChatMessage = { role: 'user', content, timestamp: Date.now() };
    setMessageHistory(prev => bounded([...prev, userMessage]));

    setIsGenerating(true);

    sendMessage(content);
    setInputValue('');
  }, [inputValue, sendMessage, connectionStatus]);

  // Handle Enter key press
  const handleKeyPress = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const statusText: Record<typeof connectionStatus, string> = {
    connecting: 'Подключение к DM...',
    connected: 'Подключено',
    reconnecting: 'Переподключение...',
    disconnected: 'Отключено',
    failed: 'Соединение потеряно'
  };

  return (
    <div className="chat-container">
      {/* Connection status indicator */}
      <div className="connection-status">
        <div className={`status-indicator status-${connectionStatus}`} />
        <span className="status-text">{statusText[connectionStatus]}</span>
      </div>

      {connectionStatus === 'reconnecting' && (
        <div className="reconnect-banner">Переподключение...</div>
      )}

      {connectionStatus === 'failed' && (
        <div className="failed-modal-overlay">
          <div className="failed-modal">
            <h3>Соединение потеряно</h3>
            <p>Перезагрузите страницу</p>
            <button onClick={() => window.location.reload()}>Перезагрузить</button>
          </div>
        </div>
      )}

      {/* Message history */}
      <div className="messages-container" ref={messagesContainerRef} onScroll={handleScroll}>
        {messageHistory.length === 0 && !stream.active ? (
          <div className="empty-state">
            <p>Добро пожаловать! Напишите что-нибудь для начала приключения...</p>
          </div>
        ) : (
          messageHistory.map((msg, idx) => (
            msg.kind === 'activity' ? (
              <ActivityLine key={idx} content={msg.content} />
            ) : msg.kind === 'error' ? (
              <div key={idx} className="message-error">⚠ {msg.content}</div>
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
        {stream.active && (
          <div className="message message-assistant">
            <div className="message-role">DM</div>
            <div className="message-content streaming">
              <Markdown>{stream.display}</Markdown>
              <span className="typing-cursor">▍</span>
            </div>
          </div>
        )}
        {isGenerating && !stream.active && (
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
          position: relative;
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
          background-color: var(--warn);
          animation: pulse 2s infinite;
        }

        .status-connected {
          background-color: var(--ok);
        }

        .status-reconnecting {
          background-color: var(--warn);
          animation: pulse 1s infinite;
        }

        .status-disconnected {
          background-color: #6b7280;
        }

        .status-failed {
          background-color: var(--danger);
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .status-text {
          font-size: 14px;
          color: rgba(255, 255, 255, 0.7);
        }

        .reconnect-banner {
          padding: 6px 16px;
          background-color: rgba(234, 179, 8, 0.15);
          color: var(--warn);
          font-size: 13px;
          text-align: center;
        }

        .failed-modal-overlay {
          position: absolute;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10;
        }

        .failed-modal {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--r-lg);
          padding: 24px 32px;
          text-align: center;
        }

        .failed-modal h3 {
          margin: 0 0 8px 0;
          color: rgba(255, 255, 255, 0.95);
        }

        .failed-modal p {
          margin: 0 0 16px 0;
          color: rgba(255, 255, 255, 0.6);
        }

        .failed-modal button {
          padding: 8px 20px;
          background-color: var(--accent);
          color: white;
          border: none;
          border-radius: var(--r-sm);
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
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
          border-radius: var(--r-lg);
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
          background-color: var(--accent);
          color: white;
        }

        .message-assistant .message-content {
          background-color: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.87);
        }

        .message-error {
          align-self: center;
          max-width: 90%;
          padding: 10px 16px;
          background-color: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.4);
          border-radius: var(--r-md);
          color: #fca5a5;
          font-size: 13px;
          white-space: pre-wrap;
          word-break: break-word;
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
          border-radius: var(--r-md);
          color: rgba(255, 255, 255, 0.87);
          font-size: 14px;
          outline: none;
          transition: border-color 0.2s;
        }

        .message-input:focus {
          border-color: var(--accent);
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
          background-color: var(--accent);
          color: white;
          border: none;
          border-radius: var(--r-md);
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .send-button:hover:not(:disabled) {
          filter: brightness(1.1);
        }

        .send-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
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
          background: rgba(129, 140, 248, 0.3);
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
          background: var(--accent);
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

const TOOL_RESULT_COLLAPSE_LENGTH = 200;

/** Renders a single activity/tool-call event, collapsing long output */
function ActivityLine({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = content.length > TOOL_RESULT_COLLAPSE_LENGTH;
  const display = isLong && !expanded ? `${content.slice(0, TOOL_RESULT_COLLAPSE_LENGTH)}…` : content;

  return (
    <div className="message-activity" onClick={isLong ? () => setExpanded(e => !e) : undefined}>
      <span>{display}</span>
      {isLong && <span className="activity-toggle">{expanded ? ' [свернуть]' : ' [показать всё]'}</span>}
      <style>{`
        .message-activity {
          align-self: flex-start;
          font-size: 12px;
          font-family: monospace;
          color: rgba(255, 255, 255, 0.35);
          padding: 2px 12px;
          max-width: 90%;
          word-break: break-all;
          white-space: pre-wrap;
          cursor: ${isLong ? 'pointer' : 'default'};
        }

        .activity-toggle {
          color: var(--accent);
          font-style: italic;
        }
      `}</style>
    </div>
  );
}
