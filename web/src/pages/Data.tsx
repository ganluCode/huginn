import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { CollectedData } from '../types/api'
import DataFilters, { type DataFiltersState, type TimeRange } from '../components/DataFilters'
import { DataTable } from '../components/DataTable'

const LIMIT = 50

/**
 * Convert time_range to start_date string
 */
function timeRangeToStartDate(timeRange: TimeRange): string | undefined {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  switch (timeRange) {
    case 'today':
      return today.toISOString().split('T')[0]
    case '3d':
      return new Date(today.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    case '7d':
      return new Date(today.getTime() - 6 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    case '30d':
      return new Date(today.getTime() - 29 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    case 'all':
      return undefined
  }
}

/**
 * Parse URL search params to filter state
 */
function parseSearchParams(searchParams: URLSearchParams): DataFiltersState {
  return {
    source: searchParams.get('source') || 'All',
    category: (searchParams.get('category') || 'All') as DataFiltersState['category'],
    keyword: searchParams.get('keyword') || '',
    timeRange: (searchParams.get('time_range') || 'all') as TimeRange,
  }
}

/**
 * Convert filter state to URL search params
 */
function filterToSearchParams(filters: DataFiltersState, offset: number): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.source !== 'All') {
    params.set('source', filters.source)
  }
  if (filters.category !== 'All') {
    params.set('category', filters.category)
  }
  if (filters.keyword) {
    params.set('keyword', filters.keyword)
  }
  if (filters.timeRange !== 'all') {
    params.set('time_range', filters.timeRange)
  }
  if (offset > 0) {
    params.set('offset', offset.toString())
  }
  return params
}

/**
 * Data Query Page
 *
 * Query, browse, and export collected data with filters and pagination.
 */
export default function Data() {
  const [searchParams, setSearchParams] = useSearchParams()

  // State
  const [filters, setFilters] = useState<DataFiltersState>(() => parseSearchParams(searchParams))
  const [offset, setOffset] = useState(() => parseInt(searchParams.get('offset') || '0', 10))
  const [items, setItems] = useState<CollectedData[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  // AbortController ref for canceling requests
  const abortControllerRef = useRef<AbortController | null>(null)

  /**
   * Load data from API with current filters and offset
   */
  const loadData = useCallback(async () => {
    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new AbortController
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    setLoading(true)
    setError(null)

    try {
      // Build query params
      const params: Record<string, string> = {
        limit: LIMIT.toString(),
        offset: offset.toString(),
      }

      if (filters.source !== 'All') {
        params.source = filters.source
      }
      if (filters.category !== 'All') {
        params.category = filters.category
      }
      if (filters.keyword) {
        params.keyword = filters.keyword
      }

      const startDate = timeRangeToStartDate(filters.timeRange)
      if (startDate) {
        params.start_date = startDate
      }

      // Call API
      const response = await apiClient.get<{ items: CollectedData[]; total: number }>(
        '/data',
        params,
      )

      // Check if request was aborted
      if (abortController.signal.aborted) {
        return
      }

      setItems(response.items)
      setTotal(response.total)
    } catch (err) {
      // Ignore abort errors
      if (abortController.signal.aborted) {
        return
      }

      const message = err instanceof Error ? err.message : 'Failed to load data'
      setError(message)
    } finally {
      if (!abortController.signal.aborted) {
        setLoading(false)
      }
    }
  }, [filters, offset])

  /**
   * Handle filter changes
   * Updates URL params and resets offset to 0
   */
  const handleFilterChange = useCallback((newFilters: DataFiltersState) => {
    setFilters(newFilters)
    setOffset(0) // Reset to first page when filters change

    // Update URL params
    const newParams = filterToSearchParams(newFilters, 0)
    setSearchParams(newParams)
  }, [setSearchParams])

  /**
   * Handle pagination changes
   */
  const handlePageChange = useCallback((newOffset: number) => {
    setOffset(newOffset)

    // Update URL params
    const newParams = filterToSearchParams(filters, newOffset)
    setSearchParams(newParams)
  }, [filters, setSearchParams])

  /**
   * Handle CSV export
   * Constructs URL with current filters and opens in new tab
   */
  const handleExport = useCallback(() => {
    setExporting(true)

    try {
      // Build export URL with current filters
      const params = new URLSearchParams()
      params.set('format', 'csv')

      if (filters.source !== 'All') {
        params.set('source', filters.source)
      }
      if (filters.category !== 'All') {
        params.set('category', filters.category)
      }
      if (filters.keyword) {
        params.set('keyword', filters.keyword)
      }

      const startDate = timeRangeToStartDate(filters.timeRange)
      if (startDate) {
        params.set('start_date', startDate)
      }

      // Open export URL in new tab
      const exportUrl = `/api/data/export?${params.toString()}`
      window.open(exportUrl, '_blank')
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      // Restore export button after a delay
      setTimeout(() => {
        setExporting(false)
      }, 1000)
    }
  }, [filters])

  /**
   * Load data when filters or offset change
   */
  useEffect(() => {
    loadData()
  }, [loadData])

  /**
   * Cleanup on unmount - cancel any pending requests
   */
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Data</h1>
        <p className="text-gray-600 mt-1">
          Query and export collected data
        </p>
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-md bg-red-50 p-4 border border-red-200">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <DataFilters
        onFilterChange={handleFilterChange}
        onExport={handleExport}
        exporting={exporting}
        initialSource={filters.source}
        initialCategory={filters.category}
        initialKeyword={filters.keyword}
        initialTimeRange={filters.timeRange}
      />

      {/* Data Table */}
      <DataTable
        items={items}
        total={total}
        offset={offset}
        limit={LIMIT}
        loading={loading}
        onPageChange={handlePageChange}
      />
    </div>
  )
}
