import { useState, useEffect, useCallback } from 'react';
import { CharacterStatus, isValidCharacterStatus } from '../types';

/**
 * CharacterPanel component props
 */
interface CharacterPanelProps {
  /** Optional API endpoint override (defaults to /api/status) */
  apiUrl?: string;
  /** Optional refresh interval in milliseconds (defaults to 5000ms) */
  refreshInterval?: number;
}

/**
 * Character status panel component
 *
 * Displays player character stats (HP, XP, Gold, Inventory) in a sidebar.
 * Fetches initial state from backend API and polls for updates.
 *
 * @example
 * ```tsx
 * <CharacterPanel />
 * ```
 */
export function CharacterPanel({
  apiUrl = '/api/status',
  refreshInterval = 5000
}: CharacterPanelProps) {
  // Character status state
  const [status, setStatus] = useState<CharacterStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch character status from API
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(apiUrl);
      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setStatus(null);
      } else if (isValidCharacterStatus(data)) {
        setStatus(data);
        setError(null);
      } else {
        setError('Неверный формат данных');
        setStatus(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки данных');
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl]);

  // Initial fetch on mount
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Poll for updates
  useEffect(() => {
    const intervalId = setInterval(fetchStatus, refreshInterval);
    return () => clearInterval(intervalId);
  }, [fetchStatus, refreshInterval]);

  // Calculate HP percentage for progress bar
  const hpPercentage = status ? Math.round((status.hp / status.max_hp) * 100) : 0;

  // Format gold display (convert copper to gold/silver/copper)
  const formatGold = (copper: number): string => {
    if (!copper) return '0m';

    const gold = Math.floor(copper / 100);
    const silver = Math.floor((copper % 100) / 10);
    const copperRemainder = copper % 10;

    const parts: string[] = [];
    if (gold > 0) parts.push(`${gold}з`);
    if (silver > 0) parts.push(`${silver}с`);
    if (copperRemainder > 0) parts.push(`${copperRemainder}м`);

    return parts.join(' ') || '0м';
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="character-panel">
        <div className="panel-header">
          <h2>Персонаж</h2>
        </div>
        <div className="loading-state">
          <p>Загрузка...</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="character-panel">
        <div className="panel-header">
          <h2>Персонаж</h2>
        </div>
        <div className="error-state">
          <p>⚠️ {error}</p>
          <button onClick={fetchStatus} className="retry-button">
            Повторить
          </button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // No data state
  if (!status) {
    return (
      <div className="character-panel">
        <div className="panel-header">
          <h2>Персонаж</h2>
        </div>
        <div className="empty-state">
          <p>Нет активной кампании</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // Main render with character data
  return (
    <div className="character-panel">
      {/* Header */}
      <div className="panel-header">
        <h2>{status.name || 'Персонаж'}</h2>
        {status.location && (
          <div className="location">
            📍 {status.location}
          </div>
        )}
      </div>

      {/* HP Section */}
      <div className="stat-section">
        <div className="stat-label">Здоровье</div>
        <div className="hp-display">
          <div className="hp-text">
            {status.hp} / {status.max_hp}
          </div>
          <div className="hp-bar">
            <div
              className="hp-bar-fill"
              style={{
                width: `${hpPercentage}%`,
                backgroundColor: hpPercentage > 50 ? '#10b981' : hpPercentage > 25 ? '#fbbf24' : '#ef4444'
              }}
            />
          </div>
        </div>
      </div>

      {/* XP Section */}
      <div className="stat-section">
        <div className="stat-label">Опыт</div>
        <div className="stat-value">{status.xp} XP</div>
      </div>

      {/* Gold Section */}
      <div className="stat-section">
        <div className="stat-label">Золото</div>
        <div className="stat-value">{formatGold(status.gold)}</div>
      </div>

      {/* Inventory Section */}
      <div className="stat-section inventory-section">
        <div className="stat-label">Инвентарь</div>
        {status.inventory.length === 0 ? (
          <div className="empty-inventory">
            <p>Пусто</p>
          </div>
        ) : (
          <div className="inventory-list">
            {status.inventory.map((item, idx) => (
              <div key={idx} className="inventory-item">
                <span className="item-name">{item.name}</span>
                {item.quantity > 1 && (
                  <span className="item-quantity">×{item.quantity}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .character-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    background-color: rgba(0, 0, 0, 0.3);
    overflow: hidden;
  }

  .panel-header {
    padding: 16px;
    background-color: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .panel-header h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
  }

  .location {
    margin-top: 8px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
  }

  .stat-section {
    padding: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .stat-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.6);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }

  .stat-value {
    font-size: 18px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  /* HP Display */
  .hp-display {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .hp-text {
    font-size: 18px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .hp-bar {
    width: 100%;
    height: 8px;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    overflow: hidden;
  }

  .hp-bar-fill {
    height: 100%;
    transition: width 0.3s ease, background-color 0.3s ease;
    border-radius: 4px;
  }

  /* Inventory */
  .inventory-section {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .inventory-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    max-height: 300px;
  }

  .inventory-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    transition: background-color 0.2s;
  }

  .inventory-item:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }

  .item-name {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.87);
  }

  .item-quantity {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
    background-color: rgba(255, 255, 255, 0.1);
    padding: 2px 6px;
    border-radius: 4px;
  }

  /* Empty States */
  .loading-state,
  .error-state,
  .empty-state,
  .empty-inventory {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    color: rgba(255, 255, 255, 0.5);
    font-style: italic;
    text-align: center;
  }

  .error-state {
    color: #ef4444;
  }

  .retry-button {
    margin-top: 12px;
    padding: 8px 16px;
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .retry-button:hover {
    background-color: #2563eb;
  }

  .empty-inventory p {
    margin: 0;
  }
`;
