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
const baseUrl = configuredBaseUrl || (process.env.NODE_ENV === "development" ? "http://localhost:8106" : "");

function apiBaseUrl(): string {
  if (!baseUrl) throw new Error("NEXT_PUBLIC_API_URL is required outside local fixture development");
  if (process.env.NODE_ENV === "production") {
    const hostname = new URL(baseUrl).hostname;
    if (["localhost", "127.0.0.1", "::1"].includes(hostname)) {
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
