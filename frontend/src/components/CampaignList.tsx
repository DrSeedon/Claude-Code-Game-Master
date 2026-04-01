import { useState, useEffect, useCallback } from 'react';

/**
 * Campaign data structure
 */
interface Campaign {
  id: string;
  name: string;
  last_played?: string;
  created_at?: string;
}

/**
 * CampaignList component props
 */
interface CampaignListProps {
  apiUrl?: string;
  refreshInterval?: number;
}

/**
 * Campaign list component
 *
 * Displays available campaigns as cards with name and last played date.
 * Fetches campaign list from backend API.
 */
export function CampaignList({
  apiUrl = '/api/campaigns',
  refreshInterval = 5000
}: CampaignListProps) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch campaigns from API
  const fetchCampaigns = useCallback(async () => {
    try {
      const response = await fetch(apiUrl);
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
  }, [apiUrl]);

  // Fetch on mount
  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  // Poll for updates
  useEffect(() => {
    const intervalId = setInterval(fetchCampaigns, refreshInterval);
    return () => clearInterval(intervalId);
  }, [fetchCampaigns, refreshInterval]);

  // Format date for display
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
      <div className="campaign-list">
        <div className="loading-state">
          <p>Загрузка кампаний...</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="campaign-list">
        <div className="error-state">
          <p>⚠️ {error}</p>
          <button onClick={fetchCampaigns} className="retry-button">
            Повторить
          </button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // Empty state
  if (campaigns.length === 0) {
    return (
      <div className="campaign-list">
        <div className="empty-state">
          <p>Нет активных кампаний</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // Campaign list render
  return (
    <div className="campaign-list">
      <div className="campaigns-grid">
        {campaigns.map(campaign => (
          <div key={campaign.id} className="campaign-card">
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
              {campaign.created_at && (
                <div className="campaign-info">
                  <span className="info-label">Создана:</span>
                  <span className="info-value">
                    {formatDate(campaign.created_at)}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .campaign-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    padding: 16px;
    overflow: hidden;
  }

  .campaigns-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    overflow-y: auto;
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
    background-color: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  .card-header {
    padding: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background-color: rgba(0, 0, 0, 0.2);
  }

  .campaign-name {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .card-body {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .campaign-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .info-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.6);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .info-value {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.85);
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
    font-style: italic;
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
`;
