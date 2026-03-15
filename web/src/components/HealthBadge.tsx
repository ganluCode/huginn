import { useState, useEffect } from 'react'
import { apiClient } from '@/api/client'
import type { HealthStatus } from '@/types/api'

const POLL_INTERVAL_MS = 30_000 // 30 seconds

type ConnectionStatus = 'connected' | 'disconnected'

export default function HealthBadge() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')

  const checkHealth = async () => {
    try {
      await apiClient.get<HealthStatus>('/health')
      setStatus('connected')
    } catch {
      setStatus('disconnected')
    }
  }

  useEffect(() => {
    // Immediate check on mount
    checkHealth()

    // Set up polling interval
    const intervalId = setInterval(() => {
      checkHealth()
    }, POLL_INTERVAL_MS)

    // Cleanup on unmount
    return () => {
      clearInterval(intervalId)
    }
  }, [])

  const isConnected = status === 'connected'

  return (
    <div className="flex items-center gap-2 px-4 py-2 text-sm">
      <span
        data-testid="health-status-dot"
        className={`h-2 w-2 rounded-full ${
          isConnected ? 'bg-green-500' : 'bg-red-500'
        }`}
        aria-hidden="true"
      />
      <span className={isConnected ? 'text-green-600' : 'text-red-600'}>
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  )
}
