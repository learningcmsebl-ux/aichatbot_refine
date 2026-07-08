import React from 'react';
import type { VoiceErrorInfo } from '../utils/micPermissionHelp';

interface MicPermissionHelpProps {
  error: VoiceErrorInfo;
  onRetry: () => void;
  onDismiss: () => void;
}

export const MicPermissionHelp: React.FC<MicPermissionHelpProps> = ({
  error,
  onRetry,
  onDismiss,
}) => {
  const isPermission = error.kind === 'permission_denied';

  return (
    <div
      className={`mic-permission-help${isPermission ? ' mic-permission-help--blocked' : ''}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="mic-permission-help__header">
        <span className="mic-permission-help__icon" aria-hidden="true">
          {isPermission ? '🎤' : 'ℹ️'}
        </span>
        <div>
          <p className="mic-permission-help__title">{error.message}</p>
          {isPermission && (
            <p className="mic-permission-help__subtitle">
              Allow microphone access in your browser, then try again.
            </p>
          )}
        </div>
      </div>

      <ol className="mic-permission-help__steps">
        {error.steps.map(step => (
          <li key={step}>{step}</li>
        ))}
      </ol>

      <div className="mic-permission-help__actions">
        <button type="button" className="mic-permission-help__retry" onClick={onRetry}>
          Try again
        </button>
        <button type="button" className="mic-permission-help__dismiss" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </div>
  );
};
