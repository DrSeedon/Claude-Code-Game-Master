import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ModuleSelector } from '../components/WizardSteps/ModuleSelector';
import { NarratorSelector } from '../components/WizardSteps/NarratorSelector';
import { RulesSelector } from '../components/WizardSteps/RulesSelector';
import { CharacterCreator } from '../components/WizardSteps/CharacterCreator';

/**
 * Campaign creation data
 */
interface CampaignData {
  name: string;
  modules: string[];
  narrator: string;
  rules: string;
  character: {
    name: string;
    class: string;
    race: string;
  };
}

/**
 * Wizard page component
 *
 * Multi-step campaign creation wizard with state management and API integration.
 */
export function Wizard() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Campaign data accumulator
  const [campaignData, setCampaignData] = useState<Partial<CampaignData>>({
    modules: [],
    character: {
      name: '',
      class: '',
      race: ''
    }
  });

  // Step definitions
  const steps = [
    {
      title: 'Выбор модулей',
      component: ModuleSelector
    },
    {
      title: 'Выбор рассказчика',
      component: NarratorSelector
    },
    {
      title: 'Выбор правил',
      component: RulesSelector
    },
    {
      title: 'Создание персонажа',
      component: CharacterCreator
    }
  ];

  // Handle module selection
  const handleModulesNext = useCallback((modules: string[]) => {
    setCampaignData(prev => ({
      ...prev,
      modules
    }));
    setCurrentStep(1);
  }, []);

  // Handle narrator selection
  const handleNarratorNext = useCallback((narrator: string) => {
    setCampaignData(prev => ({
      ...prev,
      narrator
    }));
    setCurrentStep(2);
  }, []);

  // Handle rules selection
  const handleRulesNext = useCallback((rules: string) => {
    setCampaignData(prev => ({
      ...prev,
      rules
    }));
    setCurrentStep(3);
  }, []);

  // Handle character creation and campaign submission
  const handleCharacterComplete = useCallback(async (character) => {
    try {
      setIsSubmitting(true);
      setError(null);

      // Prepare campaign data
      const finalCampaignData = {
        name: `${character.name}'s Campaign`,
        modules: campaignData.modules || [],
        narrator: campaignData.narrator || 'default',
        rules: campaignData.rules || 'default',
        character
      };

      // Submit to API
      const response = await fetch('/api/campaigns', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(finalCampaignData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Ошибка при создании кампании');
      }

      const result = await response.json();

      // Navigate to game with campaign ID
      navigate(`/game?campaign=${result.id || result.campaign_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
      setIsSubmitting(false);
    }
  }, [campaignData, navigate]);

  // Handle back navigation
  const handlePrevious = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  }, [currentStep]);

  // Get current step component
  const CurrentStepComponent = steps[currentStep].component;

  return (
    <div className="wizard-page">
      {/* Progress bar */}
      <div className="wizard-progress">
        <div className="progress-header">
          <h1>Создание кампании</h1>
          <span className="progress-indicator">
            Шаг {currentStep + 1} из {steps.length}
          </span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{
              width: `${((currentStep + 1) / steps.length) * 100}%`
            }}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="wizard-container">
        {/* Error message */}
        {error && (
          <div className="error-banner">
            <p>⚠️ {error}</p>
            <button onClick={() => setError(null)}>Закрыть</button>
          </div>
        )}

        {/* Step content */}
        <div className="step-content">
          {currentStep === 0 && (
            <ModuleSelector onNext={handleModulesNext} />
          )}
          {currentStep === 1 && (
            <NarratorSelector
              onNext={handleNarratorNext}
              onPrevious={handlePrevious}
            />
          )}
          {currentStep === 2 && (
            <RulesSelector
              onNext={handleRulesNext}
              onPrevious={handlePrevious}
            />
          )}
          {currentStep === 3 && (
            <CharacterCreator
              onComplete={handleCharacterComplete}
              onPrevious={handlePrevious}
            />
          )}
        </div>

        {/* Submitting state */}
        {isSubmitting && (
          <div className="submitting-overlay">
            <div className="spinner"></div>
            <p>Создание кампании...</p>
          </div>
        )}
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .wizard-page {
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

  .wizard-progress {
    flex-shrink: 0;
    padding: 24px 32px;
    background-color: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .progress-header h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
  }

  .progress-indicator {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
  }

  .progress-bar {
    width: 100%;
    height: 4px;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
    transition: width 0.3s ease;
  }

  .wizard-container {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .error-banner {
    background-color: rgba(239, 68, 68, 0.1);
    border-bottom: 1px solid rgba(239, 68, 68, 0.3);
    padding: 16px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #fecaca;
  }

  .error-banner p {
    margin: 0;
  }

  .error-banner button {
    background-color: transparent;
    border: 1px solid rgba(239, 68, 68, 0.5);
    color: #fecaca;
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s ease;
  }

  .error-banner button:hover {
    background-color: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.8);
  }

  .step-content {
    flex: 1;
    overflow-y: auto;
  }

  .submitting-overlay {
    position: absolute;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 16px;
    z-index: 1000;
  }

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid rgba(255, 255, 255, 0.2);
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .submitting-overlay p {
    color: rgba(255, 255, 255, 0.8);
    font-size: 16px;
  }
`;
