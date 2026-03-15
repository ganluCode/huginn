interface StatCardProps {
  title: string
  value: string | number
  loading?: boolean
  error?: boolean
}

export default function StatCard({ title, value, loading = false, error = false }: StatCardProps) {
  return (
    <div className="flex flex-col gap-1">
      {/* Title - gray small text */}
      <span className="text-sm text-gray-500">{title}</span>

      {/* Value area - shows skeleton, error, or actual value */}
      {loading ? (
        <div
          data-testid="statcard-skeleton"
          className="h-8 w-24 animate-pulse rounded bg-gray-200"
          aria-hidden="true"
        />
      ) : error ? (
        <span className="text-2xl font-bold">—</span>
      ) : (
        <span className="text-2xl font-bold">{value}</span>
      )}
    </div>
  )
}
