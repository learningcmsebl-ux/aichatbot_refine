import React from 'react';

interface MetricsCardsProps {
  metrics: {
    total_conversations: number;
    total_answered: number;
    total_unanswered: number;
    overall_answer_rate: number;
    avg_response_time_ms: number;
  };
}

const MetricsCards: React.FC<MetricsCardsProps> = ({ metrics }) => {
  const cards = [
    {
      title: 'Total Conversations',
      value: metrics.total_conversations.toLocaleString(),
      icon: '💬',
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Answered',
      value: metrics.total_answered.toLocaleString(),
      icon: '✅',
      color: 'bg-green-500',
      bgColor: 'bg-green-50',
    },
    {
      title: 'Unanswered',
      value: metrics.total_unanswered.toLocaleString(),
      icon: '❌',
      color: 'bg-red-500',
      bgColor: 'bg-red-50',
    },
    {
      title: 'Answer Rate',
      value: `${metrics.overall_answer_rate.toFixed(1)}%`,
      icon: '📊',
      color: 'bg-purple-500',
      bgColor: 'bg-purple-50',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`${card.bgColor} rounded-lg shadow-md p-6 border-l-4 ${card.color}`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium mb-1">{card.title}</p>
              <p className="text-3xl font-bold text-gray-800">{card.value}</p>
            </div>
            <div className="text-4xl">{card.icon}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default MetricsCards;

