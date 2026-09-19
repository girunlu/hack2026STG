import type {
  ClientDetailResponse,
  ClientsResponse,
  HealthResponse,
  MarketSearchResponse,
  PortfolioDetailResponse,
} from '../types';
import type { Lang } from '../i18n';

const BASE: string = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  readonly status?: number;
  /** The server's own ``detail`` when it sent a plain string, e.g. "Unknown client CASE-NOPE". */
  readonly detail?: string;

  constructor(message: string, status?: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Build the ``ApiError`` for a non-2xx response.
 *
 * FastAPI's ``detail`` is either a plain string (an advisor can read "Unknown client CASE-NOPE") or a
 * structured object (never dumped at the user). The raw body is only quoted when no plain detail
 * exists, and then only its first 200 characters.
 */
async function httpError(path: string, response: Response): Promise<ApiError> {
  const raw = await response.text().catch(() => '');
  let detail: string | undefined;
  try {
    const payload = JSON.parse(raw) as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : undefined;
  } catch {
    detail = undefined;
  }
  const shown = detail ?? (raw ? raw.slice(0, 200) : '');
  return new ApiError(
    `Request ${path} failed (HTTP ${response.status})${shown ? `: ${shown}` : ''}`,
    response.status,
    detail,
  );
}

// In-flight request cache to prevent duplicate concurrent requests
const inflight = new Map<string, Promise<unknown>>();

async function get<T>(path: string, lang: Lang): Promise<T> {
  const separator = path.includes('?') ? '&' : '?';
  const url = `${BASE}${path}${separator}lang=${lang}`;
  const cacheKey = `GET:${url}`;
  
  // Return existing in-flight request if present
  const cached = inflight.get(cacheKey);
  if (cached) return cached as Promise<T>;
  
  const promise = (async () => {
    let response: Response;
    try {
      response = await fetch(url, {
        headers: { Accept: 'application/json', 'Accept-Language': lang },
      });
    } catch {
      throw new ApiError(
        'Backend not reachable. Is the server running on port 8000? (python -m uvicorn app.main:app)',
      );
    }
    if (!response.ok) {
      throw await httpError(path, response);
    }
    return (await response.json()) as T;
  })();
  
  inflight.set(cacheKey, promise);
  try {
    return await promise;
  } finally {
    inflight.delete(cacheKey);
  }
}

async function post<T>(path: string, body: unknown, lang: Lang): Promise<T> {
  const url = `${BASE}${path}`;
  const cacheKey = `POST:${url}:${JSON.stringify(body)}:${lang}`;
  
  // Return existing in-flight request if present
  const cached = inflight.get(cacheKey);
  if (cached) return cached as Promise<T>;
  
  const promise = (async () => {
    let response: Response;
    try {
      response = await fetch(`${url}?lang=${lang}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'Accept-Language': lang },
        body: JSON.stringify(body),
      });
    } catch {
      throw new ApiError(
        'Backend not reachable. Is the server running on port 8000? (python -m uvicorn app.main:app)',
      );
    }
    if (!response.ok) {
      throw await httpError(path, response);
    }
    return (await response.json()) as T;
  })();
  
  inflight.set(cacheKey, promise);
  try {
    return await promise;
  } finally {
    inflight.delete(cacheKey);
  }
}

export interface ImportClientsResult {
  file: string;
  clients_added: number;
  refs: string[];
  clients_total: number;
  portfolios_total: number;
  unresolved_positions: Array<{ client_ref: string; isin: string | null; reason: string }>;
  warnings: string[];
  data_gaps: string[];
}

export interface DatasetUpload {
  file: string;
  bytes: number;
  clients: number;
  refs: string[];
  valid: boolean;
  error: string | null;
}

/** Multipart upload — the only endpoint here that is not plain JSON. */
async function postFile<T>(path: string, file: File, lang: Lang): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}?lang=${lang}`, { method: 'POST', body: form });
  } catch {
    throw new ApiError('Backend not reachable. Is the server running on port 8000?');
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail ?? `HTTP ${response.status}`;
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status);
  }
  return payload as T;
}

export const api = {
  health: (lang: Lang) => get<HealthResponse>('/api/health', lang),
  clients: (lang: Lang) => get<ClientsResponse>('/api/clients', lang),
  client: (ref: string, lang: Lang) =>
    get<ClientDetailResponse>(`/api/clients/${encodeURIComponent(ref)}`, lang),
  portfolio: (ref: string, nr: string, lang: Lang) =>
    get<PortfolioDetailResponse>(
      `/api/clients/${encodeURIComponent(ref)}/portfolios/${encodeURIComponent(nr)}`,
      lang,
    ),
  /** New client files, the way the README requires them to be accepted. */
  importClients: (file: File, lang: Lang) => postFile<ImportClientsResult>('/api/dataset/clients', file, lang),
  uploads: (lang: Lang) =>
    get<{ directory: string; files: DatasetUpload[]; uploaded_clients: number }>('/api/dataset/uploads', lang),
  /** POST /api/briefing — deduped in-flight, returns the full briefing payload. */
  briefing: <T,>(body: { client_ref: string; portfolio_nr: string | null; renderer: string; lang: Lang }, lang: Lang) =>
    post<T>('/api/briefing', body, lang),
  /** Any other JSON POST: same in-flight dedupe and the same readable error as the rest of the client. */
  post,
  /** Generic GET with deduplication */
  get: <T,>(path: string, lang: Lang) => get<T>(path, lang),
  /** Market search — advisor tool. Limit is clamped server-side; we pass it through. */
  marketSearch: (q: string, lang: Lang, limit = 8) =>
    get<MarketSearchResponse>(
      `/api/market/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      lang,
    ),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

/**
 * Which R4 renderer to ask the backend for.
 *
 * The optional LLM pass only rephrases sentences — it never computes a figure — so the UI asks for
 * it when the backend reports a key, and falls back to the deterministic template when it does not.
 * The probe runs once per page load: the answer cannot change while the app is open, and every
 * briefing would otherwise pay for an extra round trip.
 */
let rendererProbe: Promise<string> | null = null;

export function preferredRenderer(lang: Lang): Promise<string> {
  if (!rendererProbe) {
    rendererProbe = api
      .health(lang)
      .then((health) => (health.llm_available ? 'llm' : 'template'))
      .catch(() => 'template');
  }
  return rendererProbe;
}
