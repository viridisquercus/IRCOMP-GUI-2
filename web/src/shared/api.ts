/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import type { Diagnostic } from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public diagnostics: Diagnostic[] = [],
  ) {
    super(message);
  }
}

/** Send JSON to the local service and pass its error information to the view. */
export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method: method ?? (body === undefined ? "GET" : "POST"),
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      "CONNECTION_FAILED",
      "The local service is unavailable. Keep your inputs and refresh working state before retrying.",
    );
  }
  if (!response.ok) {
    const failure = await response.json().catch(() => null);
    throw new ApiError(
      failure?.error?.code ?? "HTTP_ERROR",
      failure?.error?.message ?? "The operation could not complete.",
      failure?.error?.diagnostics ?? [],
    );
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}

/** Read the selected file after checking the supported import size. */
export async function fileBase64(file: File): Promise<string> {
  if (file.size > 1048576)
    throw new ApiError("LIMIT_EXCEEDED", "Choose a file no larger than 1 MiB.");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
