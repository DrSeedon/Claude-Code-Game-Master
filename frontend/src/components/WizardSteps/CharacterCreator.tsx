import { useState, useCallback } from 'react';

/**
 * Character data structure
 */
interface CharacterData {
  name: string;
  class: string;
  race: string;
}

/**
 * CharacterCreator component props
 */
interface CharacterCreatorProps {
  onComplete: (character: CharacterData) => void;
  onPrevious?: () => void;
}

/**
 * Character creator step component for campaign wizard
 *
 * Allows user to create their character with name, class, and race.
 */
export function CharacterCreator({
  onComplete,
  onPrevious
}: CharacterCreatorProps) {
  const [character, setCharacter] = useState<CharacterData>({
    name: '',
    class: '',
    race: ''
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  // Available character classes and races
  const classes = ['Fighter', 'Wizard', 'Rogue', 'Cleric', 'Barbarian', 'Ranger'];
  const races = ['Human', 'Elf', 'Dwarf', 'Halfling', 'Dragonborn', 'Tiefling'];

  // Validate form
  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!character.name.trim()) {
      newErrors.name = 'Введите имя персонажа';
    }
    if (!character.class) {
      newErrors.class = 'Выберите класс';
    }
    if (!character.race) {
      newErrors.race = 'Выберите расу';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle field change
  const handleChange = (field: keyof CharacterData, value: string) => {
    setCharacter(prev => ({
      ...prev,
      [field]: value
    }));
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: ''
      }));
    }
  };

  // Handle form submission
  const handleComplete = useCallback(() => {
    if (validate()) {
      onComplete(character);
    }
  }, [character, onComplete]);

  return (
    <div className="wizard-step character-creator">
      <h2>Создание персонажа</h2>
      <p className="step-description">
        Установите параметры вашего персонажа
      </p>

      <form className="character-form" onSubmit={e => {
        e.preventDefault();
        handleComplete();
      }}>
        {/* Character Name */}
        <div className="form-group">
          <label htmlFor="character-name">Имя персонажа</label>
          <input
            id="character-name"
            type="text"
            value={character.name}
            onChange={e => handleChange('name', e.target.value)}
            placeholder="Введите имя персонажа"
            className={errors.name ? 'error' : ''}
          />
          {errors.name && <span className="error-message">{errors.name}</span>}
        </div>

        {/* Character Class */}
        <div className="form-group">
          <label htmlFor="character-class">Класс</label>
          <select
            id="character-class"
            value={character.class}
            onChange={e => handleChange('class', e.target.value)}
            className={errors.class ? 'error' : ''}
          >
            <option value="">Выберите класс...</option>
            {classes.map(cls => (
              <option key={cls} value={cls}>
                {cls}
              </option>
            ))}
          </select>
          {errors.class && <span className="error-message">{errors.class}</span>}
        </div>

        {/* Character Race */}
        <div className="form-group">
          <label htmlFor="character-race">Раса</label>
          <select
            id="character-race"
            value={character.race}
            onChange={e => handleChange('race', e.target.value)}
            className={errors.race ? 'error' : ''}
          >
            <option value="">Выберите расу...</option>
            {races.map(race => (
              <option key={race} value={race}>
                {race}
              </option>
            ))}
          </select>
          {errors.race && <span className="error-message">{errors.race}</span>}
        </div>

        <div className="wizard-buttons">
          {onPrevious && (
            <button type="button" className="btn-secondary" onClick={onPrevious}>
              Назад
            </button>
          )}
          <button type="submit" className="btn-primary">
            Создать кампанию
          </button>
        </div>
      </form>

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

  .character-creator h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.95);
  }

  .step-description {
    color: rgba(255, 255, 255, 0.6);
    margin: 0;
  }

  .character-form {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin: 16px 0;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .form-group label {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
    font-size: 14px;
  }

  .form-group input,
  .form-group select {
    padding: 10px 12px;
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.9);
    font-size: 14px;
    transition: all 0.2s ease;
  }

  .form-group input::placeholder {
    color: rgba(255, 255, 255, 0.4);
  }

  .form-group input:focus,
  .form-group select:focus {
    outline: none;
    border-color: #3b82f6;
    background-color: rgba(255, 255, 255, 0.15);
  }

  .form-group input.error,
  .form-group select.error {
    border-color: #ef4444;
  }

  .error-message {
    font-size: 12px;
    color: #fecaca;
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
`;
