import React from 'react'
import ReactDOM from 'react-dom/client'
import { Chat } from './components/Chat'
import './index.css'

// Временный компонент-обёртка для тестирования Chat до создания App.tsx
function App() {
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      margin: 0,
      padding: 0
    }}>
      <Chat />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
