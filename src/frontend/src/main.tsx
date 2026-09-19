import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import { I18nProvider } from './i18n';
import { ErrorBoundary } from './components/ErrorBoundary';
import './styles/global.css';

const container = document.getElementById('root');
if (!container) throw new Error('#root missing from index.html');

createRoot(container).render(
  <StrictMode>
    <I18nProvider>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </I18nProvider>
  </StrictMode>,
);
