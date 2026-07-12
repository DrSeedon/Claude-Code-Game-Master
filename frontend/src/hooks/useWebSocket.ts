import { useEffect, useRef, useState, useCallback } from 'react';
import { ConnectionStatus, WsServerEvent, isWsServerEvent } from '../types';

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_DELAY_MS = 30000;

export interface UseWebSocketOptions {
  /** Called for every parsed server event, in arrival order */
  onEvent: (event: WsServerEvent) => void;
  /** Replay cursor — sent as `after_id` query param on every (re)connect, bumped on every id-bearing event */
  afterIdRef: React.MutableRefObject<number>;
}

export interface UseWebSocketReturn {
  sendMessage: (msg: string) => void;
  connectionStatus: ConnectionStatus;
}

export function useWebSocket(basePath: string, campaign: string, { onEvent, afterIdRef }: UseWebSocketOptions): UseWebSocketReturn {
  const ws = useRef<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const mountedRef = useRef(true);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const buildUrl = useCallback(() => {
    const base = basePath.startsWith('ws') ? basePath : `ws://${window.location.host}${basePath}`;
    const params = new URLSearchParams({ campaign, after_id: String(afterIdRef.current) });
    return `${base}?${params.toString()}`;
  }, [basePath, campaign, afterIdRef]);

  const connect = useCallback(() => {
    const socket = new WebSocket(buildUrl());
    ws.current = socket;

    socket.onopen = () => {
      if (!mountedRef.current) return;
      attemptRef.current = 0;
      setConnectionStatus('connected');
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
      if ('id' in parsed) afterIdRef.current = parsed.id;
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
        if (mountedRef.current) connect();
      }, delay);
    };
  }, [buildUrl, afterIdRef]);

  useEffect(() => {
    mountedRef.current = true;
    attemptRef.current = 0;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      const socket = ws.current;
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close();
      }
      ws.current = null;
    };
  }, [connect]);

  const sendMessage = useCallback((msg: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(msg);
    }
  }, []);

  return { sendMessage, connectionStatus };
}
