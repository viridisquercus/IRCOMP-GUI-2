/**
 * @file constants.ts
 * @brief Fixed values shared by the web client
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 *
 * Detailed description:
 *  Limits here only give an earlier message to the user, the service
 *  checks all of them again (see domain/constants.py).
 */

/* Limits */
export const MAX_FILE = 1048576; // Max size of an imported file - 1 MiB
export const MAX_LABEL = 200; // Max length of labels, titles and names
export const MAX_RATIONALE = 4000; // Max length of a decision rationale

/* Other values */
export const API_ROOT = "/api/v1"; // Prefix of every service route
export const SESSION_KEY = "ircomp.workspace"; // sessionStorage key of the open workspace
export const DEMO_REFERENCE = "demo-reference-v1"; // Synthetic reference of the examples
export const NO_DRAFTS = { target: null, decision: null }; // Empty editor buffers
