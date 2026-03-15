import { isUrl } from '../utils/utils';

interface DataDetailProps {
  data: Record<string, unknown> | null;
}

export function DataDetail({ data }: DataDetailProps) {
  // Handle empty or null data
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="text-center text-gray-500 py-4">
        No details available
      </div>
    );
  }

  const renderValue = (value: unknown): React.ReactNode => {
    // Handle null and undefined
    if (value === null) {
      return <span className="text-gray-400">null</span>;
    }
    if (value === undefined) {
      return <span className="text-gray-400">undefined</span>;
    }

    // Handle URL strings
    if (typeof value === 'string' && isUrl(value)) {
      return (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 underline break-all"
        >
          {value}
        </a>
      );
    }

    // Handle objects and arrays (including nested structures)
    if (typeof value === 'object') {
      const jsonString = JSON.stringify(value, null, 2);
      return (
        <pre className="font-mono text-xs bg-gray-50 p-2 rounded overflow-x-auto">
          {jsonString}
        </pre>
      );
    }

    // Handle booleans
    if (typeof value === 'boolean') {
      return <span className={value ? 'text-green-600' : 'text-red-600'}>{String(value)}</span>;
    }

    // Handle numbers and other primitives
    return <span>{String(value)}</span>;
  };

  return (
    <div className="space-y-2">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex flex-col sm:flex-row sm:items-start py-2 border-b border-gray-100 last:border-0">
          <span className="text-gray-500 font-medium min-w-[120px] sm:w-1/3 flex-shrink-0">
            {key}
          </span>
          <div className="flex-1 min-w-0 text-gray-900">
            {renderValue(value)}
          </div>
        </div>
      ))}
    </div>
  );
}
