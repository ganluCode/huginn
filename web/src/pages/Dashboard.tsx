/**
 * Dashboard Page
 *
 * Displays collection status, data statistics, and recent data flow.
 */

import { useEffect, useState } from 'react'

interface SpiderStatus {
  name: string
  enabled: boolean
  last_run_at: string | null
  last_status: string | null
  item_count: number
}

interface DataStats {
  total_items: number
  today_items: number
  sources_count: number
  active_spiders: number
}

interface RecentItem {
  id: number
  source: string
  category: string
  collected_at: string
  data: {
    title?: string
    url?: string
    [key: string]: unknown
  }
}

export default function Dashboard() {
  const [stats, setStats] = useState<DataStats | null>(null)
  const [spiders, setSpiders] = useState<SpiderStatus[]>([])
  const [recentItems, setRecentItems] = useState<RecentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        // In a real implementation, these would be actual API calls
        // For now, using mock data
        setStats({
          total_items: 1234,
          today_items: 56,
          sources_count: 3,
          active_spiders: 3,
        })

        setSpiders([
          {
            name: 'hackernews',
            enabled: true,
            last_run_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
            last_status: 'success',
            item_count: 450,
          },
          {
            name: 'github_trending',
            enabled: true,
            last_run_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
            last_status: 'success',
            item_count: 320,
          },
          {
            name: 'crypto_price',
            enabled: true,
            last_run_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
            last_status: 'success',
            item_count: 464,
          },
        ])

        setRecentItems([
          {
            id: 1,
            source: 'hackernews',
            category: 'tech',
            collected_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
            data: {
              title: 'Show HN: I built a tool for...',
              url: 'https://example.com/1',
            },
          },
          {
            id: 2,
            source: 'github_trending',
            category: 'tech',
            collected_at: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
            data: {
              title: 'facebook/react',
              description: 'A declarative JavaScript library...',
            },
          },
          {
            id: 3,
            source: 'crypto_price',
            category: 'finance',
            collected_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
            data: {
              symbol: 'BTC',
              price_usd: 51234.56,
            },
          },
        ])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500" aria-label="Loading">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"
        role="alert"
      >
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">
          Collection status and data overview
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="text-3xl font-bold text-blue-600">
              {stats.total_items.toLocaleString()}
            </div>
            <div className="text-sm text-gray-600 mt-1">Total Items</div>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="text-3xl font-bold text-green-600">
              {stats.today_items.toLocaleString()}
            </div>
            <div className="text-sm text-gray-600 mt-1">Today</div>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="text-3xl font-bold text-purple-600">
              {stats.sources_count}
            </div>
            <div className="text-sm text-gray-600 mt-1">Data Sources</div>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="text-3xl font-bold text-orange-600">
              {stats.active_spiders}
            </div>
            <div className="text-sm text-gray-600 mt-1">Active Spiders</div>
          </div>
        </div>
      )}

      {/* Spider Status */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Spider Status
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Run
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Items
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {spiders.map((spider) => (
                <tr key={spider.name}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {spider.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        spider.enabled
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {spider.enabled ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {spider.last_run_at
                      ? new Date(spider.last_run_at).toLocaleString()
                      : 'Never'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {spider.item_count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Data Flow */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Data Flow
          </h2>
        </div>
        <div className="divide-y divide-gray-200">
          {recentItems.map((item) => (
            <div key={item.id} className="px-6 py-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {item.source}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(item.collected_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-sm font-medium text-gray-900">
                    {item.data.title ||
                      item.data.url ||
                      JSON.stringify(item.data).slice(0, 100)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
