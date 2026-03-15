/**
 * Dashboard Page
 *
 * Displays collection status, data statistics, and recent data flow.
 */

import { useEffect, useState, useCallback } from 'react'
import { apiClient } from '../api/client'
import type { Spider, CollectedData } from '../types/api'
import StatCard from '../components/StatCard'
import SpiderStatusList from '../components/SpiderStatusList'
import RecentDataFeed from '../components/RecentDataFeed'

interface DashboardStats {
  total_items: number
  today_items: number
  sources_count: number
  active_spiders: number
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [spiders, setSpiders] = useState<Spider[]>([])
  const [recentItems, setRecentItems] = useState<CollectedData[]>([])
  const [loading, setLoading] = useState(true)
  const [statsError, setStatsError] = useState(false)

  const fetchSpiders = useCallback(async () => {
    try {
      const data = await apiClient.get<Spider[]>('/spiders')
      setSpiders(data)
    } catch {
      // SpiderStatusList component handles empty state
    }
  }, [])

  useEffect(() => {
    async function fetchData() {
      setLoading(true)

      try {
        // Fetch stats
        try {
          const data = await apiClient.get<DashboardStats>('/stats')
          setStats(data)
          setStatsError(false)
        } catch {
          setStatsError(true)
        }

        // Fetch spiders
        await fetchSpiders()

        // Fetch recent items
        try {
          const data = await apiClient.get<CollectedData[]>('/data', { limit: '10' })
          setRecentItems(data)
        } catch {
          // RecentDataFeed component handles empty state
        }
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [fetchSpiders])

  // Transform CollectedData to match RecentDataFeed interface
  const feedItems = recentItems.map(item => ({
    ...item,
    collected_at: new Date(item.collected_at),
  }))

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
      <section aria-labelledby="stats-heading">
        <h2 id="stats-heading" className="sr-only">
          Statistics
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <StatCard
              title="Total Items"
              value={stats?.total_items.toLocaleString() ?? '—'}
              loading={loading}
              error={statsError}
            />
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <StatCard
              title="Today"
              value={stats?.today_items.toLocaleString() ?? '—'}
              loading={loading}
              error={statsError}
            />
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <StatCard
              title="Data Sources"
              value={stats?.sources_count ?? '—'}
              loading={loading}
              error={statsError}
            />
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <StatCard
              title="Active Spiders"
              value={stats?.active_spiders ?? '—'}
              loading={loading}
              error={statsError}
            />
          </div>
        </div>
      </section>

      {/* Spider Status */}
      <section aria-labelledby="spiders-heading">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 id="spiders-heading" className="text-lg font-semibold text-gray-900">
              Spider Status
            </h2>
          </div>
          <div className="p-6">
            <SpiderStatusList
              spiders={spiders}
              loading={loading}
              onRefresh={fetchSpiders}
            />
          </div>
        </div>
      </section>

      {/* Recent Data Flow */}
      <section aria-labelledby="recent-heading">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 id="recent-heading" className="text-lg font-semibold text-gray-900">
              Recent Data Flow
            </h2>
          </div>
          <div className="p-6">
            <RecentDataFeed
              items={feedItems.length > 0 ? feedItems : null}
              loading={loading}
            />
          </div>
        </div>
      </section>
    </div>
  )
}
