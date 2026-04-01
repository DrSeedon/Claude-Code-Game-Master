import { useState, useEffect, useCallback } from 'react';

/**
 * Module data structure
 */
interface Module {
  id: string;
  name: string;
  description: string;
}

/**
 * ModuleSelector component props
 */
interface ModuleSelectorProps {
  onNext: (selectedModules: string[]) => void;
  onPrevious?: () => void;
  apiUrl?: string;
}

/**
 * Module selector step component for campaign wizard
 *
 * Allows user to select optional gameplay modules to enable for the campaign.
 */
export function ModuleSelector({
  onNext,
  onPrevious,
  apiUrl = '/api/modules'
}: ModuleSelectorProps) {
  const [modules, setModules] = useState<Module[]>([]);
  const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available modules
  const fetchModules = useCallback(async () => {
    try {
      const response = await fetch(apiUrl);
      const data = await response.json();

      if (Array.isArray(data)) {
        setModules(data);
      } else if (data.modules && Array.isArray(data.modules)) {
        setModules(data.modules);
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
    fetchModules();
  }, [fetchModules]);

  // Toggle module selection
  const toggleModule = (moduleId: string) => {
    const newSelected = new Set(selectedModules);
    if (newSelected.has(moduleId)) {
      newSelected.delete(moduleId);
    } else {
      newSelected.add(moduleId);
    }
    setSelectedModules(newSelected);
  };

  // Handle next step
  const handleNext = () => {
    onNext(Array.from(selectedModules));
  };

  if (isLoading) {
    return (
      <div className="wizard-step module-selector">
        <h2>Выбор модулей</h2>
        <p>Загрузка доступных модулей...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wizard-step module-selector">
        <h2>Выбор модулей</h2>
        <p className="error">⚠️ {error}</p>
        <button onClick={fetchModules}>Повторить</button>
      </div>
    );
  }

  return (
    <div className="wizard-step module-selector">
      <h2>Выбор модулей</h2>
      <p className="step-description">
        Выберите опциональные модули для расширения функциональности кампании
      </p>

      <div className="modules-list">
        {modules.length === 0 ? (
          <p>Нет доступных модулей</p>
        ) : (
          modules.map(module => (
            <label key={module.id} className="module-item">
              <input
                type="checkbox"
                checked={selectedModules.has(module.id)}
                onChange={() => toggleModule(module.id)}
              />
              <div className="module-info">
                <span className="module-name">{module.name}</span>
                <span className="module-description">{module.description}</span>
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
        <button className="btn-primary" onClick={handleNext}>
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

  .module-selector h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
  }

  .step-description {
    color: rgba(255, 255, 255, 0.6);
    margin: 0;
  }

  .modules-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 16px 0;
  }

  .module-item {
    display: flex;
    gap: 12px;
    padding: 12px;
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .module-item:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .module-item input[type="checkbox"] {
    width: 20px;
    height: 20px;
    margin-top: 2px;
    cursor: pointer;
    flex-shrink: 0;
  }

  .module-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .module-name {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
  }

  .module-description {
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

  .btn-primary:hover {
    background-color: #2563eb;
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
