/**
 * Settings Page
 *
 * System configuration and settings.
 */

export default function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">
          System configuration
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
        <div className="text-gray-400 text-5xl mb-4" aria-hidden="true">
          ⚙️
        </div>
        <h2 className="text-lg font-medium text-gray-900 mb-2">
          Settings
        </h2>
        <p className="text-gray-600">
          System settings will be available here.
        </p>
      </div>
    </div>
  )
}
