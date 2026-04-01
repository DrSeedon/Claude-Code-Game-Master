import { useEffect, useState, useRef, useCallback } from 'react';
import { ConnectionStatus } from '../types';

export interface UseWebSocketReturn {
  messages: string[];
  sendMessage: (msg: string) => void;
  connectionStatus: ConnectionStatus;
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const ws = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const wsUrl = url.startsWith('ws') ? url : `ws://${window.location.host}${url}`;
    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      if (mountedRef.current) {
        setConnectionStatus('connected');
      }
    };

    socket.onmessage = (event) => {
      if (mountedRef.current) {
        setMessages(prev => [...prev, event.data]);
      }
    };

    socket.onerror = () => {
      if (mountedRef.current) setConnectionStatus('error');
    };

    socket.onclose = () => {
      if (mountedRef.current) setConnectionStatus('disconnected');
    };

    return () => {
      mountedRef.current = false;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
      ws.current = null;
    };
  }, [url]);

  const sendMessage = useCallback((msg: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(msg);
    }
  }, []);

  return { messages, sendMessage, connectionStatus };
}
