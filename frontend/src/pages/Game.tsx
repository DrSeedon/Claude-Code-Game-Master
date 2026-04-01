import { useSearchParams, useNavigate } from 'react-router-dom';
import { Chat } from '../components/Chat';
import { CharacterPanel } from '../components/CharacterPanel';

/**
 * Game page component
 *
 * Main game screen displaying chat interface and character panel side-by-side.
 * Uses flexbox layout with chat taking the main area and character panel as fixed-width sidebar.
 */
export function Game() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const campaignId = searchParams.get('campaign');

  // Check if campaign is selected
  if (!campaignId) {
    return (
      <div className="game-page error-state">
        <div className="error-content">
          <h2>Кампания не выбрана</h2>
          <p>Пожалуйста, выберите кампанию из лобби для начала игры.</p>
          <button onClick={() => navigate('/')}>Вернуться в лобби</button>
        </div>
        <style>{errorStyles}</style>
      </div>
    );
  }

  return (
    <div className="game-page">
      {/* Main chat area - takes remaining space */}
      <main className="main-content">
        <Chat wsUrl={`/ws/game?campaign=${campaignId}`} />
      </main>

      {/* Character panel sidebar - fixed width on the right */}
      <aside className="sidebar">
        <CharacterPanel apiUrl={`/api/status?campaign=${campaignId}`} />
      </aside>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .game-page {
    display: flex;
    height: 100vh;
    width: 100vw;
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  }

  .main-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background-color: rgba(0, 0, 0, 0.2);
  }

  .sidebar {
    width: 320px;
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background-color: rgba(0, 0, 0, 0.3);
  }

  /* Responsive: Stack vertically on small screens */
  @media (max-width: 768px) {
    .game-page {
      flex-direction: column;
    }

    .sidebar {
      width: 100%;
      height: 40vh;
      border-left: none;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .main-content {
      height: 60vh;
    }
  }
`;

const errorStyles = `
  .game-page {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    width: 100vw;
    margin: 0;
    padding: 0;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  }

  .error-state {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .error-content {
    text-align: center;
    padding: 32px;
    background-color: rgba(0, 0, 0, 0.3);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    max-width: 400px;
  }

  .error-content h2 {
    margin: 0 0 16px 0;
    font-size: 24px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
  }

  .error-content p {
    margin: 0 0 24px 0;
    color: rgba(255, 255, 255, 0.6);
    line-height: 1.6;
  }

  .error-content button {
    padding: 10px 24px;
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.2s ease;
  }

  .error-content button:hover {
    background-color: #2563eb;
  }
`;
