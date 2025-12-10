import React, { useState } from 'react';
import { format, parseISO } from 'date-fns';
import type { Conversation } from '../types';

interface ConversationsTableProps {
  conversations: Conversation[];
}

const ConversationsTable: React.FC<ConversationsTableProps> = ({ conversations }) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (conversations.length === 0) {
    return (
      <p className="text-gray-500 text-center py-8">No conversations found</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Session ID
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              User Message
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Knowledge Base
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Time
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {conversations.map((conv) => (
            <React.Fragment key={conv.id}>
              <tr className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm text-gray-600">
                  <div className="truncate max-w-xs" title={conv.session_id}>
                    {conv.session_id}
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 max-w-md">
                  <div className="truncate" title={conv.user_message}>
                    {conv.user_message}
                  </div>
                </td>
                <td className="px-4 py-3 text-sm">
                  <span
                    className={`px-2 py-1 text-xs font-semibold rounded-full ${
                      conv.is_answered
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {conv.is_answered ? '✅ Answered' : '❌ Unanswered'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {conv.knowledge_base || 'N/A'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {format(parseISO(conv.created_at), 'MMM dd, HH:mm')}
                </td>
                <td className="px-4 py-3 text-sm">
                  <button
                    onClick={() => setExpandedId(expandedId === conv.id ? null : conv.id)}
                    className="text-bank-blue-600 hover:text-bank-blue-800 font-medium"
                  >
                    {expandedId === conv.id ? 'Hide' : 'View'}
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
                        <p className="text-sm text-gray-600 bg-white p-3 rounded border whitespace-pre-wrap">
                          {conv.assistant_response}
                        </p>
                      </div>
                      {conv.response_time_ms && (
                        <div className="text-xs text-gray-500">
                          Response time: {conv.response_time_ms}ms
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ConversationsTable;

