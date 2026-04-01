import { useEffect, useState, useRef, useCallback } from 'react';
import { ConnectionStatus } from '../types';

/**
 * WebSocket hook return type
 */
export interface UseWebSocketReturn {
  /** Array of messages received from server */
  messages: string[];
  /** Function to send a message to the server */
  sendMessage: (msg: string) => void;
  /** Current WebSocket connection status */
  connectionStatus: ConnectionStatus;
}

/**
 * Custom hook for managing WebSocket connection
 *
 * @param url - WebSocket URL to connect to
 * @returns WebSocket connection state and methods
 *
 * @example
 * ```tsx
 * const { messages, sendMessage, connectionStatus } = useWebSocket('ws://localhost:8000/ws/game');
 *
 * // Send a message
 * sendMessage('Hello DM!');
 *
 * // Display messages
 * messages.forEach(msg => console.log(msg));
 *
 * // Check connection status
 * if (connectionStatus === 'connected') {
 *   // Ready to send messages
 * }
 * ```
 */
export function useWebSocket(url: string): UseWebSocketReturn {
  // Use useRef to maintain WebSocket instance across renders
  const ws = useRef<WebSocket | null>(null);

  // Connection state managed via useState
  const [messages, setMessages] = useState<string[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');

  useEffect(() => {
    // Set initial connecting state
    setConnectionStatus('connecting');

    // Create WebSocket connection
    ws.current = new WebSocket(url);

    // Handle connection open
    ws.current.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
    };

    // Handle incoming messages
    ws.current.onmessage = (event) => {
      setMessages(prev => [...prev, event.data]);
    };

    // Handle connection errors
    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    };

    // Handle connection close
    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');
    };

    // CRITICAL: Cleanup on unmount - close WebSocket to prevent memory leaks
    return () => {
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
    };
  }, [url]);

  // Send message function
  const sendMessage = useCallback((msg: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(msg);
    } else {
      console.warn('WebSocket is not connected. Cannot send message:', msg);
    }
  }, []);

  return { messages, sendMessage, connectionStatus };
}
