// Typed API Client for Hexagonal Go Backend
// Standardizes fetch calls, typed error handling, and payload parsing.

export interface ApiErrorPayload {
  error?: string;
  message?: string;
  details?: Record<string, string>;
}

export class ApiClientError extends Error {
  public readonly status: number;
  public readonly payload: ApiErrorPayload | null;

  constructor(status: number, message: string, payload: ApiErrorPayload | null = null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = path.startsWith("http") ? path : path.startsWith("/") ? path : `/${path}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (options.body && !headers.has("Content-Type") && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | null = null;
    let message = `Erreur réseau (HTTP ${response.status})`;

    try {
      const parsed: unknown = await response.json();
      if (typeof parsed === "object" && parsed !== null) {
        payload = parsed as ApiErrorPayload;
        if (typeof payload.message === "string") {
          message = payload.message;
        } else if (typeof payload.error === "string") {
          message = payload.error;
        }
      }
    } catch {
      // Body is not JSON
    }

    throw new ApiClientError(response.status, message, payload);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, options?: RequestInit): Promise<T> =>
    apiFetch<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, body?: unknown, options?: RequestInit): Promise<T> =>
    apiFetch<T>(path, {
      ...options,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown, options?: RequestInit): Promise<T> =>
    apiFetch<T>(path, {
      ...options,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(path: string, body?: unknown, options?: RequestInit): Promise<T> =>
    apiFetch<T>(path, {
      ...options,
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string, options?: RequestInit): Promise<T> =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
};

