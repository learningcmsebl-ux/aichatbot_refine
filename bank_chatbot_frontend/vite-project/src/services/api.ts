import type { ChatRequest, ChatResponse } from '../types';

// Use relative path in dev (Vite proxy) or env variable for production
const API_BASE = import.meta.env.VITE_API_URL || '/api';

export class ChatAPI {
  private baseUrl: string;
  private clientIp: string | null = null;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
    // Fetch client IP on initialization
    this.fetchClientIp();
  }

  private async fetchClientIp(): Promise<void> {
    // First, try to get local IP using WebRTC (for local network IPs like 192.168.x.x)
    try {
      const localIp = await this.getLocalIpViaWebRTC();
      if (localIp && this.isLocalNetworkIp(localIp)) {
        this.clientIp = localIp;
        console.log('✓ Detected local IP via WebRTC:', localIp);
        return;
      } else if (localIp) {
        console.warn('WebRTC returned non-local IP, ignoring:', localIp);
      }
    } catch (error) {
      console.warn('WebRTC IP detection failed:', error);
    }

    // If WebRTC didn't return a local IP, we'll let the backend detect it
    // Don't use public IP services - we want local network IPs only
    console.log('WebRTC did not return local IP, will rely on backend detection');
    this.clientIp = null;
  }

  private isLocalNetworkIp(ip: string): boolean {
    // Check if IP is a local network address
    if (!ip || ip === '0.0.0.0') return false;
    
    // IPv4 local network ranges
    if (ip.startsWith('192.168.')) return true;
    if (ip.startsWith('10.')) return true;
    if (ip.startsWith('172.')) {
      const parts = ip.split('.');
      if (parts.length === 4) {
        const secondOctet = parseInt(parts[1], 10);
        if (secondOctet >= 16 && secondOctet <= 31) {
          return true; // 172.16.0.0 - 172.31.255.255
        }
      }
    }
    
    // IPv6 local addresses
    if (ip.startsWith('fe80:') || ip.startsWith('fc00:') || ip.startsWith('fd00:')) {
      return true;
    }
    
    return false;
  }

  private async getLocalIpViaWebRTC(): Promise<string | null> {
    return new Promise((resolve) => {
      const RTCPeerConnection = window.RTCPeerConnection || 
                                (window as any).webkitRTCPeerConnection || 
                                (window as any).mozRTCPeerConnection;

      if (!RTCPeerConnection) {
        console.warn('WebRTC not supported in this browser');
        resolve(null);
        return;
      }

      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });

      const localIps: string[] = [];
      const allIps: string[] = [];
      const ipRegex = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7})/g;

      pc.createDataChannel('');

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          const candidate = event.candidate.candidate;
          const match = candidate.match(ipRegex);
          if (match) {
            const ip = match[0];
            if (ip && !allIps.includes(ip)) {
              allIps.push(ip);
              
              // Check if it's a local network IP
              if (this.isLocalNetworkIp(ip)) {
                if (!localIps.includes(ip)) {
                  localIps.push(ip);
                  console.log('Found local IP via WebRTC:', ip);
                }
              } else {
                console.log('Found non-local IP (ignoring):', ip);
              }
            }
          }
        } else {
          // All ICE candidates have been received
          pc.close();
          console.log('WebRTC candidates complete. Local IPs found:', localIps);
          if (localIps.length > 0) {
            // Return the first local IP found (usually the most relevant)
            resolve(localIps[0]);
          } else {
            console.warn('No local network IP found via WebRTC. All IPs:', allIps);
            resolve(null);
          }
        }
      };

      pc.createOffer()
        .then(offer => pc.setLocalDescription(offer))
        .catch(err => {
          console.warn('WebRTC offer creation failed:', err);
          resolve(null);
        });

      // Timeout after 5 seconds (increased for better detection)
      setTimeout(() => {
        pc.close();
        console.log('WebRTC timeout. Local IPs found:', localIps);
        if (localIps.length > 0) {
          resolve(localIps[0]);
        } else {
          console.warn('No local network IP found via WebRTC (timeout). All IPs:', allIps);
          resolve(null);
        }
      }, 5000);
    });
  }

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    let response: Response;
    try {
      // Ensure we have the client IP
      if (!this.clientIp) {
        await this.fetchClientIp();
      }
      
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      // Add client IP header if available
      if (this.clientIp) {
        headers['X-Client-IP'] = this.clientIp;
      }
      
      response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          ...request,
          stream: false,
        }),
      });
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        throw new Error('Failed to connect to the server. Please check if the backend is running.');
      }
      throw err;
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! status: ${response.status}: ${errorText}`);
    }

    return response.json();
  }

  async *streamMessage(request: ChatRequest): AsyncGenerator<string, void, unknown> {
    let response: Response;
    try {
      // Ensure we have the client IP
      if (!this.clientIp) {
        await this.fetchClientIp();
      }
      
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      // Add client IP header if available
      if (this.clientIp) {
        headers['X-Client-IP'] = this.clientIp;
      }
      
      response = await fetch(`${this.baseUrl}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          ...request,
          stream: true,
        }),
      });
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        throw new Error('Failed to connect to the server. Please check if the backend is running.');
      }
      throw err;
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! status: ${response.status}: ${errorText}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported in this browser.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          // Flush any remaining decoded content
          const remaining = decoder.decode();
          if (remaining) {
            yield remaining;
          }
          break;
        }

        // Decode chunk (use stream: true to handle multi-byte UTF-8 characters correctly)
        // The decoder will hold back incomplete UTF-8 sequences until the next chunk
        const decodedChunk = decoder.decode(value, { stream: true });
        
        // Yield only the newly decoded chunk
        // The frontend accumulates these chunks in fullResponse
        if (decodedChunk) {
          yield decodedChunk;
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async getHistory(sessionId: string, limit: number = 50) {
    const response = await fetch(`${this.baseUrl}/chat/history/${sessionId}?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Failed to get history: ${response.statusText}`);
    }
    return response.json();
  }

  async clearHistory(sessionId: string) {
    const response = await fetch(`${this.baseUrl}/chat/history/${sessionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Failed to clear history: ${response.statusText}`);
    }
    return response.json();
  }
}

export const chatAPI = new ChatAPI();

