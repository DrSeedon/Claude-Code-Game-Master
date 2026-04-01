import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Lobby } from './pages/Lobby';
import { Game } from './screens/Game';
import { Wizard } from './pages/Wizard';
import { Dashboard } from './screens/Dashboard';

/**
 * Main application component with routing
 *
 * Sets up React Router with multiple screens:
 * - / : Campaign lobby (list and create campaigns)
 * - /game : Active game screen (chat with character panel)
 * - /wizard : Campaign creation wizard
 * - /dashboard : Campaign management dashboard
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
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Lobby />} />
        <Route path="/game" element={<Game />} />
        <Route path="/wizard" element={<Wizard />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  );
}
