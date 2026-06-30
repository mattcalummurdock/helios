import { ensureAuth, getToken, getWsUrl } from "./auth";
import { isDemoMode } from "./demo";
import type { WsEvent } from "./types";

export type WsHandlers = {
  onEvent: (event: WsEvent) => void;
  onReconnect?: () => void;
  onStatus?: (connected: boolean) => void;
};

export class HeliosWebSocket {
  private ws: WebSocket | null = null;
  private handlers: WsHandlers;
  private reconnectAttempt = 0;
  private closed = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(handlers: WsHandlers) {
    this.handlers = handlers;
  }

  async connect(): Promise<void> {
    if (isDemoMode()) return;

    this.closed = false;
    await ensureAuth();
    const token = getToken();
    if (!token) throw new Error("No auth token");

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    const url = `${getWsUrl()}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.handlers.onStatus?.(true);
    };

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data as string) as WsEvent;
        if (data.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
          return;
        }
        this.handlers.onEvent(data);
      } catch {
        /* ignore malformed */
      }
    };

    ws.onclose = () => {
      this.handlers.onStatus?.(false);
      if (!this.closed) this.scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    const delay = Math.min(1000 * 2 ** this.reconnectAttempt, 30000);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
        this.handlers.onReconnect?.();
      } catch {
        this.scheduleReconnect();
      }
    }, delay);
  }

  disconnect(): void {
    this.closed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}
