/**
 * In-memory API client for Sponsy Bot (SEC-10, SEC-35).
 * CSRF token is kept strictly in-memory and never written to storage.
 */

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let memoryCsrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  memoryCsrfToken = token;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD" && memoryCsrfToken) {
    headers.set("X-CSRF-Token", memoryCsrfToken);
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = (await response.json()) as { detail?: string };
      if (errJson && typeof errJson.detail === "string") {
        errorDetail = errJson.detail;
      }
    } catch {
      // Body was not JSON
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
