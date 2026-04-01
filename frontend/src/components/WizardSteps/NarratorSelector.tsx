import { useState, useEffect, useCallback } from 'react';

/**
 * Narrator style data structure
 */
interface NarratorStyle {
  id: string;
  name: string;
  description: string;
}

/**
 * NarratorSelector component props
 */
interface NarratorSelectorProps {
  onNext: (narrador: string) => void;
  onPrevious?: () => void;
  apiUrl?: string;
}

/**
 * Narrator selector step component for campaign wizard
 *
 * Allows user to select the narrator style for the DM.
 */
export function NarratorSelector({
  onNext,
  onPrevious,
  apiUrl = '/api/narrators'
}: NarratorSelectorProps) {
  const [narrators, setNarrators] = useState<NarratorStyle[]>([]);
  const [selectedNarrator, setSelectedNarrator] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available narrator styles
  const fetchNarrators = useCallback(async () => {
    try {
      const response = await fetch(apiUrl);
      const data = await response.json();

      if (Array.isArray(data)) {
        setNarrators(data);
        if (data.length > 0) {
          setSelectedNarrator(data[0].id);
        }
      } else if (data.narrators && Array.isArray(data.narrators)) {
        setNarrators(data.narrators);
        if (data.narrators.length > 0) {
          setSelectedNarrator(data.narrators[0].id);
        }
      } else {
        setError('Неверный формат данных');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки');
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchNarrators();
  }, [fetchNarrators]);

  // Handle next step
  const handleNext = () => {
    if (selectedNarrator) {
      onNext(selectedNarrator);
    }
  };

  if (isLoading) {
    return (
      <div className="wizard-step narrator-selector">
        <h2>Выбор рассказчика</h2>
        <p>Загрузка доступных стилей...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wizard-step narrator-selector">
        <h2>Выбор рассказчика</h2>
        <p className="error">⚠️ {error}</p>
        <button onClick={fetchNarrators}>Повторить</button>
      </div>
    );
  }

  return (
    <div className="wizard-step narrator-selector">
      <h2>Выбор стиля рассказчика</h2>
      <p className="step-description">
        Выберите стиль повествования для вашего DM
      </p>

      <div className="narrators-grid">
        {narrators.length === 0 ? (
          <p>Нет доступных стилей</p>
        ) : (
          narrators.map(narrator => (
            <label
              key={narrator.id}
              className={`narrator-card ${selectedNarrator === narrator.id ? 'selected' : ''}`}
            >
              <input
                type="radio"
                name="narrator"
                value={narrator.id}
                checked={selectedNarrator === narrator.id}
                onChange={() => setSelectedNarrator(narrator.id)}
              />
              <div className="card-content">
                <span className="narrator-name">{narrator.name}</span>
                <span className="narrator-description">{narrator.description}</span>
              </div>
            </label>
          ))
        )}
      </div>

      <div className="wizard-buttons">
        {onPrevious && (
          <button className="btn-secondary" onClick={onPrevious}>
            Назад
          </button>
        )}
        <button className="btn-primary" onClick={handleNext} disabled={!selectedNarrator}>
          Далее
        </button>
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .wizard-step {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 32px;
  }

  .narrator-selector h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
  }

  .step-description {
    color: rgba(255, 255, 255, 0.6);
    margin: 0;
  }

  .narrators-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin: 16px 0;
  }

  .narrator-card {
    position: relative;
    padding: 16px;
    background-color: rgba(255, 255, 255, 0.05);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .narrator-card:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .narrator-card.selected {
    background-color: rgba(59, 130, 246, 0.1);
    border-color: #3b82f6;
  }

  .narrator-card input[type="radio"] {
    width: 20px;
    height: 20px;
    cursor: pointer;
    flex-shrink: 0;
  }

  .card-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .narrator-name {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .narrator-description {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
  }

  .wizard-buttons {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 24px;
  }

  .btn-primary,
  .btn-secondary {
    padding: 10px 24px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-primary {
    background-color: #3b82f6;
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: #2563eb;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background-color: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .btn-secondary:hover {
    background-color: rgba(255, 255, 255, 0.15);
  }

  .error {
    color: #fecaca;
  }
`;
