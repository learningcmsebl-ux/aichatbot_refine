export type VoiceErrorKind =
  | 'permission_denied'
  | 'no_speech'
  | 'unsupported'
  | 'generic';

export interface VoiceErrorInfo {
  kind: VoiceErrorKind;
  message: string;
  steps: string[];
}

type BrowserName = 'chrome' | 'edge' | 'firefox' | 'safari' | 'other';

function detectBrowser(): BrowserName {
  if (typeof navigator === 'undefined') return 'other';
  const ua = navigator.userAgent;
  if (/Edg\//.test(ua)) return 'edge';
  if (/Chrome\//.test(ua) && !/Edg\//.test(ua)) return 'chrome';
  if (/Firefox\//.test(ua)) return 'firefox';
  if (/Safari\//.test(ua) && !/Chrome\//.test(ua)) return 'safari';
  return 'other';
}

function siteLabel(): string {
  if (typeof window === 'undefined') return 'this site';
  return window.location.hostname || 'this site';
}

function permissionSteps(browser: BrowserName): string[] {
  const site = siteLabel();

  switch (browser) {
    case 'chrome':
    case 'edge':
      return [
        `Click the lock or tune icon to the left of the address bar on ${site}.`,
        'Open Site settings (or Permissions).',
        'Set Microphone to Allow.',
        'Reload this page, then click the microphone button again.',
      ];
    case 'firefox':
      return [
        `Click the permissions icon in the address bar on ${site}.`,
        'Clear the blocked Microphone permission or set it to Allow.',
        'If needed: Menu → Settings → Privacy & Security → Permissions → Microphone.',
        'Reload this page, then click the microphone button again.',
      ];
    case 'safari':
      return [
        'Safari → Settings for This Website (or the AA icon in the address bar).',
        'Set Microphone to Allow.',
        'Reload this page, then click the microphone button again.',
      ];
    default:
      return [
        'Open your browser site settings for this page.',
        'Allow microphone access for this website.',
        'Reload the page, then click the microphone button again.',
      ];
  }
}

export function buildPermissionDeniedError(): VoiceErrorInfo {
  return {
    kind: 'permission_denied',
    message: 'Microphone access is blocked for this site.',
    steps: permissionSteps(detectBrowser()),
  };
}

export function buildVoiceError(kind: VoiceErrorKind): VoiceErrorInfo {
  if (kind === 'permission_denied') {
    return buildPermissionDeniedError();
  }
  if (kind === 'no_speech') {
    return {
      kind,
      message: 'No speech detected.',
      steps: ['Move closer to the microphone and speak clearly, then try again.'],
    };
  }
  if (kind === 'unsupported') {
    return {
      kind,
      message: 'Voice input is not supported in this browser.',
      steps: ['Use Google Chrome or Microsoft Edge on desktop for voice input.'],
    };
  }
  return {
    kind: 'generic',
    message: 'Voice input failed.',
    steps: ['Check your microphone connection and try again.'],
  };
}

export async function queryMicPermissionState(): Promise<PermissionState | 'unknown'> {
  if (!navigator.permissions?.query) return 'unknown';
  try {
    const status = await navigator.permissions.query({
      name: 'microphone' as PermissionName,
    });
    return status.state;
  } catch {
    return 'unknown';
  }
}

/** Request mic access so the browser shows its permission prompt when possible. */
export async function requestMicrophoneAccess(): Promise<'granted' | 'denied' | 'unavailable'> {
  if (!navigator.mediaDevices?.getUserMedia) {
    return 'unavailable';
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach(track => track.stop());
    return 'granted';
  } catch (err) {
    const name = err instanceof DOMException ? err.name : '';
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      return 'denied';
    }
    return 'unavailable';
  }
}
