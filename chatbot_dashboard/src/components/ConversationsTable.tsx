import React, { useState } from 'react';
import { format, parseISO } from 'date-fns';
import type { Conversation } from '../types';

interface ConversationsTableProps {
  conversations: Conversation[];
  onSearch?: (search: string) => void;
  onFilterRouting?: (routing: string) => void;
  onExportCsv?: () => void;
  searchValue?: string;
  routingFilter?: string;
}

const ROUTING_OPTIONS = [
  { value: '', label: 'All Routes' },
  { value: 'LIGHTRAG', label: 'LightRAG' },
  { value: 'FEE_ENGINE_CARDS', label: 'Fee Engine - Cards' },
  { value: 'FEE_ENGINE_RETAIL', label: 'Fee Engine - Retail' },
  { value: 'FEE_ENGINE_SKYBANKING', label: 'Fee Engine - Skybanking' },
  { value: 'LOCATION', label: 'Location Service' },
  { value: 'PHONEBOOK', label: 'Phonebook' },
  { value: 'DISAMBIGUATION', label: 'Disambiguation' },
  { value: 'CLARIFICATION', label: 'Clarification' },
  { value: 'PRODUCT_INFO', label: 'Product Info' },
];

const getRoutingBadgeColor = (routing: string | null): string => {
  const colors: Record<string, string> = {
    'LIGHTRAG': 'bg-blue-100 text-blue-800',
    'FEE_ENGINE_CARDS': 'bg-green-100 text-green-800',
    'FEE_ENGINE_RETAIL': 'bg-purple-100 text-purple-800',
    'FEE_ENGINE_SKYBANKING': 'bg-amber-100 text-amber-800',
    'LOCATION': 'bg-red-100 text-red-800',
    'PHONEBOOK': 'bg-cyan-100 text-cyan-800',
    'DISAMBIGUATION': 'bg-orange-100 text-orange-800',
    'CLARIFICATION': 'bg-violet-100 text-violet-800',
    'PRODUCT_INFO': 'bg-lime-100 text-lime-800',
    'SMALL_TALK': 'bg-pink-100 text-pink-800',
  };
  return colors[routing || ''] || 'bg-gray-100 text-gray-800';
};

const formatRouting = (routing: string | null): string => {
  if (!routing) return 'N/A';
  const labels: Record<string, string> = {
    'LIGHTRAG': 'LightRAG',
    'FEE_ENGINE_CARDS': 'Fee-Cards',
    'FEE_ENGINE_RETAIL': 'Fee-Retail',
    'FEE_ENGINE_SKYBANKING': 'Fee-Sky',
    'LOCATION': 'Location',
    'PHONEBOOK': 'Phonebook',
    'DISAMBIGUATION': 'Disambig',
    'CLARIFICATION': 'Clarify',
    'PRODUCT_INFO': 'Product',
    'SMALL_TALK': 'SmallTalk',
  };
  return labels[routing] || routing;
};

const ConversationsTable: React.FC<ConversationsTableProps> = ({ 
  conversations,
  onSearch,
  onFilterRouting,
  onExportCsv,
  searchValue = '',
  routingFilter = ''
}) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [localSearch, setLocalSearch] = useState(searchValue);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch?.(localSearch);
  };

  return (
    <div className="space-y-4">
      {/* Search and Filter Bar */}
      <div className="flex flex-wrap gap-4 items-center">
        <form onSubmit={handleSearchSubmit} className="flex gap-2 flex-1 min-w-[200px]">
          <input
            type="text"
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            placeholder="Search conversations..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-bank-blue-500 focus:border-transparent text-sm"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-bank-blue-500 text-white rounded-lg hover:bg-bank-blue-600 transition-colors text-sm"
          >
            Search
          </button>
        </form>
        
        <select
          value={routingFilter}
          onChange={(e) => onFilterRouting?.(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-bank-blue-500 text-sm"
        >
          {ROUTING_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        
        {onExportCsv && (
          <button
            onClick={onExportCsv}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm flex items-center gap-2"
          >
            📥 Export CSV
          </button>
        )}
      </div>

      {conversations.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No conversations found</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Session
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User Message
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Routing
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Time
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {conversations.map((conv) => (
                <React.Fragment key={conv.id}>
                  <tr className="hover:bg-gray-50">
                    <td className="px-3 py-3 text-sm text-gray-600">
                      <div className="truncate max-w-[100px] font-mono text-xs" title={conv.session_id}>
                        {conv.session_id.slice(0, 8)}...
                      </div>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 max-w-md">
                      <div className="truncate" title={conv.user_message}>
                        {conv.user_message}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-sm">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded-full ${
                          conv.is_answered
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {conv.is_answered ? '✅' : '❌'}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-sm">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${getRoutingBadgeColor(conv.routing_target)}`}>
                        {formatRouting(conv.routing_target)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {format(parseISO(conv.created_at), 'MMM dd, HH:mm')}
                    </td>
                    <td className="px-3 py-3 text-sm">
                      <button
                        onClick={() => setExpandedId(expandedId === conv.id ? null : conv.id)}
                        className="text-bank-blue-600 hover:text-bank-blue-800 font-medium"
                      >
                        {expandedId === conv.id ? '▲ Hide' : '▼ View'}
                      </button>
                    </td>
                  </tr>
                  {expandedId === conv.id && (
                    <tr>
                      <td colSpan={6} className="px-4 py-4 bg-gray-50">
                        <div className="space-y-3">
                          <div>
                            <h4 className="font-semibold text-gray-700 mb-1">User Message:</h4>
                            <p className="text-sm text-gray-600 bg-white p-3 rounded border">
                              {conv.user_message}
                            </p>
                          </div>
                          <div>
                            <h4 className="font-semibold text-gray-700 mb-1">Assistant Response:</h4>
                            <p className="text-sm text-gray-600 bg-white p-3 rounded border whitespace-pre-wrap max-h-64 overflow-y-auto">
                              {conv.assistant_response}
                            </p>
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-gray-500 bg-white p-3 rounded border">
                            <div>
                              <span className="font-semibold">Response Time:</span> {conv.response_time_ms ? `${conv.response_time_ms}ms` : 'N/A'}
                            </div>
                            <div>
                              <span className="font-semibold">Knowledge Base:</span> {conv.knowledge_base || 'N/A'}
                            </div>
                            <div>
                              <span className="font-semibold">Client IP:</span> <span className="font-mono">{conv.client_ip || 'N/A'}</span>
                            </div>
                            <div>
                              <span className="font-semibold">Routing:</span> {conv.routing_target || 'N/A'}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ConversationsTable;
