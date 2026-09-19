import { Component, type ErrorInfo, type ReactNode } from 'react';
import { useI18n } from '../i18n';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

// Localized functional child — class components cannot use hooks, so this wrapper
// provides the translation function to the error panel.
function ErrorPanel({ error }: { error: Error | null }) {
  const { t } = useI18n();
  return (
    <div className="screen-error">
      <h2>{t('error.boundaryTitle')}</h2>
      <p>{t('error.boundaryBody')}</p>
      {error && (
        <details style={{ marginTop: 'var(--space-2)', fontSize: 'var(--fs-cell)' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>
            {error.message}
          </summary>
          <pre style={{ marginTop: 'var(--space-1)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {error.stack}
          </pre>
        </details>
      )}
      <button
        onClick={() => window.location.reload()}
        style={{ marginTop: 'var(--space-3)' }}
      >
        {t('error.reload')}
      </button>
    </div>
  );
}

/**
 * Error boundary — catches render crashes in the component tree and shows a localized
 * fallback instead of unmounting the entire app. Logs the error and component stack
 * to the console for debugging.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <ErrorPanel error={this.state.error} />;
    }
    return this.props.children;
  }
}
