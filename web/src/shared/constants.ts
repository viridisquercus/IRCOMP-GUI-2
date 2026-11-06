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
 *  The numeric limits are generated from that module.
 */

/* Limits */
export { MAX_FILE, MAX_LABEL, MAX_RATIONALE } from "./constants.generated";

/* Other values */
export const API_ROOT = "/api/v1"; // Prefix of every service route
export const SESSION_KEY = "ircomp.workspace"; // sessionStorage key of the open workspace
export const DEMO_REFERENCE = "demo-reference-v1"; // Synthetic reference of the examples
export const NO_DRAFTS = { target: null, decision: null }; // Empty editor buffers
