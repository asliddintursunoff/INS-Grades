// Mini App API Client
// Secure REST API client with zero exposed master API keys

export function getTelegramInitData(): string {
  if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp?.initData) {
    return (window as any).Telegram.WebApp.initData;
  }
  return '';
}

export function getTelegramUser(): { id: number; first_name: string; username?: string } | null {
  if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp?.initDataUnsafe?.user) {
    return (window as any).Telegram.WebApp.initDataUnsafe.user;
  }
  return null;
}

const API_BASE_URL = ((import.meta as any).env?.VITE_API_URL || '').replace(/\/$/, '');

let cachedSessionToken: string | null = null;
let sessionPromise: Promise<string | null> | null = null;

async function getClientSessionToken(): Promise<string | null> {
  if (cachedSessionToken) return cachedSessionToken;
  if (sessionPromise) return sessionPromise;

  sessionPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const data = await res.json();
        cachedSessionToken = data.session_token || null;
        return cachedSessionToken;
      }
    } catch {
      // Non-blocking fallback
    } finally {
      sessionPromise = null;
    }
    return null;
  })();

  return sessionPromise;
}

export async function apiCall<T = any>(endpoint: string, method = 'GET', body: any = null): Promise<T> {
  const initData = getTelegramInitData();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (initData) {
    // Authenticate via Telegram WebApp cryptographic signature (zero API key in frontend)
    headers['Authorization'] = `TelegramWebApp ${initData}`;
  } else {
    // Authenticate web preview client via ephemeral session token
    const token = await getClientSessionToken();
    if (token) {
      headers['X-Session-Token'] = token;
    }
  }

  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullUrl = endpoint.startsWith('http://') || endpoint.startsWith('https://')
    ? endpoint
    : `${API_BASE_URL}${normalizedEndpoint}`;

  const res = await fetch(fullUrl, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let err = 'API xatosi';
    try {
      const json = await res.json();
      err = json.detail || json.error || json.message || JSON.stringify(json);
    } catch {
      err = await res.text();
    }
    throw new Error(err);
  }

  return res.json();
}
