/**
 * @file api.ts
 * @brief Communication with the local Python service
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 *
 * Detailed description:
 *  The responses are not checked again here, FastAPI already validates
 *  them against the response models before sending. Their types come
 *  from types.generated.ts, so they always match the Python side.
 */
import { API_ROOT, MAX_FILE } from "./constants";
import type { Diagnostic, ErrorResponse } from "./types";

/* Classes */
/**
 * @brief Error reported by the service (or by the connection to it)
 */
export class ApiError extends Error {
  constructor(
    public code: string, // Error code, such as INTERVAL_INVALID
    message: string,
    public diagnostics: Diagnostic[] = [], // Detailed problems by field
  ) {
    super(message);
  }
}

/* Functions */
/**
 * @brief Send JSON to the local service and turn its errors into ApiError
 *
 * @param path Route after /api/v1
 * @param body Body to send, if undefined a GET is made
 * @param method Overrides the method chosen from the body
 * @return The parsed JSON response, undefined for 204
 */
export async function api<T = void>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const hasBody = body !== undefined;

  let response: Response;
  try {
    response = await fetch(API_ROOT + path, {
      method: method ?? (hasBody ? "POST" : "GET"),
      headers: hasBody ? { "Content-Type": "application/json" } : undefined,
      body: hasBody ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch only throws when the service can't be reached at all
    throw new ApiError(
      "CONNECTION_FAILED",
      "Can't reach the local service. Your input is still here, use Refresh working state once it runs again.",
    );
  }

  if (!response.ok) {
    // Error body may be missing (proxy error etc.), fall back to defaults
    const failure = (await response
      .json()
      .catch(() => null)) as ErrorResponse | null;
    throw new ApiError(
      failure?.error?.code ?? "HTTP_ERROR",
      failure?.error?.message ?? "Something went wrong.",
      failure?.error?.diagnostics ?? [],
    );
  }

  // No content - nothing to parse
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * @brief Read the chosen file as base64, after checking its size
 *
 * @param file File chosen by the user
 * @return The file encoded in base64
 */
export async function fileBase64(file: File): Promise<string> {
  if (file.size > MAX_FILE)
    throw new ApiError(
      "LIMIT_EXCEEDED",
      "The file is too big, the limit is 1 MiB.",
    );

  // btoa needs a binary string, one character per byte
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
