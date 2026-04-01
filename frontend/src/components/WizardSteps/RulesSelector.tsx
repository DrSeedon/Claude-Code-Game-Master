import { useState, useEffect, useCallback } from 'react';

/**
 * Rules set data structure
 */
interface RulesSet {
  id: string;
  name: string;
  description: string;
}

/**
 * RulesSelector component props
 */
interface RulesSelectorProps {
  onNext: (rules: string) => void;
  onPrevious?: () => void;
  apiUrl?: string;
}

/**
 * Rules selector step component for campaign wizard
 *
 * Allows user to select the rule set for the campaign.
 */
export function RulesSelector({
  onNext,
  onPrevious,
  apiUrl = '/api/rules'
}: RulesSelectorProps) {
  const [rules, setRules] = useState<RulesSet[]>([]);
  const [selectedRules, setSelectedRules] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available rule sets
  const fetchRules = useCallback(async () => {
    try {
      const response = await fetch(apiUrl);
      const data = await response.json();

      if (Array.isArray(data)) {
        setRules(data);
        if (data.length > 0) {
          setSelectedRules(data[0].id);
        }
      } else if (data.rules && Array.isArray(data.rules)) {
        setRules(data.rules);
        if (data.rules.length > 0) {
          setSelectedRules(data.rules[0].id);
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
    fetchRules();
  }, [fetchRules]);

  // Handle next step
  const handleNext = () => {
    if (selectedRules) {
      onNext(selectedRules);
    }
  };

  if (isLoading) {
    return (
      <div className="wizard-step rules-selector">
        <h2>Выбор правил</h2>
        <p>Загрузка доступных наборов правил...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wizard-step rules-selector">
        <h2>Выбор правил</h2>
        <p className="error">⚠️ {error}</p>
        <button onClick={fetchRules}>Повторить</button>
      </div>
    );
  }

  return (
    <div className="wizard-step rules-selector">
      <h2>Выбор системы правил</h2>
      <p className="step-description">
        Выберите систему правил для вашей кампании
      </p>

      <div className="rules-list">
        {rules.length === 0 ? (
          <p>Нет доступных наборов правил</p>
        ) : (
          rules.map(ruleSet => (
            <label key={ruleSet.id} className="rules-item">
              <input
                type="radio"
                name="rules"
                value={ruleSet.id}
                checked={selectedRules === ruleSet.id}
                onChange={() => setSelectedRules(ruleSet.id)}
              />
              <div className="rules-info">
                <span className="rules-name">{ruleSet.name}</span>
                <span className="rules-description">{ruleSet.description}</span>
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
        <button className="btn-primary" onClick={handleNext} disabled={!selectedRules}>
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

  .rules-selector h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
  }

  .step-description {
    color: rgba(255, 255, 255, 0.6);
    margin: 0;
  }

  .rules-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 16px 0;
  }

  .rules-item {
    display: flex;
    gap: 12px;
    padding: 12px;
    background-color: rgba(255, 255, 255, 0.05);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .rules-item:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .rules-item input[type="radio"] {
    width: 20px;
    height: 20px;
    margin-top: 2px;
    cursor: pointer;
    flex-shrink: 0;
  }

  .rules-item input[type="radio"]:checked + .rules-info {
    color: #3b82f6;
  }

  .rules-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .rules-name {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .rules-description {
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
