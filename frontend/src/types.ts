/**
 * TypeScript type definitions for DM Game Master frontend
 */

/**
 * Chat message type
 */
export interface Message {
  /** Message role - either user or AI assistant */
  role: 'user' | 'assistant';
  /** Message content text */
  content: string;
  /** Optional timestamp for message ordering */
  timestamp?: number;
}

/**
 * Inventory item
 */
export interface InventoryItem {
  /** Item name */
  name: string;
  /** Item quantity */
  quantity: number;
}

/**
 * Character status data from backend API
 */
export interface CharacterStatus {
  /** Character name */
  name: string;
  /** Current health points */
  hp: number;
  /** Maximum health points */
  max_hp: number;
  /** Experience points */
  xp: number;
  /** Gold in base units (copper) */
  gold: number;
  /** Inventory items list */
  inventory: InventoryItem[];
  /** Current location (optional) */
  location?: string;
  /** Error message if status fetch failed (optional) */
  error?: string;
}

/**
 * WebSocket connection status
 */
export type ConnectionStatus =
  | 'connecting'    // Initial connection attempt
  | 'connected'     // Successfully connected
  | 'reconnecting'  // Lost connection, retrying with backoff
  | 'disconnected'  // Connection closed, not retrying (e.g. clean close)
  | 'failed';       // Exceeded max reconnect attempts

/**
 * Raw event shapes sent by the backend over the game WebSocket
 */
export type WsServerEvent =
  | { type: 'text'; content: string; id: number }
  | { type: 'activity'; content: string; id: number }
  | { type: 'error'; content: string; id: number }
  | { type: 'done'; id: number }
  | { type: 'history'; messages: Message[] };

/**
 * Type guard for known server event shapes. Unknown/malformed events are dropped.
 */
export function isWsServerEvent(value: unknown): value is WsServerEvent {
  if (typeof value !== 'object' || value === null || !('type' in value)) return false;
  const type = (value as { type: unknown }).type;
  return type === 'text' || type === 'activity' || type === 'error' || type === 'done' || type === 'history';
}

/**
 * API error response
 */
export interface ApiError {
  /** Error message */
  error: string;
}

/**
 * Type guard to check if response is an error
 */
export function isApiError(response: unknown): response is ApiError {
  return (
    typeof response === 'object' &&
    response !== null &&
    'error' in response &&
    typeof (response as ApiError).error === 'string'
  );
}

/**
 * Type guard to check if character status is valid (not an error)
 */
export function isValidCharacterStatus(status: CharacterStatus): boolean {
  return !status.error && status.name !== undefined;
}
