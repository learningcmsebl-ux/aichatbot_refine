import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('React Error Boundary caught an error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#f3f4f6',
          padding: '20px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
            padding: '32px',
            maxWidth: '600px',
            width: '100%'
          }}>
            <h1 style={{
              fontSize: '24px',
              fontWeight: 600,
              color: '#dc2626',
              marginBottom: '16px'
            }}>
              Application Error
            </h1>
            <p style={{
              color: '#374151',
              marginBottom: '16px',
              lineHeight: '1.5'
            }}>
              An error occurred while loading the application. Please check the browser console for more details.
            </p>
            {this.state.error && (
              <div style={{
                backgroundColor: '#f9fafb',
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '16px',
                border: '1px solid #e5e7eb'
              }}>
                <p style={{
                  fontSize: '14px',
                  fontFamily: 'monospace',
                  color: '#dc2626',
                  marginBottom: '8px',
                  fontWeight: 600
                }}>
                  {this.state.error.message}
                </p>
                {this.state.error.stack && (
                  <pre style={{
                    fontSize: '12px',
                    color: '#6b7280',
                    marginTop: '8px',
                    overflow: 'auto',
                    maxHeight: '200px',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                  }}>
                    {this.state.error.stack}
                  </pre>
                )}
              </div>
            )}
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              style={{
                backgroundColor: '#0057a6',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                padding: '12px 24px',
                fontSize: '16px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#004080';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#0057a6';
              }}
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
