import React from 'react'
import ReactDOM from 'react-dom/client'
import { Chat } from './components/Chat'
import { CharacterPanel } from './components/CharacterPanel'
import './index.css'

// Временный компонент-обёртка для тестирования Chat и CharacterPanel до создания App.tsx
function App() {
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      margin: 0,
      padding: 0
    }}>
      {/* Main chat area */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Chat />
      </div>

      {/* Character panel sidebar */}
      <div style={{ width: '320px', borderLeft: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <CharacterPanel />
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
