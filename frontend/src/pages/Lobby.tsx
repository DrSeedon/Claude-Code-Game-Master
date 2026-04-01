import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Campaign data structure
 */
interface Campaign {
  id: string;
  name: string;
  last_played?: string;
}

/**
 * Lobby page component
 *
 * Main entry point showing available campaigns and allowing creation of new ones.
 * Users can select a campaign to start playing or create a new one.
 */
export function Lobby() {
  const navigate = useNavigate();

  // Handle campaign selection - navigate to game screen
  const handleCampaignSelect = useCallback((campaignId: string) => {
    // Navigate to game screen with campaign ID in URL or state
    navigate(`/game?campaign=${campaignId}`);
  }, [navigate]);

  // Handle create new campaign - navigate to wizard
  const handleCreateNew = useCallback(() => {
    navigate('/wizard');
  }, [navigate]);

  return (
    <div className="lobby-page">
      {/* Header section */}
      <header className="lobby-header">
        <div className="header-content">
          <h1 className="title">DM Game Master</h1>
          <p className="subtitle">Выберите кампанию или создайте новую</p>
        </div>
        <button
          className="create-button"
          onClick={handleCreateNew}
          title="Создать новую кампанию"
        >
          <span className="button-icon">+</span>
          <span className="button-text">Новая кампания</span>
        </button>
      </header>

      {/* Campaign list section */}
      <main className="lobby-main">
        <CampaignListWithNavigation onSelectCampaign={handleCampaignSelect} />
      </main>

      <style>{styles}</style>
    </div>
  );
}

/**
 * Wrapper component that adds navigation to CampaignList
 */
function CampaignListWithNavigation({
  onSelectCampaign
}: {
  onSelectCampaign: (campaignId: string) => void;
}) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch campaigns
  const fetchCampaigns = useCallback(async () => {
    try {
      const response = await fetch('/api/campaigns');
      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setCampaigns([]);
      } else if (Array.isArray(data)) {
        setCampaigns(data);
        setError(null);
      } else if (data.campaigns && Array.isArray(data.campaigns)) {
        setCampaigns(data.campaigns);
        setError(null);
      } else {
        setError('Неверный формат данных');
        setCampaigns([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки данных');
      setCampaigns([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampaigns();
    const interval = setInterval(fetchCampaigns, 5000);
    return () => clearInterval(interval);
  }, [fetchCampaigns]);

  const formatDate = (dateStr?: string): string => {
    if (!dateStr) return 'Никогда';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('ru-RU');
    } catch {
      return dateStr;
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="campaigns-container">
        <div className="loading-state">
          <p>Загрузка кампаний...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="campaigns-container">
        <div className="error-state">
          <p>⚠️ {error}</p>
          <button onClick={fetchCampaigns} className="retry-button">
            Повторить
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (campaigns.length === 0) {
    return (
      <div className="campaigns-container">
        <div className="empty-state">
          <p>Нет активных кампаний</p>
          <p className="empty-hint">Создайте новую кампанию для начала</p>
        </div>
      </div>
    );
  }

  // Campaign list
  return (
    <div className="campaigns-container">
      <div className="campaigns-grid">
        {campaigns.map(campaign => (
          <div
            key={campaign.id}
            className="campaign-card"
            onClick={() => onSelectCampaign(campaign.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelectCampaign(campaign.id);
              }
            }}
          >
            <div className="card-header">
              <h3 className="campaign-name">{campaign.name}</h3>
            </div>
            <div className="card-body">
              <div className="campaign-info">
                <span className="info-label">Последняя игра:</span>
                <span className="info-value">
                  {formatDate(campaign.last_played)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = `
  .lobby-page {
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

  .lobby-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 24px 32px;
    background-color: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    flex-shrink: 0;
  }

  .header-content {
    flex: 1;
  }

  .title {
    margin: 0;
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .subtitle {
    margin: 8px 0 0 0;
    font-size: 16px;
    color: rgba(255, 255, 255, 0.6);
  }

  .create-button {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .create-button:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(59, 130, 246, 0.3);
  }

  .create-button:active {
    transform: translateY(0);
  }

  .button-icon {
    font-size: 20px;
    font-weight: 700;
  }

  .button-text {
    display: none;
  }

  @media (min-width: 768px) {
    .button-text {
      display: inline;
    }
  }

  .lobby-main {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .campaigns-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 24px;
    overflow-y: auto;
  }

  .campaigns-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }

  .campaign-card {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.2s ease;
    cursor: pointer;
  }

  .campaign-card:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  }

  .campaign-card:focus {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
  }

  .card-header {
    padding: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background-color: rgba(0, 0, 0, 0.2);
  }

  .campaign-name {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .card-body {
    padding: 16px;
  }

  .campaign-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .info-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.5);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .info-value {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.8);
  }

  .loading-state,
  .error-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: rgba(255, 255, 255, 0.5);
    text-align: center;
  }

  .error-state {
    color: #fecaca;
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

  .empty-hint {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.4);
    margin-top: 8px;
  }
`;
