// Mini App API Client
// Qat'iy qoida: Mini App DB'ga tegmaydi, barcha logikani faqat REST API orqali oladi.

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

export async function apiCall<T = any>(endpoint: string, method = 'GET', body: any = null): Promise<T> {
  const initData = getTelegramInitData();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (initData) {
    headers['Authorization'] = `TelegramWebApp ${initData}`;
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
      err = json.error || json.message || JSON.stringify(json);
    } catch {
      err = await res.text();
    }
    throw new Error(err);
  }

  return res.json();
}
