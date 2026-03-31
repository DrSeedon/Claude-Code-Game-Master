import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

// Временный компонент-заглушка до создания App.tsx
function App() {
  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>DM Game Master</h1>
      <p>Web interface загружается...</p>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
