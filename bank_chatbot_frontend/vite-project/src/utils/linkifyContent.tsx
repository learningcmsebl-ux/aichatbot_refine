import React from 'react';

const LINK_PATTERN = /(https?:\/\/[^\s<>"']+|\/api\/(?:forms|soc|proposals)\/download\/\d+|\/api\/leadership\/photo\/\d+)/g;
const PHOTO_LINE_PATTERN = /^(\s*)Photo:\s*(\S+)\s*$/i;

function trimTrailingPunctuation(url: string): { href: string; trailing: string } {
  let href = url;
  let trailing = '';
  while (/[),.;:!?]+$/.test(href)) {
    trailing = href.slice(-1) + trailing;
    href = href.slice(0, -1);
  }
  return { href, trailing };
}

function isFormDownloadLink(href: string): boolean {
  return /\/(?:forms|soc|proposals)\/download\/\d+(?:\?|$)/.test(href);
}

function isLeadershipPhotoLink(href: string): boolean {
  return /\/leadership\/photo\/\d+(?:\?|$)/.test(href);
}

function linkLabel(href: string): string {
  if (isFormDownloadLink(href)) {
    if (/\/soc\/download\//.test(href)) {
      return 'Download schedule';
    }
    if (/\/proposals\/download\//.test(href)) {
      return 'Download guide';
    }
    return 'Download form';
  }
  if (isLeadershipPhotoLink(href)) {
    return 'View photo';
  }
  return href;
}

/**
 * Turn plain-text URLs (and /api/forms/download paths) into clickable links.
 * Form download links use same-origin proxy URLs so the browser saves the file.
 */
export function linkifyContent(text: string, keyPrefix = ''): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  LINK_PATTERN.lastIndex = 0;
  while ((match = LINK_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(
        <React.Fragment key={`${keyPrefix}t-${key++}`}>
          {text.slice(lastIndex, match.index)}
        </React.Fragment>,
      );
    }

    const { href, trailing } = trimTrailingPunctuation(match[0]);
    const downloadLink = isFormDownloadLink(href);

    if (isLeadershipPhotoLink(href)) {
      nodes.push(
        <div key={`${keyPrefix}img-inline-${key++}`} className="msg-leader-photo msg-leader-photo--inline">
          <img src={href} alt="Leadership profile" loading="lazy" />
        </div>,
      );
    } else {
      nodes.push(
        <a
          key={`${keyPrefix}u-${key++}`}
          href={href}
          target={downloadLink ? undefined : '_blank'}
          rel={downloadLink ? undefined : 'noopener noreferrer'}
          download={downloadLink ? '' : undefined}
          className={downloadLink ? 'msg-link msg-link--download' : 'msg-link'}
        >
          {linkLabel(href)}
        </a>,
      );
    }

    if (trailing) {
      nodes.push(<React.Fragment key={`${keyPrefix}p-${key++}`}>{trailing}</React.Fragment>);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(
      <React.Fragment key={`${keyPrefix}t-${key++}`}>{text.slice(lastIndex)}</React.Fragment>,
    );
  }

  return nodes.length > 0 ? nodes : [text];
}

/**
 * Render chat text with inline leadership portraits on dedicated Photo: lines.
 */
export function renderMessageContent(text: string): React.ReactNode {
  const lines = text.split('\n');
  const nodes: React.ReactNode[] = [];
  const textBuffer: string[] = [];
  let key = 0;

  const flushText = () => {
    if (textBuffer.length === 0) {
      return;
    }
    const chunk = textBuffer.join('\n');
    textBuffer.length = 0;
    if (!chunk) {
      return;
    }
    nodes.push(
      <React.Fragment key={`block-${key++}`}>{linkifyContent(chunk, `b${key}-`)}</React.Fragment>,
    );
  };

  for (const line of lines) {
    const photoMatch = line.match(PHOTO_LINE_PATTERN);
    if (photoMatch) {
      flushText();
      const url = photoMatch[2];
      const compact = photoMatch[1].length > 0;
      nodes.push(
        <div
          key={`photo-${key++}`}
          className={compact ? 'msg-leader-photo msg-leader-photo--compact' : 'msg-leader-photo'}
        >
          <img src={url} alt="Leadership profile" loading="lazy" />
        </div>,
      );
      continue;
    }

    textBuffer.push(line);
  }

  flushText();
  return nodes.length > 0 ? nodes : text;
}
