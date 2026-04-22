import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';

interface ChoiceOption {
  id: string;
  title: string;
  description?: string;
  color: 'green' | 'yellow' | 'red';
  comment?: string;
}

interface Control {
  type: 'radio' | 'checkbox' | 'text_input';
  id: string;
  label: string;
  options?: ChoiceOption[];
  placeholder?: string;
  required?: boolean;
}

interface ChoicesData {
  step: string;
  title: string;
  controls: Control[];
  submit_label: string;
}

interface WizardMessage {
  role: 'user' | 'assistant' | 'activity';
  content: string;
}

export function Wizard() {
  const navigate = useNavigate();
  const ws = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);

  const [messages, setMessages] = useState<WizardMessage[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const streamingRef = useRef('');

  // Sidebar state
  const [choices, setChoices] = useState<ChoicesData | null>(null);
  const [selections, setSelections] = useState<Record<string, string | string[]>>({});
  const [textValues, setTextValues] = useState<Record<string, string>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mountedRef.current = true;
    const wsUrl = `ws://${window.location.host}/ws/wizard`;
    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      if (mountedRef.current) setConnected(true);
    };

    socket.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'activity') {
          // Finalize streaming text FIRST, then add activity — correct order
          const pending = streamingRef.current;
          if (pending.trim()) {
            const cleaned = pending.replace(/```tool:\w+\s*\n\{[\s\S]*?\}\s*\n```/g, '').trim();
            if (cleaned) {
              setMessages(prev => [...prev, { role: 'assistant', content: cleaned }, { role: 'activity', content: data.content }]);
            } else {
              setMessages(prev => [...prev, { role: 'activity', content: data.content }]);
            }
            streamingRef.current = '';
            setStreamingContent('');
          } else {
            setMessages(prev => [...prev, { role: 'activity', content: data.content }]);
          }
          return;
        }

        if (data.type === 'text') {
          if (!isGenerating) setIsGenerating(true);
          streamingRef.current += data.content;
          setStreamingContent(streamingRef.current);
          return;
        }

        if (data.type === 'done') {
          setIsGenerating(false);
          const pending = streamingRef.current;
          if (pending.trim()) {
            const cleaned = pending.replace(/```tool:\w+\s*\n\{[\s\S]*?\}\s*\n```/g, '').trim();
            if (cleaned) {
              setMessages(prev => [...prev, { role: 'assistant', content: cleaned }]);
            }
          }
          streamingRef.current = '';
          setStreamingContent('');
          return;
        }

        if (data.type === 'show_choices') {
          setChoices(data.data);
          setSelections({});
          setTextValues({});
          return;
        }

        if (data.type === 'clear_choices') {
          setChoices(null);
          return;
        }

        if (data.type === 'wizard_complete') {
          navigate(`/game?campaign=${data.campaign_name}`);
          return;
        }

        if (data.type === 'error') {
          setIsGenerating(false);
          setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${data.content}` }]);
        }
      } catch {
        setStreamingContent(prev => prev + event.data);
      }
    };

    socket.onerror = () => { if (mountedRef.current) setConnected(false); };
    socket.onclose = () => { if (mountedRef.current) setConnected(false); };

    return () => {
      mountedRef.current = false;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    };
  }, [navigate]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Show initial DM greeting + preset choices (no LLM call)
  // First user message includes context about visible choices
  const greetingSent = useRef(false);
  const initialContextSent = useRef(false);
  useEffect(() => {
    if (connected && !greetingSent.current) {
      greetingSent.current = true;
      setMessages([{
        role: 'assistant',
        content: 'Привет! Давай создадим кампанию.\n\nВыбери готовый сеттинг справа или опиши свой мир в чате.'
      }]);
      // Show initial concept choices
      setChoices({
        step: 'concept',
        title: 'Мир кампании',
        submit_label: 'Выбрать',
        controls: [
          {
            type: 'radio', id: 'preset', label: 'Готовые сеттинги',
            options: [
              { id: 'standard-dnd', title: 'Стандартный D&D', description: 'Классическое фэнтези — драконы, подземелья, магия', color: 'green', comment: 'Проверенная классика для любого игрока' },
              { id: 'zombie-apocalypse', title: 'Зомби-апокалипсис', description: 'Мертвецы, выживание, дефицит ресурсов', color: 'green', comment: 'Напряжение и моральные дилеммы' },
              { id: 'survival-zone', title: 'Зона выживания (STALKER)', description: 'Аномалии, радиация, артефакты, фракции', color: 'green', comment: 'Атмосфера постапока и исследование' },
              { id: 'space-travel', title: 'Космос', description: 'Корабль, экипаж, галактика, ресурсы', color: 'green', comment: 'Эпик среди звёзд' },
              { id: 'horror-investigation', title: 'Хоррор-расследование', description: 'Безумие, культы, запретное знание', color: 'yellow', comment: 'Для любителей Лавкрафта' },
              { id: 'political-intrigue', title: 'Политические интриги', description: 'Влияние, альянсы, предательства', color: 'yellow', comment: 'Война умов, а не мечей' },
              { id: 'gladiator-arena', title: 'Гладиаторская арена', description: 'Раб → бог арены, пермасмерть', color: 'yellow', comment: 'Чистый бой и прогрессия' },
              { id: 'roguelike-missions', title: 'Рогалик: База + Миссии', description: 'XCOM/Darkest Dungeon — хаб + вылазки', color: 'yellow', comment: 'Прогрессия и риск' },
              { id: 'civilization', title: 'Цивилизация', description: 'От племени до империи', color: 'yellow', comment: 'Управляешь народом, а не персонажем' },
              { id: 'monster-hunters', title: 'Охотники на монстров', description: 'Ведьмак meets Warhammer — контракты, бой', color: 'yellow', comment: 'Структурированные сессии' },
            ]
          },
          {
            type: 'text_input', id: 'custom_idea', label: 'Или опиши свой мир',
            placeholder: 'Киберпанк-детектив, пиратское фэнтези, что угодно...',
            required: false
          }
        ]
      });
    }
  }, [connected]);

  // Send message with optional hidden metadata (visible to DM but not in chat)
  const sendMessage = useCallback((text: string, meta?: string) => {
    if (!text.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN || isGenerating) return;
    // Show clean text in chat
    setMessages(prev => [...prev, { role: 'user', content: text.trim() }]);
    setIsGenerating(true);

    // Build message for DM — prepend metadata if any
    let msgToSend = text.trim();

    // First message — include sidebar context
    if (!initialContextSent.current) {
      initialContextSent.current = true;
      const presetNames = choices?.controls
        ?.flatMap(c => c.options?.map(o => o.title) || [])
        .join(', ');
      if (presetNames) {
        msgToSend = `[System: The sidebar currently shows campaign setting presets: ${presetNames}. This is step 1 — choosing the campaign world.]\n\n${msgToSend}`;
      }
    }

    if (meta) {
      msgToSend = `${meta}\n${msgToSend}`;
    }

    ws.current.send(msgToSend);
    setInput('');
  }, [isGenerating, choices]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }, [input, sendMessage]);

  // Submit sidebar choices as a message
  const handleSubmitChoices = useCallback(() => {
    if (!choices || !ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    const parts: string[] = [];
    for (const ctrl of choices.controls) {
      const label = ctrl.label || ctrl.id;
      if (ctrl.type === 'text_input') {
        const val = textValues[ctrl.id];
        if (val?.trim()) {
          parts.push(`${label}: ${val.trim()}`);
        }
      } else if (ctrl.type === 'radio') {
        const val = selections[ctrl.id];
        if (val && typeof val === 'string') {
          const opt = ctrl.options?.find(o => o.id === val);
          parts.push(`${label}: ${opt?.title || val}`);
        }
      } else if (ctrl.type === 'checkbox') {
        const vals = selections[ctrl.id];
        if (Array.isArray(vals) && vals.length > 0) {
          const names = vals.map(v => ctrl.options?.find(o => o.id === v)?.title || v);
          parts.push(`${label}: ${names.join(', ')}`);
        }
      }
    }

    if (parts.length === 0) {
      parts.push('Пропускаю этот шаг');
    }

    const displayMsg = parts.join('\n');
    sendMessage(displayMsg, `[Sidebar selection for step "${choices.step}"]`);
    setChoices(null);
  }, [choices, selections, textValues, sendMessage]);

  // Selection handlers
  const handleRadioChange = (controlId: string, optionId: string) => {
    setSelections(prev => ({ ...prev, [controlId]: optionId }));
  };

  const handleCheckboxChange = (controlId: string, optionId: string) => {
    setSelections(prev => {
      const current = (prev[controlId] as string[]) || [];
      const updated = current.includes(optionId)
        ? current.filter(id => id !== optionId)
        : [...current, optionId];
      return { ...prev, [controlId]: updated };
    });
  };

  const handleTextChange = (controlId: string, value: string) => {
    setTextValues(prev => ({ ...prev, [controlId]: value }));
  };

  const colorMap = {
    green: { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.4)', dot: '#10b981' },
    yellow: { bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.4)', dot: '#fbbf24' },
    red: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.4)', dot: '#ef4444' },
  };

  return (
    <div className="wizard-page">
      <header className="wizard-header">
        <button className="back-btn" onClick={() => navigate('/')}>&#8592; Лобби</button>
        <h1>Создание кампании</h1>
        <div className={`ws-status ${connected ? 'ws-ok' : 'ws-off'}`}>
          {connected ? 'Подключено' : 'Подключение...'}
        </div>
      </header>

      <div className="wizard-body">
        {/* Chat */}
        <div className="wizard-chat">
          <div className="messages-area">
            {messages.map((msg, i) => (
              msg.role === 'activity' ? (
                <div key={i} className="msg-activity">{msg.content}</div>
              ) : (
                <div key={i} className={`msg msg-${msg.role}`}>
                  <div className="msg-label">{msg.role === 'user' ? 'Вы' : 'DM'}</div>
                  <div className="msg-text">
                    {msg.role === 'assistant' ? <Markdown>{msg.content}</Markdown> : msg.content}
                  </div>
                </div>
              )
            ))}
            {streamingContent && (
              <div className="msg msg-assistant">
                <div className="msg-label">DM</div>
                <div className="msg-text"><Markdown>{
                  streamingContent.replace(/```tool:\w+\s*\n\{[\s\S]*?\}\s*\n```/g, '').trim()
                }</Markdown></div>
              </div>
            )}
            {isGenerating && !streamingContent && (
              <div className="generating">
                <div className="gen-bar" />
                <span>DM думает...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Напишите что-нибудь..."
              disabled={!connected || isGenerating}
            />
            <button onClick={() => sendMessage(input)} disabled={!connected || !input.trim() || isGenerating}>
              Отправить
            </button>
          </div>
        </div>

        {/* Sidebar — dynamic choices */}
        <div className="wizard-sidebar">
          {!choices ? (
            <div className="sidebar-empty">
              <p>DM покажет варианты здесь</p>
            </div>
          ) : (
            <div className="sidebar-content">
              <div className="sidebar-header">
                <h2>{choices.title}</h2>
                <span className="step-badge">{choices.step}</span>
              </div>

              <div className="controls-area">
                {choices.controls.map(ctrl => (
                  <div key={ctrl.id} className="control-group">
                    <div className="control-label">
                      {ctrl.label}
                      {ctrl.required && <span className="req">*</span>}
                    </div>

                    {ctrl.type === 'text_input' && (
                      <input
                        className="ctrl-text"
                        type="text"
                        placeholder={ctrl.placeholder || ''}
                        value={textValues[ctrl.id] || ''}
                        onChange={e => handleTextChange(ctrl.id, e.target.value)}
                      />
                    )}

                    {(ctrl.type === 'radio' || ctrl.type === 'checkbox') && ctrl.options && (
                      <div className="options-list">
                        {ctrl.options.map(opt => {
                          const colors = colorMap[opt.color];
                          const isSelected = ctrl.type === 'radio'
                            ? selections[ctrl.id] === opt.id
                            : ((selections[ctrl.id] as string[]) || []).includes(opt.id);

                          return (
                            <div
                              key={opt.id}
                              className={`option-card ${isSelected ? 'option-selected' : ''}`}
                              style={{
                                backgroundColor: isSelected ? colors.bg : 'rgba(255,255,255,0.03)',
                                borderColor: isSelected ? colors.border : 'rgba(255,255,255,0.1)',
                              }}
                              onClick={() => ctrl.type === 'radio'
                                ? handleRadioChange(ctrl.id, opt.id)
                                : handleCheckboxChange(ctrl.id, opt.id)
                              }
                            >
                              <div className="option-top">
                                <span className="color-dot" style={{ backgroundColor: colors.dot }} />
                                <span className="option-title">{opt.title}</span>
                                <span className="option-type">
                                  {ctrl.type === 'checkbox' ? (isSelected ? '☑' : '☐') : (isSelected ? '◉' : '○')}
                                </span>
                              </div>
                              {opt.description && (
                                <div className="option-desc">{opt.description}</div>
                              )}
                              {opt.comment && (
                                <div className="option-comment" style={{ color: colors.dot }}>
                                  {opt.comment}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="sidebar-footer">
                <button className="skip-btn" onClick={() => { sendMessage('Пропускаю этот шаг', `[Sidebar skip for step "${choices.step}"]`); setChoices(null); }} disabled={isGenerating}>
                  Пропустить
                </button>
                <button className="submit-btn" onClick={handleSubmitChoices} disabled={isGenerating}>
                  {choices.submit_label}
                </button>
              </div>
            </div>
          )}
        </div>
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
  .wizard-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 24px;
    background: rgba(0,0,0,0.3);
    border-bottom: 1px solid rgba(255,255,255,0.1);
    flex-shrink: 0;
  }
  .wizard-header h1 { margin: 0; font-size: 22px; font-weight: 700; flex: 1; }
  .back-btn {
    padding: 6px 14px;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 6px;
    color: rgba(255,255,255,0.8);
    cursor: pointer;
    font-size: 14px;
  }
  .back-btn:hover { background: rgba(255,255,255,0.15); }
  .ws-status { font-size: 12px; padding: 4px 10px; border-radius: 12px; }
  .ws-ok { background: rgba(16,185,129,0.2); color: #10b981; }
  .ws-off { background: rgba(251,191,36,0.2); color: #fbbf24; }

  .wizard-body { flex: 1; display: flex; overflow: hidden; }

  /* Chat */
  .wizard-chat { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .messages-area {
    flex: 1; overflow-y: auto; overflow-x: hidden; padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .msg { display: flex; flex-direction: column; gap: 4px; max-width: 85%; }
  .msg-user { align-self: flex-end; align-items: flex-end; }
  .msg-assistant { align-self: flex-start; align-items: flex-start; }
  .msg-label {
    font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.5);
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .msg-text {
    padding: 10px 14px; border-radius: 12px; line-height: 1.5;
    white-space: pre-wrap; word-wrap: break-word; word-break: break-word;
    overflow-wrap: break-word; overflow-x: hidden;
    font-size: 14px; max-width: 100%;
  }
  .msg-text p { margin: 0 0 8px 0; }
  .msg-text p:last-child { margin: 0; }
  .msg-text ul, .msg-text ol { margin: 4px 0; padding-left: 20px; }
  .msg-text strong { color: rgba(255,255,255,1); }
  .msg-user .msg-text { background: #3b82f6; color: white; }
  .msg-assistant .msg-text { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.87); }
  .msg-activity {
    align-self: flex-start;
    font-size: 12px; font-family: monospace;
    color: rgba(255,255,255,0.35);
    padding: 2px 12px;
    max-width: 90%;
    word-break: break-all;
    white-space: pre-wrap;
  }

  .input-area {
    display: flex; gap: 8px; padding: 16px;
    background: rgba(0,0,0,0.2); border-top: 1px solid rgba(255,255,255,0.1);
  }
  .input-area input {
    flex: 1; padding: 10px 14px;
    background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px; color: rgba(255,255,255,0.87); font-size: 14px; outline: none;
  }
  .input-area input:focus { border-color: #3b82f6; }
  .input-area input:disabled { opacity: 0.5; }
  .input-area input::placeholder { color: rgba(255,255,255,0.4); }
  .input-area button {
    padding: 10px 20px; background: #3b82f6; color: white;
    border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
  }
  .input-area button:hover:not(:disabled) { background: #2563eb; }
  .input-area button:disabled { opacity: 0.5; cursor: not-allowed; }

  .generating {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 16px; color: rgba(255,255,255,0.5); font-size: 13px;
  }
  .gen-bar {
    width: 40px; height: 3px; background: rgba(59,130,246,0.3);
    border-radius: 2px; overflow: hidden; position: relative;
  }
  .gen-bar::after {
    content: ''; position: absolute; top: 0; left: -40px;
    width: 40px; height: 100%; background: #3b82f6; border-radius: 2px;
    animation: gen-slide 1s ease-in-out infinite;
  }
  @keyframes gen-slide { 0% { left: -40px; } 100% { left: 40px; } }

  /* Sidebar */
  .wizard-sidebar {
    width: 380px; border-left: 1px solid rgba(255,255,255,0.1);
    display: flex; flex-direction: column; background: rgba(0,0,0,0.2); flex-shrink: 0;
  }
  .sidebar-empty {
    flex: 1; display: flex; align-items: center; justify-content: center;
    color: rgba(255,255,255,0.3); font-size: 14px; padding: 32px;
    text-align: center;
  }
  .sidebar-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .sidebar-header {
    padding: 16px 16px 12px; border-bottom: 1px solid rgba(255,255,255,0.1);
    display: flex; align-items: center; gap: 10px;
  }
  .sidebar-header h2 { margin: 0; font-size: 16px; font-weight: 700; flex: 1; }
  .step-badge {
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    background: rgba(59,130,246,0.2); color: #3b82f6; font-weight: 600;
  }

  .controls-area { flex: 1; overflow-y: auto; padding: 12px; }
  .control-group { margin-bottom: 16px; }
  .control-label {
    font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.7);
    margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.3px;
  }
  .req { color: #ef4444; margin-left: 4px; }

  .ctrl-text {
    width: 100%; padding: 10px 12px; box-sizing: border-box;
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px; color: rgba(255,255,255,0.9); font-size: 14px; outline: none;
  }
  .ctrl-text:focus { border-color: #3b82f6; }
  .ctrl-text::placeholder { color: rgba(255,255,255,0.35); }

  .options-list { display: flex; flex-direction: column; gap: 6px; }
  .option-card {
    padding: 10px 12px; border: 1.5px solid rgba(255,255,255,0.1);
    border-radius: 8px; cursor: pointer; transition: all 0.15s ease;
  }
  .option-card:hover { transform: translateY(-1px); }
  .option-selected { transform: translateY(-1px); }
  .option-top { display: flex; align-items: center; gap: 8px; }
  .color-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .option-title { font-size: 13px; font-weight: 600; flex: 1; }
  .option-type { font-size: 14px; color: rgba(255,255,255,0.4); }
  .option-desc { font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 4px; line-height: 1.3; }
  .option-comment {
    font-size: 11px; margin-top: 4px; font-weight: 500;
    line-height: 1.3;
  }

  .sidebar-footer {
    padding: 12px 16px; border-top: 1px solid rgba(255,255,255,0.1);
    display: flex; gap: 8px;
  }
  .skip-btn {
    padding: 8px 16px; background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
    color: rgba(255,255,255,0.6); font-size: 13px; cursor: pointer;
  }
  .skip-btn:hover { background: rgba(255,255,255,0.12); }
  .submit-btn {
    flex: 1; padding: 10px 16px; background: #3b82f6; color: white;
    border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer;
  }
  .submit-btn:hover:not(:disabled) { background: #2563eb; }
  .submit-btn:disabled, .skip-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  @media (max-width: 768px) {
    .wizard-body { flex-direction: column; }
    .wizard-sidebar {
      width: 100%; height: 45vh;
      border-left: none; border-top: 1px solid rgba(255,255,255,0.1);
    }
  }
`;
