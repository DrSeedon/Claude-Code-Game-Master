import { useEffect, useRef, useState, useCallback } from 'react';
import { ConnectionStatus, WsServerEvent, isWsServerEvent } from '../types';

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_DELAY_MS = 30000;

export interface UseWebSocketOptions {
  /** Called for every parsed server event, in arrival order */
  onEvent: (event: WsServerEvent) => void;
}

export interface UseWebSocketReturn {
  sendMessage: (msg: string) => void;
  connectionStatus: ConnectionStatus;
}

export function useWebSocket(url: string, { onEvent }: UseWebSocketOptions): UseWebSocketReturn {
  const ws = useRef<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const mountedRef = useRef(true);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastEventIdRef = useRef<number | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback((wsUrl: string) => {
    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      if (!mountedRef.current) return;
      attemptRef.current = 0;
      setConnectionStatus('connected');
      if (lastEventIdRef.current !== null) {
        socket.send(JSON.stringify({ type: 'replay', after_id: lastEventIdRef.current }));
      }
    };

    socket.onmessage = (event) => {
      if (!mountedRef.current) return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!isWsServerEvent(parsed)) return;
      if ('id' in parsed) lastEventIdRef.current = parsed.id;
      onEventRef.current(parsed);
    };

    socket.onerror = () => {
      // onclose fires right after onerror for connection failures — reconnect handled there
    };

    socket.onclose = (event) => {
      ws.current = null;
      if (!mountedRef.current) return;
      if (event.wasClean) {
        setConnectionStatus('disconnected');
        return;
      }
      if (attemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setConnectionStatus('failed');
        return;
      }
      setConnectionStatus('reconnecting');
      const delay = Math.min(BASE_RECONNECT_DELAY_MS * 2 ** attemptRef.current, MAX_RECONNECT_DELAY_MS);
      attemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) connect(wsUrl);
      }, delay);
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    attemptRef.current = 0;
    lastEventIdRef.current = null;
    const wsUrl = url.startsWith('ws') ? url : `ws://${window.location.host}${url}`;
    connect(wsUrl);

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      const socket = ws.current;
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close();
      }
      ws.current = null;
    };
  }, [url, connect]);

  const sendMessage = useCallback((msg: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(msg);
    }
  }, []);

  return { sendMessage, connectionStatus };
}
