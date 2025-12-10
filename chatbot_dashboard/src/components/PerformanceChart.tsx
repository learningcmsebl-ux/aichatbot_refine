import React from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO } from 'date-fns';

interface PerformanceChartProps {
  data: Array<{
    date: string;
    total_conversations: number;
    answered_count: number;
    unanswered_count: number;
    answer_rate: number;
  }>;
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ data }) => {
  const chartData = data.map((item) => ({
    ...item,
    date: format(parseISO(item.date), 'MMM dd'),
    fullDate: item.date,
  }));

  return (
    <div className="space-y-6">
      {/* Conversations Over Time */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-700">Conversations Over Time</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="total_conversations"
              stroke="#0057a6"
              strokeWidth={2}
              name="Total Conversations"
            />
            <Line
              type="monotone"
              dataKey="answered_count"
              stroke="#10b981"
              strokeWidth={2}
              name="Answered"
            />
            <Line
              type="monotone"
              dataKey="unanswered_count"
              stroke="#ef4444"
              strokeWidth={2}
              name="Unanswered"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Answer Rate */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-700">Answer Rate Trend</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis domain={[0, 100]} />
            <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
            <Legend />
            <Bar dataKey="answer_rate" fill="#8b5cf6" name="Answer Rate (%)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default PerformanceChart;

