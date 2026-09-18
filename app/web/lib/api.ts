export type ValidationFlag = {
  code: string;
  severity: "blocking" | "warning";
  message: string;
  relatedIds?: string[];
};

export class ApiError extends Error {
  readonly status: number;
  readonly flags: ValidationFlag[];
  readonly details: unknown;

  constructor(status: number, details: unknown) {
    const body = details as {flags?: ValidationFlag[]; message?: string} | null;
    super(body?.flags?.[0]?.message ?? body?.message ?? `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.flags = body?.flags ?? [];
    this.details = details;
  }
}

const configuredBaseUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const fixtureBuild = process.env.NEXT_PUBLIC_APP_ENV === "local-fixture";
const baseUrl = configuredBaseUrl || (process.env.NODE_ENV === "development" ? "http://localhost:8106" : "");

export function isLocalApiUrl(value: string): boolean {
  const hostname = new URL(value).hostname.replace(/^\[|\]$/g, "").toLowerCase();
  return hostname === "localhost" || hostname === "::1" || /^127(?:\.\d{1,3}){3}$/.test(hostname);
}

function apiBaseUrl(): string {
  if (!baseUrl) throw new Error("NEXT_PUBLIC_API_URL is required outside local fixture development");
  if (process.env.NODE_ENV === "production" && !fixtureBuild) {
    if (isLocalApiUrl(baseUrl)) {
      throw new Error("localhost API URLs are only allowed in local fixture development");
    }
  }
  return baseUrl.replace(/\/$/, "");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {"Content-Type": "application/json", ...(init?.headers ?? {})},
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) throw new ApiError(response.status, body);
  return body as T;
}

export const api = {
  url(path: string) {
    return `${apiBaseUrl()}${path}`;
  },
  get<T>(path: string) {
    return request<T>(path);
  },
  post<T>(path: string, body: unknown) {
    return request<T>(path, {method: "POST", body: JSON.stringify(body)});
  },
};
