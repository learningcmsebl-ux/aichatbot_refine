import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../services/api';
import type { PerformanceMetrics, Question, Conversation, HealthStatus } from '../types';
import MetricsCards from './MetricsCards';
import PerformanceChart from './PerformanceChart';
import QuestionsTable from './QuestionsTable';
import ConversationsTable from './ConversationsTable';
import HealthStatusPanel from './HealthStatusPanel';

const Dashboard: React.FC = () => {
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [mostAsked, setMostAsked] = useState<Question[]>([]);
  const [unanswered, setUnanswered] = useState<Question[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [daysFilter, setDaysFilter] = useState(30);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Use Promise.allSettled to handle partial failures gracefully
      const results = await Promise.allSettled([
        analyticsAPI.getPerformanceMetrics(daysFilter),
        analyticsAPI.getMostAskedQuestions(20),
        analyticsAPI.getUnansweredQuestions(50),
        analyticsAPI.getConversationHistory(undefined, 50),
        analyticsAPI.getHealthStatus(),
      ]);

      // Extract results, using defaults for failed requests
      const metrics = results[0].status === 'fulfilled' ? results[0].value : null;
      const mostAskedData = results[1].status === 'fulfilled' ? results[1].value : [];
      const unansweredData = results[2].status === 'fulfilled' ? results[2].value : [];
      const conversationsData = results[3].status === 'fulfilled' ? results[3].value : [];
      const health = results[4].status === 'fulfilled' ? results[4].value : null;

      // Log any failures with detailed information
      const endpointNames = ['Performance Metrics', 'Most Asked Questions', 'Unanswered Questions', 'Conversation History', 'Health Status'];
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          console.error(`Failed to fetch ${endpointNames[index]}:`, result.reason);
          console.error(`Error details:`, {
            message: result.reason?.message,
            response: result.reason?.response?.data,
            status: result.reason?.response?.status,
            url: result.reason?.config?.url
          });
        } else {
          console.log(`✓ Successfully fetched ${endpointNames[index]}`);
          if (index === 3) { // Conversation History
            console.log(`  Found ${conversationsData.length} conversations`);
          }
        }
      });

      setPerformanceMetrics(metrics);
      setMostAsked(mostAskedData);
      setUnanswered(unansweredData);
      setConversations(conversationsData);
      setHealthStatus(health);
    } catch (err: any) {
      console.error('Error fetching dashboard data:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to load dashboard data';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [daysFilter]);

  if (loading && !performanceMetrics) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-bank-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && !performanceMetrics) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-xl font-semibold text-red-800 mb-2">Error Loading Dashboard</h2>
          <p className="text-red-600 mb-4">{error}</p>
          <div className="text-sm text-gray-600 mb-4">
            <p>Please ensure:</p>
            <ul className="list-disc list-inside text-left mt-2">
              <li>Backend is running on port 8001</li>
              <li>API endpoints are accessible</li>
              <li>PostgreSQL database is connected</li>
            </ul>
          </div>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-bank-blue-500 to-bank-blue-600 text-white shadow-lg">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <img src="/dia-avatar.png" alt="EBL DIA" className="w-12 h-12 rounded-lg" />
              <div>
                <h1 className="text-2xl font-bold">EBL DIA 2.0 - Analytics Dashboard</h1>
                <p className="text-bank-blue-100 text-sm">Real-time Chatbot Monitoring</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <select
                value={daysFilter}
                onChange={(e) => setDaysFilter(Number(e.target.value))}
                className="bg-white/20 border border-white/30 rounded px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-white/50"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last year</option>
              </select>
              <button
                onClick={fetchData}
                disabled={loading}
                className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded transition-colors disabled:opacity-50"
                title="Refresh data"
              >
                🔄 Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {error && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <p className="text-yellow-800 text-sm">
              ⚠️ Warning: {error} (Some data may be incomplete)
            </p>
          </div>
        )}

        {/* Health Status */}
        {healthStatus && <HealthStatusPanel health={healthStatus} />}

        {/* Metrics Cards */}
        {performanceMetrics && (
          <MetricsCards metrics={performanceMetrics.overall} />
        )}

        {/* Performance Chart */}
        {performanceMetrics && performanceMetrics.daily_metrics.length > 0 && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Performance Trends</h2>
            <PerformanceChart data={performanceMetrics.daily_metrics} />
          </div>
        )}

        {/* Tables Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Most Asked Questions */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Most Asked Questions</h2>
            <QuestionsTable questions={mostAsked} />
          </div>

          {/* Unanswered Questions */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Unanswered Questions</h2>
            {unanswered.length > 0 ? (
              <QuestionsTable questions={unanswered} />
            ) : (
              <p className="text-gray-500 text-center py-8">No unanswered questions! 🎉</p>
            )}
          </div>
        </div>

        {/* Recent Conversations */}
        <div className="bg-white rounded-lg shadow-md p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Recent Conversations</h2>
          <ConversationsTable conversations={conversations} />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 text-white mt-12 py-4">
        <div className="container mx-auto px-6 text-center text-sm">
          <p>EBL DIA 2.0 Analytics Dashboard | Powered by EBL ICT Division</p>
          <p className="text-gray-400 mt-1">
            Last updated: {new Date().toLocaleString()}
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Dashboard;
