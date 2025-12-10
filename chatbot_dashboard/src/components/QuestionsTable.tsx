import React from 'react';
import { format, parseISO } from 'date-fns';
import type { Question } from '../types';

interface QuestionsTableProps {
  questions: Question[];
}

const QuestionsTable: React.FC<QuestionsTableProps> = ({ questions }) => {
  if (questions.length === 0) {
    return (
      <p className="text-gray-500 text-center py-8">No questions found</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Question
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Asked
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Answer Rate
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Last Asked
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {questions.map((question, index) => (
            <tr key={index} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-sm text-gray-900 max-w-md">
                <div className="truncate" title={question.question}>
                  {question.question}
                </div>
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                <div className="flex flex-col">
                  <span className="font-semibold">{question.total_asked}</span>
                  <span className="text-xs text-gray-500">
                    {question.answered_count} answered, {question.unanswered_count} unanswered
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 text-sm">
                <div className="flex items-center">
                  <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                    <div
                      className={`h-2 rounded-full ${
                        (question.answer_rate ?? 0) >= 80
                          ? 'bg-green-500'
                          : (question.answer_rate ?? 0) >= 50
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${question.answer_rate ?? 0}%` }}
                    ></div>
                  </div>
                  <span className="text-gray-700 font-medium">{(question.answer_rate ?? 0).toFixed(1)}%</span>
                </div>
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {question.last_asked ? format(parseISO(question.last_asked), 'MMM dd, yyyy HH:mm') : 'N/A'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default QuestionsTable;

