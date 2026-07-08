import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';

interface RoutingDistributionChartProps {
  data: Array<{
    routing_target: string;
    count: number;
    percentage: number;
  }>;
  total: number;
}

// Color palette for routing targets
const COLORS: Record<string, string> = {
  'LIGHTRAG': '#3b82f6',           // Blue
  'FEE_ENGINE_CARDS': '#10b981',   // Green
  'FEE_ENGINE_RETAIL': '#8b5cf6',  // Purple
  'FEE_ENGINE_SKYBANKING': '#f59e0b', // Amber
  'LOCATION': '#ef4444',           // Red
  'PHONEBOOK': '#06b6d4',          // Cyan
  'DISAMBIGUATION': '#f97316',     // Orange
  'CLARIFICATION': '#a855f7',      // Violet
  'PRODUCT_INFO': '#84cc16',       // Lime
  'SMALL_TALK': '#ec4899',         // Pink
  'UNKNOWN': '#6b7280',            // Gray
};

const getColor = (target: string): string => {
  return COLORS[target] || COLORS['UNKNOWN'];
};

const formatLabel = (target: string): string => {
  const labels: Record<string, string> = {
    'LIGHTRAG': 'LightRAG (Knowledge Base)',
    'FEE_ENGINE_CARDS': 'Fee Engine - Cards',
    'FEE_ENGINE_RETAIL': 'Fee Engine - Retail Assets',
    'FEE_ENGINE_SKYBANKING': 'Fee Engine - Skybanking',
    'LOCATION': 'Location Service',
    'PHONEBOOK': 'Phonebook/Contacts',
    'DISAMBIGUATION': 'Disambiguation',
    'CLARIFICATION': 'Clarification Request',
    'PRODUCT_INFO': 'Product Information',
    'SMALL_TALK': 'Small Talk',
    'UNKNOWN': 'Unknown/Other',
  };
  return labels[target] || target;
};

const RoutingDistributionChart: React.FC<RoutingDistributionChartProps> = ({ data, total }) => {
  const chartData = data.map(item => ({
    name: formatLabel(item.routing_target),
    value: item.count,
    percentage: item.percentage,
    color: getColor(item.routing_target),
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
          <p className="font-semibold text-gray-800">{data.name}</p>
          <p className="text-gray-600">
            <span className="font-medium">{data.value.toLocaleString()}</span> queries
          </p>
          <p className="text-gray-500 text-sm">
            {data.percentage.toFixed(1)}% of total
          </p>
        </div>
      );
    }
    return null;
  };

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No routing data available yet. Data will appear as conversations are logged.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center text-sm text-gray-600 mb-4">
        <span>Total Routed Queries: <strong>{total.toLocaleString()}</strong></span>
      </div>
      
      <ResponsiveContainer width="100%" height={350}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={120}
            paddingAngle={2}
            dataKey="value"
            label={({ name, percentage }) => percentage > 5 ? `${percentage.toFixed(0)}%` : ''}
            labelLine={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            layout="vertical" 
            align="right" 
            verticalAlign="middle"
            formatter={(value) => <span className="text-sm text-gray-700">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Summary Table */}
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 font-semibold text-gray-700">Routing Target</th>
              <th className="text-right py-2 px-3 font-semibold text-gray-700">Count</th>
              <th className="text-right py-2 px-3 font-semibold text-gray-700">Percentage</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, index) => (
              <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 px-3 flex items-center gap-2">
                  <span 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: getColor(item.routing_target) }}
                  />
                  {formatLabel(item.routing_target)}
                </td>
                <td className="text-right py-2 px-3 font-medium">
                  {item.count.toLocaleString()}
                </td>
                <td className="text-right py-2 px-3 text-gray-600">
                  {item.percentage.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RoutingDistributionChart;
