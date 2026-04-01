import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CharacterStatus, isValidCharacterStatus } from '../types';

/**
 * Dashboard page component
 *
 * Campaign management dashboard with tabbed interface showing:
 * - Wiki: Campaign lore and reference material
 * - Map: Campaign map viewer
 * - Stats: Character statistics and campaign info
 */
export function Dashboard() {
  const [searchParams] = useSearchParams();
  const campaignId = searchParams.get('campaign');
  const [activeTab, setActiveTab] = useState<'wiki' | 'map' | 'stats'>('stats');
  const [characterStatus, setCharacterStatus] = useState<CharacterStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch character status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/status${campaignId ? `?campaign=${campaignId}` : ''}`);
      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setCharacterStatus(null);
      } else if (isValidCharacterStatus(data)) {
        setCharacterStatus(data);
        setError(null);
      } else {
        setError('Неверный формат данных');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки');
    } finally {
      setIsLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return (
    <div className="dashboard-page">
      {/* Header */}
      <header className="dashboard-header">
        <h1>Кампания</h1>
        <div className="header-actions">
          <button className="btn-icon" title="Сохранить">
            💾
          </button>
          <button className="btn-icon" title="Настройки">
            ⚙️
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="dashboard-tabs">
        <button
          className={`tab ${activeTab === 'wiki' ? 'active' : ''}`}
          onClick={() => setActiveTab('wiki')}
        >
          📖 Вики
        </button>
        <button
          className={`tab ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => setActiveTab('map')}
        >
          🗺️ Карта
        </button>
        <button
          className={`tab ${activeTab === 'stats' ? 'active' : ''}`}
          onClick={() => setActiveTab('stats')}
        >
          📊 Статистика
        </button>
      </div>

      {/* Content */}
      <main className="dashboard-content">
        {error && (
          <div className="error-message">
            <p>⚠️ {error}</p>
            <button onClick={fetchStatus}>Повторить</button>
          </div>
        )}

        {!error && isLoading && (
          <div className="loading-state">
            <p>Загрузка данных...</p>
          </div>
        )}

        {!error && !isLoading && activeTab === 'wiki' && (
          <WikiTab />
        )}

        {!error && !isLoading && activeTab === 'map' && (
          <MapTab />
        )}

        {!error && !isLoading && activeTab === 'stats' && (
          <StatsTab status={characterStatus} />
        )}
      </main>

      <style>{styles}</style>
    </div>
  );
}

/**
 * Wiki tab component
 */
function WikiTab() {
  return (
    <div className="tab-content wiki-tab">
      <h2>Вики кампании</h2>
      <div className="wiki-sections">
        <div className="wiki-section">
          <h3>📚 О мире</h3>
          <p>Информация о мире и сеттинге кампании появится здесь.</p>
        </div>
        <div className="wiki-section">
          <h3>👥 Персонажи и НПС</h3>
          <p>Описание важных персонажей и НПС появится здесь.</p>
        </div>
        <div className="wiki-section">
          <h3>⚔️ Враги и существа</h3>
          <p>Информация о врагах и существах появится здесь.</p>
        </div>
        <div className="wiki-section">
          <h3>💎 Артефакты и вещи</h3>
          <p>Каталог магических вещей и артефактов появится здесь.</p>
        </div>
      </div>
    </div>
  );
}

/**
 * Map tab component
 */
function MapTab() {
  return (
    <div className="tab-content map-tab">
      <h2>Карта кампании</h2>
      <div className="map-placeholder">
        <div className="map-grid">
          {Array.from({ length: 25 }).map((_, i) => (
            <div key={i} className="map-cell"></div>
          ))}
        </div>
        <p>Карта кампании загружается здесь</p>
      </div>
    </div>
  );
}

/**
 * Stats tab component
 */
function StatsTab({ status }: { status: CharacterStatus | null }) {
  if (!status) {
    return (
      <div className="tab-content stats-tab">
        <p>Нет данных персонажа</p>
      </div>
    );
  }

  const hpPercentage = Math.round((status.hp / status.max_hp) * 100);

  const formatGold = (copper: number): string => {
    const gold = Math.floor(copper / 100);
    const silver = Math.floor((copper % 100) / 10);
    const copperRemainder = copper % 10;

    const parts: string[] = [];
    if (gold > 0) parts.push(`${gold}з`);
    if (silver > 0) parts.push(`${silver}с`);
    if (copperRemainder > 0) parts.push(`${copperRemainder}м`);

    return parts.join(' ') || '0м';
  };

  return (
    <div className="tab-content stats-tab">
      <h2>Статистика персонажа</h2>

      <div className="stats-grid">
        {/* Character Info */}
        <section className="stat-section">
          <h3>Информация</h3>
          <div className="stat-item">
            <span className="label">Имя:</span>
            <span className="value">{status.name}</span>
          </div>
          {status.location && (
            <div className="stat-item">
              <span className="label">Локация:</span>
              <span className="value">{status.location}</span>
            </div>
          )}
        </section>

        {/* Health */}
        <section className="stat-section">
          <h3>Здоровье</h3>
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
            <div className="hp-percentage">{hpPercentage}%</div>
          </div>
        </section>

        {/* Experience */}
        <section className="stat-section">
          <h3>Опыт</h3>
          <div className="stat-item">
            <span className="label">Очки опыта:</span>
            <span className="value">{status.xp} XP</span>
          </div>
        </section>

        {/* Gold */}
        <section className="stat-section">
          <h3>Золото</h3>
          <div className="stat-item">
            <span className="label">Деньги:</span>
            <span className="value">{formatGold(status.gold)}</span>
          </div>
        </section>

        {/* Inventory */}
        <section className="stat-section full-width">
          <h3>Инвентарь</h3>
          {status.inventory.length === 0 ? (
            <p className="empty-message">Инвентарь пуст</p>
          ) : (
            <div className="inventory-list">
              {status.inventory.map((item, idx) => (
                <div key={idx} className="inventory-item">
                  <span className="item-name">{item.name}</span>
                  {item.quantity > 1 && (
                    <span className="item-qty">×{item.quantity}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

const styles = `
  .dashboard-page {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
    margin: 0;
    padding: 0;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: rgba(255, 255, 255, 0.95);
    overflow: hidden;
  }

  .dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 32px;
    background-color: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    flex-shrink: 0;
  }

  .dashboard-header h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  .btn-icon {
    background-color: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: rgba(255, 255, 255, 0.8);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-icon:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.3);
  }

  .dashboard-tabs {
    display: flex;
    padding: 0 32px;
    background-color: rgba(0, 0, 0, 0.2);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    gap: 8px;
    flex-shrink: 0;
    overflow-x: auto;
  }

  .tab {
    padding: 12px 20px;
    background-color: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .tab:hover {
    color: rgba(255, 255, 255, 0.9);
    border-bottom-color: rgba(255, 255, 255, 0.3);
  }

  .tab.active {
    color: rgba(255, 255, 255, 0.95);
    border-bottom-color: #3b82f6;
  }

  .dashboard-content {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
  }

  .tab-content {
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .tab-content h2 {
    margin: 0 0 24px 0;
    font-size: 24px;
    font-weight: 700;
  }

  /* Wiki Tab */
  .wiki-sections {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
  }

  .wiki-section {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 20px;
  }

  .wiki-section h3 {
    margin: 0 0 12px 0;
    font-size: 16px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .wiki-section p {
    margin: 0;
    color: rgba(255, 255, 255, 0.6);
    line-height: 1.6;
  }

  /* Map Tab */
  .map-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 40px;
    min-height: 400px;
  }

  .map-grid {
    display: grid;
    grid-template-columns: repeat(5, 60px);
    gap: 8px;
  }

  .map-cell {
    width: 60px;
    height: 60px;
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }

  .map-placeholder p {
    color: rgba(255, 255, 255, 0.6);
  }

  /* Stats Tab */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
  }

  .stat-section {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 20px;
  }

  .stat-section.full-width {
    grid-column: 1 / -1;
  }

  .stat-section h3 {
    margin: 0 0 16px 0;
    font-size: 16px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .stat-item:last-child {
    border-bottom: none;
  }

  .stat-item .label {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
  }

  .stat-item .value {
    color: rgba(255, 255, 255, 0.95);
    font-weight: 600;
  }

  .hp-display {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .hp-text {
    font-size: 16px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .hp-bar {
    width: 100%;
    height: 12px;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    overflow: hidden;
  }

  .hp-bar-fill {
    height: 100%;
    transition: width 0.3s ease;
    border-radius: 6px;
  }

  .hp-percentage {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
  }

  .inventory-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .inventory-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    font-size: 14px;
  }

  .item-name {
    color: rgba(255, 255, 255, 0.9);
  }

  .item-qty {
    color: rgba(255, 255, 255, 0.5);
    font-size: 12px;
  }

  .empty-message {
    color: rgba(255, 255, 255, 0.5);
    font-style: italic;
    margin: 0;
  }

  .error-message {
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 16px;
    border-radius: 8px;
    color: #fecaca;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .error-message p {
    margin: 0;
  }

  .error-message button {
    background-color: transparent;
    border: 1px solid rgba(239, 68, 68, 0.5);
    color: #fecaca;
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .error-message button:hover {
    background-color: rgba(239, 68, 68, 0.1);
  }

  .loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: rgba(255, 255, 255, 0.6);
  }
`;
