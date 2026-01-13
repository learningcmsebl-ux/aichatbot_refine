import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Dashboard Error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-lg p-8 max-w-2xl">
            <h1 className="text-2xl font-bold text-red-600 mb-4">Dashboard Error</h1>
            <p className="text-gray-700 mb-4">
              An error occurred while loading the dashboard. Please check the console for details.
            </p>
            {this.state.error && (
              <div className="bg-gray-100 p-4 rounded mb-4">
                <p className="text-sm font-mono text-red-600">{this.state.error.message}</p>
                {this.state.error.stack && (
                  <pre className="text-xs text-gray-600 mt-2 overflow-auto max-h-64">
                    {this.state.error.stack}
                  </pre>
                )}
              </div>
            )}
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-bank-blue-500 text-white rounded hover:bg-bank-blue-600"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

