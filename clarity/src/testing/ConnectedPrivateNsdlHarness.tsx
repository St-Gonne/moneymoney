import { createRoot } from 'react-dom/client';
import '../index.css';
import { backendAccess, setBackendCurrentUserResolver } from '../services/apiAuth.ts';
import { PrivateNsdlApp } from '../components/PrivateNsdlApp.tsx';

const owner = 'synthetic_connected_owner';
const portfolio = 'synthetic_connected_portfolio';
const ordinaryMode = new URLSearchParams(window.location.search).has('ordinary');

setBackendCurrentUserResolver(() => ({ uid: owner, getIdToken: async () => 'synthetic-connected-token' }));
backendAccess.establishFirebaseSession(owner);

createRoot(document.getElementById('root')!).render(
  <div className="min-h-screen bg-theme-app">
    <div className="max-w-6xl mx-auto px-4 pt-4">
      <div className="card border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100" role="status" aria-label="Synthetic demo sample data">
        <strong>Synthetic demo</strong>
        <span className="text-blue-200"> — sample data, local only.</span>
      </div>
    </div>
    <PrivateNsdlApp
      portfolioId={portfolio}
      {...(ordinaryMode ? {} : { presentation: { label: 'Synthetic complete-history portfolio', observationDates: ['2026-03-02', '2026-06-01', '2026-09-09'] } })}
      currentUser={{ uid: owner, familyId: 'synthetic_connected_family', role: 'ADMIN', sessionKind: 'firebase_session', email: 'synthetic.connected@example.test', name: 'Synthetic connected owner' }}
      onSignOut={async () => backendAccess.clearSession()}
    />
  </div>,
);
