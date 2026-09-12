export type JsonSocketHandlers<T> = {
  onopen?: () => void;
  onmessage: (value: T) => void;
  oninvalid?: (error: Error) => void;
  onclose?: () => void;
};

export type JsonSocketSubscription = {
  close(): void;
};

export function openJsonSocket<T>(path: string, handlers: JsonSocketHandlers<T>): JsonSocketSubscription {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${protocol}//${window.location.host}${path}`);
  let closedByClient = false;

  socket.onopen = () => handlers.onopen?.();
  socket.onmessage = (event) => {
    try {
      handlers.onmessage(JSON.parse(event.data) as T);
    } catch {
      handlers.oninvalid?.(new Error('WebSocket message was not valid JSON.'));
    }
  };
  socket.onerror = () => {
    if (!closedByClient) socket.close();
  };
  socket.onclose = () => {
    if (!closedByClient) handlers.onclose?.();
  };

  return {
    close() {
      closedByClient = true;
      socket.close();
    },
  };
}
