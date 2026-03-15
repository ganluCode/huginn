/**
 * API Response Types
 *
 * This file defines TypeScript interfaces for the Huginn backend API responses.
 * These correspond to the FastAPI endpoints defined in F06 (Spider Management)
 * and F07 (Data Query).
 */

/**
 * Generic paginated response wrapper
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

/**
 * Spider metadata from spider_registry table
 */
export interface Spider {
  name: string;
  engine: "scrapy" | "rpa";
  category: "tech" | "social" | "finance" | "market";
  schedule: string | null; // cron expression or null
  enabled: boolean;
  last_run_at: string | null; // ISO 8601 datetime or null
  last_status: "success" | "failed" | "running" | null;
  item_count: number;
  created_at: string; // ISO 8601 datetime
}

/**
 * Single spider run record from spider_runs table
 */
export interface SpiderRun {
  id: number;
  spider_name: string;
  started_at: string; // ISO 8601 datetime
  finished_at: string | null; // ISO 8601 datetime or null
  status: "running" | "success" | "failed";
  item_count: number;
  error_message: string | null;
  duration_ms: number | null;
}

/**
 * Single collected data record from collected_data table
 */
export interface CollectedData {
  id: number;
  source: string; // e.g., "hackernews", "weibo_hot"
  category: "tech" | "social" | "finance" | "market";
  collected_at: string; // ISO 8601 datetime
  data: Record<string, unknown>; // JSONB data, flexible structure per spider
}

/**
 * Statistics aggregation response
 */
export interface DataStats {
  total: number;
  by_source: Record<string, number>;
  by_category: Record<string, number>;
  by_date: Record<string, number>; // date string -> count
}

/**
 * Health check endpoint response
 */
export interface HealthStatus {
  status: "healthy" | "unhealthy";
  postgres: "connected" | "disconnected";
  redis: "connected" | "disconnected";
}
