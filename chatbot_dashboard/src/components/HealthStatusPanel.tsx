import React from 'react';
import type { HealthStatus } from '../types';

interface HealthStatusPanelProps {
  health: HealthStatus;
}

const HealthStatusPanel: React.FC<HealthStatusPanelProps> = ({ health }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'unhealthy':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return '✅';
      case 'unhealthy':
        return '❌';
      default:
        return '⚠️';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-6">
      <h2 className="text-xl font-semibold mb-4 text-gray-800">System Health Status</h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Overall Status */}
        <div className={`border-2 rounded-lg p-4 ${getStatusColor(health.status)}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold">Overall</span>
            <span className="text-2xl">{getStatusIcon(health.status)}</span>
          </div>
          <p className="text-sm capitalize">{health.status}</p>
        </div>

        {/* LightRAG */}
        {health.components?.lightrag && (
          <div
            className={`border-2 rounded-lg p-4 ${getStatusColor(health.components.lightrag.status)}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">LightRAG</span>
              <span className="text-2xl">
                {getStatusIcon(health.components.lightrag.status)}
              </span>
            </div>
            <p className="text-sm capitalize">{health.components.lightrag.status}</p>
          </div>
        )}

        {/* Redis */}
        {health.components?.redis && (
          <div
            className={`border-2 rounded-lg p-4 ${getStatusColor(health.components.redis.status)}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">Redis</span>
              <span className="text-2xl">{getStatusIcon(health.components.redis.status)}</span>
            </div>
            <p className="text-sm capitalize">{health.components.redis.status}</p>
          </div>
        )}

        {/* PostgreSQL */}
        {health.components?.postgresql && (
          <div
            className={`border-2 rounded-lg p-4 ${getStatusColor(health.components.postgresql.status)}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">PostgreSQL</span>
              <span className="text-2xl">
                {getStatusIcon(health.components.postgresql.status)}
              </span>
            </div>
            <p className="text-sm capitalize">{health.components.postgresql.status}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default HealthStatusPanel;

