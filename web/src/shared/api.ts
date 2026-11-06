/**
 * @file api.ts
 * @brief Communication with the local Python service
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 */
import { API_ROOT, MAX_FILE } from "./constants";
import type { Diagnostic } from "./types";
import type { ResponseTypes } from "./types.generated";
import { definitions, responseSchemas } from "./schemas.generated";
import { matchesSchema } from "./responseValidation";
function readResponse<T extends keyof ResponseTypes>(
  kind: T,
  value: unknown,
): ResponseTypes[T] {
  if (!matchesSchema(value, responseSchemas[kind], definitions))
    throw new ApiError(
      "RESPONSE_INVALID",
      "The local service returned an invalid response.",
    );
  return value as ResponseTypes[T];
}

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
 * @param kind Response model to check, null for an empty response
 * @param body Body to send, if undefined a GET is made
 * @param method Overrides the method chosen from the body
 * @return The parsed JSON response, undefined for 204
 */
export function api<T extends keyof ResponseTypes>(
  path: string,
  kind: T,
  body?: unknown,
  method?: string,
): Promise<ResponseTypes[T]>;
export function api(
  path: string,
  kind: null,
  body?: unknown,
  method?: string,
): Promise<void>;
export async function api<T extends keyof ResponseTypes>(
  path: string,
  kind: T | null,
  body?: unknown,
  method?: string,
): Promise<ResponseTypes[T] | void> {
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
    const raw: unknown = await response.json().catch(() => null);
    if (matchesSchema(raw, responseSchemas.ErrorResponse, definitions)) {
      const failure = readResponse("ErrorResponse", raw).error;
      throw new ApiError(failure.code, failure.message, failure.diagnostics);
    }
    throw new ApiError("HTTP_ERROR", "The operation could not complete.");
  }
  if (kind === null) {
    if (response.status !== 204)
      throw new ApiError("RESPONSE_INVALID", "Expected an empty response.");
    return;
  }
  const document: unknown = await response.json().catch(() => {
    throw new ApiError(
      "RESPONSE_INVALID",
      "The local service returned invalid JSON.",
    );
  });
  return readResponse(kind, document);
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
