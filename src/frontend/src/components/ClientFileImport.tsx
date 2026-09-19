import { useRef, useState } from 'react';

import { ApiError, api } from '../api/client';
import { useI18n } from '../i18n';
import './components.css';

/**
 * Accepts additional client files, the way the case README requires: *"build your solution to accept
 * new files of this shape (for example via an upload) rather than hardcoding the one you have today"*.
 *
 * The backend merges the file into the dataset, so a newly added client is immediately brief-able —
 * which is also what the final presentation's unseen-client drill needs.
 */
export default function ClientFileImport({ onImported }: { onImported: () => void }) {
  const { lang, t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function handleFile(file: File) {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      const result = await api.importClients(file, lang);
      setMessage(
        t('import.ok', { count: result.clients_added, total: result.clients_total }) +
          (result.data_gaps.length > 0 ? ` — ${result.data_gaps.join('; ')}` : ''),
      );
      onImported();
    } catch (error) {
      setFailed(true);
      // A 409 means the file clashes with provided data; name the refs rather than dumping JSON.
      const raw = error instanceof ApiError ? error.message : String(error);
      let refs: string[] = [];
      try {
        const parsed = JSON.parse(raw);
        refs = parsed?.clashing_refs ?? [];
      } catch {
        refs = [];
      }
      setMessage(refs.length > 0 ? t('import.clash', { refs: refs.join(', ') }) : t('import.error', { detail: raw }));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div className="client-import">
      <input
        ref={input}
        id="client-file-import"
        type="file"
        accept="application/json,.json"
        disabled={busy}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void handleFile(file);
        }}
      />
      <label htmlFor="client-file-import" className="client-import__label" title={t('import.hint')}>
        {busy ? t('import.busy') : t('import.title')}
      </label>
      {message ? (
        <span className={`client-import__status${failed ? ' client-import__status--failed' : ''}`}>{message}</span>
      ) : null}
    </div>
  );
}
