import { useState } from 'react'
import { formatRelativeTime } from '../utils/utils'
import { apiClient } from '../api/client'
import type { Spider } from '../types/api'

interface SpiderStatusListProps {
  spiders: Spider[]
  loading?: boolean
  onRefresh?: () => void
}

// Status color mapping
const getStatusColor = (status: Spider['last_status']): string => {
  switch (status) {
    case 'success':
      return 'bg-green-500'
    case 'failed':
      return 'bg-red-500'
    case 'running':
      return 'bg-blue-500'
    default:
      return 'bg-gray-400'
  }
}

// Category color mapping for badges
const getCategoryColor = (category: Spider['category']): string => {
  switch (category) {
    case 'tech':
      return 'bg-blue-100 text-blue-700'
    case 'social':
      return 'bg-purple-100 text-purple-700'
    case 'finance':
      return 'bg-green-100 text-green-700'
    case 'market':
      return 'bg-orange-100 text-orange-700'
    default:
      return 'bg-gray-100 text-gray-700'
  }
}

export default function SpiderStatusList({ spiders, loading = false, onRefresh }: SpiderStatusListProps) {
  // Track trigger state for each spider: { [spiderName]: string | null }
  // string can be 'triggered' | 'already-running' | 'error'
  const [triggerStates, setTriggerStates] = useState<Record<string, string | null>>({})
  const [triggeringSpiders, setTriggeringSpiders] = useState<Set<string>>(new Set())

  const handleTrigger = async (spiderName: string) => {
    // Prevent multiple clicks
    if (triggeringSpiders.has(spiderName)) {
      return
    }

    // Set loading state
    setTriggeringSpiders(prev => new Set(prev).add(spiderName))

    try {
      await apiClient.post(`/spiders/${spiderName}/run`)

      // Success - show 'Triggered' message
      setTriggerStates(prev => ({ ...prev, [spiderName]: 'triggered' }))

      // Clear message after 2 seconds and call onRefresh
      setTimeout(() => {
        setTriggerStates(prev => {
          const newStates = { ...prev }
          delete newStates[spiderName]
          return newStates
        })
        onRefresh?.()
      }, 2000)
    } catch (error) {
      // Handle different error types
      const apiError = error as { status?: number }
      if (apiError.status === 409) {
        setTriggerStates(prev => ({ ...prev, [spiderName]: 'already-running' }))
      } else {
        setTriggerStates(prev => ({ ...prev, [spiderName]: 'error' }))
      }

      // Clear error message after 3 seconds
      setTimeout(() => {
        setTriggerStates(prev => {
          const newStates = { ...prev }
          delete newStates[spiderName]
          return newStates
        })
      }, 3000)
    } finally {
      setTriggeringSpiders(prev => {
        const newSet = new Set(prev)
        newSet.delete(spiderName)
        return newSet
      })
    }
  }

  // Loading state
  if (loading) {
    return (
      <div className="space-y-3" data-testid="loading-skeleton">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse rounded-lg bg-gray-100 p-4">
            <div className="h-6 w-48 rounded bg-gray-200" />
          </div>
        ))}
      </div>
    )
  }

  // Empty state
  if (!spiders || spiders.length === 0) {
    return (
      <div className="flex min-h-32 items-center justify-center rounded-lg bg-gray-50">
        <p className="text-sm text-gray-500">No spiders configured</p>
      </div>
    )
  }

  // Normal state - render table
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Spider
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Category
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Status
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Items
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Last Run
            </th>
            <th scope="col" className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {spiders.map(spider => {
            const statusColor = getStatusColor(spider.last_status)
            const categoryColor = getCategoryColor(spider.category)
            const lastRunTime = spider.last_run_at ? new Date(spider.last_run_at) : null
            const isTriggering = triggeringSpiders.has(spider.name)
            const triggerState = triggerStates[spider.name]

            return (
              <tr key={spider.name} className="hover:bg-gray-50">
                {/* Spider name */}
                <td className="whitespace-nowrap px-4 py-4 text-sm font-medium text-gray-900">
                  {spider.name}
                </td>

                {/* Category badge */}
                <td className="whitespace-nowrap px-4 py-4 text-sm">
                  <span className={`rounded-md px-2 py-1 text-xs font-medium ${categoryColor}`}>
                    {spider.category}
                  </span>
                </td>

                {/* Status dot */}
                <td className="whitespace-nowrap px-4 py-4 text-sm">
                  <div className="flex items-center gap-2">
                    <div className={`h-2.5 w-2.5 rounded-full ${statusColor}`} />
                  </div>
                </td>

                {/* Item count */}
                <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-500">
                  {spider.item_count.toLocaleString()}
                </td>

                {/* Last run time */}
                <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-500">
                  {formatRelativeTime(lastRunTime)}
                </td>

                {/* Trigger button */}
                <td className="whitespace-nowrap px-4 py-4 text-sm">
                  <div className="flex items-center justify-end gap-2">
                    {triggerState === 'triggered' && (
                      <span className="text-xs font-medium text-green-600">Triggered</span>
                    )}
                    {triggerState === 'already-running' && (
                      <span className="text-xs font-medium text-orange-600">Already running</span>
                    )}
                    {triggerState === 'error' && (
                      <span className="text-xs font-medium text-red-600">Error</span>
                    )}
                    {!triggerState && (
                      <button
                        onClick={() => handleTrigger(spider.name)}
                        disabled={isTriggering}
                        aria-label={`Trigger spider ${spider.name}`}
                        className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                          isTriggering
                            ? 'cursor-not-allowed bg-gray-100 text-gray-400'
                            : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
                        }`}
                      >
                        {isTriggering ? 'Triggering...' : 'Trigger'}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
