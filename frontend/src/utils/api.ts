/**
 * Centralized API Base URL config.
 * Reads from process.env.NEXT_PUBLIC_API_URL if provided, otherwise defaults to http://localhost:8000
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
