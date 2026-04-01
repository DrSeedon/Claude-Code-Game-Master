import { Chat } from './components/Chat';
import { CharacterPanel } from './components/CharacterPanel';

/**
 * Main application component
 *
 * Provides the layout structure with chat interface and character panel sidebar.
 * Uses flexbox layout with chat taking the main area and character panel as a fixed-width sidebar.
 *
 * @example
 * ```tsx
 * import { App } from './App';
 *
 * ReactDOM.createRoot(document.getElementById('root')!).render(
 *   <React.StrictMode>
 *     <App />
 *   </React.StrictMode>
 * );
 * ```
 */
export function App() {
  return (
    <div className="app-container">
      {/* Main chat area - takes remaining space */}
      <main className="main-content">
        <Chat />
      </main>

      {/* Character panel sidebar - fixed width on the right */}
      <aside className="sidebar">
        <CharacterPanel />
      </aside>

      <style>{`
        .app-container {
          display: flex;
          height: 100vh;
          width: 100vw;
          margin: 0;
          padding: 0;
          overflow: hidden;
        }

        .main-content {
          flex: 1;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }

        .sidebar {
          width: 320px;
          border-left: 1px solid rgba(255, 255, 255, 0.1);
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }

        /* Responsive: Stack vertically on small screens */
        @media (max-width: 768px) {
          .app-container {
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
      `}</style>
    </div>
  );
}
