import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../api/client'

// Time range options
export type TimeRange = 'today' | '3d' | '7d' | '30d' | 'all'

// Category options (from API spec)
const CATEGORIES = ['All', 'tech', 'social', 'finance', 'market', 'news'] as const
export type Category = typeof CATEGORIES[number]

// Time range display names
const TIME_RANGE_OPTIONS: Array<{ value: TimeRange; label: string }> = [
  { value: 'today', label: 'Today' },
  { value: '3d', label: 'Last 3 days' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'all', label: 'All' },
]

// Filter state interface
export interface DataFiltersState {
  source: string
  category: Category
  keyword: string
  timeRange: TimeRange
}

interface DataFiltersProps {
  onFilterChange: (filters: DataFiltersState) => void
  onExport: () => void
  exporting?: boolean
  initialSource?: string
  initialCategory?: Category
  initialKeyword?: string
  initialTimeRange?: TimeRange
}

export default function DataFilters({
  onFilterChange,
  onExport,
  exporting = false,
  initialSource = 'All',
  initialCategory = 'All',
  initialKeyword = '',
  initialTimeRange = 'all',
}: DataFiltersProps) {
  // State for sources loaded from API
  const [sources, setSources] = useState<string[]>(['All'])
  const [sourcesLoading, setSourcesLoading] = useState(true)

  // Filter state
  const [source, setSource] = useState(initialSource)
  const [category, setCategory] = useState<Category>(initialCategory)
  const [keyword, setKeyword] = useState(initialKeyword)
  const [timeRange, setTimeRange] = useState<TimeRange>(initialTimeRange)

  // Debounce timer ref
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load sources from API
  useEffect(() => {
    const loadSources = async () => {
      try {
        setSourcesLoading(true)
        const data = await apiClient.get<string[]>('/data/sources')
        setSources(['All', ...data])
      } catch (error) {
        console.error('Failed to load sources:', error)
        // Keep 'All' as default if API fails
      } finally {
        setSourcesLoading(false)
      }
    }

    loadSources()
  }, [])

  // Debounced keyword change handler
  const debouncedNotifyFilterChange = useCallback((filters: DataFiltersState) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    debounceTimerRef.current = setTimeout(() => {
      onFilterChange(filters)
    }, 300)
  }, [onFilterChange])

  // Immediate filter change notification
  const notifyFilterChange = useCallback((filters: DataFiltersState) => {
    onFilterChange(filters)
  }, [onFilterChange])

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  // Handle source change
  const handleSourceChange = (value: string) => {
    setSource(value)
    notifyFilterChange({
      source: value,
      category,
      keyword,
      timeRange,
    })
  }

  // Handle category change
  const handleCategoryChange = (value: Category) => {
    setCategory(value)
    notifyFilterChange({
      source,
      category: value,
      keyword,
      timeRange,
    })
  }

  // Handle keyword input with debounce
  const handleKeywordChange = (value: string) => {
    setKeyword(value)
    debouncedNotifyFilterChange({
      source,
      category,
      keyword: value,
      timeRange,
    })
  }

  // Handle time range change
  const handleTimeRangeChange = (value: TimeRange) => {
    setTimeRange(value)
    notifyFilterChange({
      source,
      category,
      keyword,
      timeRange: value,
    })
  }

  return (
    <div className="space-y-4 rounded-lg bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        {/* Source dropdown */}
        <div className="flex flex-col gap-1">
          <label htmlFor="source-select" className="text-xs font-medium text-gray-600">
            Source
          </label>
          <select
            id="source-select"
            value={source}
            onChange={(e) => handleSourceChange(e.target.value)}
            disabled={sourcesLoading}
            aria-label="Filter by data source"
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm transition-colors hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
          >
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Category dropdown */}
        <div className="flex flex-col gap-1">
          <label htmlFor="category-select" className="text-xs font-medium text-gray-600">
            Category
          </label>
          <select
            id="category-select"
            value={category}
            onChange={(e) => handleCategoryChange(e.target.value as Category)}
            aria-label="Filter by category"
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm transition-colors hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Keyword input */}
        <div className="flex flex-col gap-1">
          <label htmlFor="keyword-input" className="text-xs font-medium text-gray-600">
            Keyword
          </label>
          <input
            id="keyword-input"
            type="text"
            value={keyword}
            onChange={(e) => handleKeywordChange(e.target.value)}
            placeholder="Search..."
            aria-label="Filter by keyword"
            className="w-48 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 shadow-sm transition-colors placeholder:text-gray-400 hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        {/* Export button */}
        <div className="ml-auto flex items-end">
          <button
            onClick={onExport}
            disabled={exporting}
            aria-label={exporting ? 'Exporting data...' : 'Export data'}
            className={`rounded-md px-4 py-1.5 text-sm font-medium text-white shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed ${
              exporting
                ? 'cursor-not-allowed bg-gray-400 text-gray-200'
                : 'bg-blue-500 hover:bg-blue-600 active:bg-blue-700'
            }`}
          >
            {exporting ? 'Exporting...' : 'Export'}
          </button>
        </div>
      </div>

      {/* Time range quick select */}
      <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
        <span className="text-xs font-medium text-gray-600">Time Range:</span>
        <div className="flex flex-wrap gap-2">
          {TIME_RANGE_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => handleTimeRangeChange(option.value)}
              aria-label={`Time range: ${option.label}`}
              aria-pressed={timeRange === option.value}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 ${
                timeRange === option.value
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
