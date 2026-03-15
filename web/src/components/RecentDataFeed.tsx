import { formatRelativeTime } from '../utils/utils'

interface DataItem {
  id: number
  source: string
  category: string
  collected_at: Date
  data: {
    title?: string
    url?: string
    [key: string]: unknown
  }
}

interface RecentDataFeedProps {
  items: DataItem[] | null
  loading?: boolean
}

export default function RecentDataFeed({ items, loading = false }: RecentDataFeedProps) {
  // Loading state - show skeleton
  if (loading) {
    return (
      <div className="space-y-3" data-testid="loading-skeleton">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse rounded-lg bg-gray-100 p-4">
            <div className="flex h-4 w-32 rounded bg-gray-200" />
          </div>
        ))}
      </div>
    )
  }

  // Empty state
  if (!items || items.length === 0) {
    return (
      <div className="flex min-h-32 items-center justify-center rounded-lg bg-gray-50">
        <p className="text-sm text-gray-500">No data available</p>
      </div>
    )
  }

  // Normal state - render items
  return (
    <ul className="space-y-3">
      {items.map(item => {
        const title = item.data.title || `${item.source} #${item.id}`
        const hasUrl = item.data.url && typeof item.data.url === 'string'

        return (
          <li
            key={item.id}
            className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4 transition-colors hover:border-gray-300"
          >
            {/* Left side - title and metadata */}
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              {/* Title row */}
              <div className="flex items-start gap-2">
                {hasUrl ? (
                  <a
                    href={item.data.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-gray-900 hover:text-blue-600 hover:underline"
                  >
                    {title}
                  </a>
                ) : (
                  <span className="font-medium text-gray-900">{title}</span>
                )}
                {hasUrl && (
                  <svg
                    className="mt-0.5 h-4 w-4 shrink-0 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                )}
              </div>

              {/* Metadata row - source badge and time */}
              <div className="flex items-center gap-2 text-sm">
                {/* Source badge */}
                <span className="rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                  {item.source}
                </span>

                {/* Relative time */}
                <span className="text-gray-500">
                  {formatRelativeTime(item.collected_at instanceof Date ? item.collected_at : new Date(item.collected_at))}
                </span>
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
