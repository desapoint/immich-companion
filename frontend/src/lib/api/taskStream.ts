export type JsonSocketHandlers<T> = {
  onopen?: () => void;
  onmessage: (value: T) => void;
  onerror?: () => void;
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
      handlers.onerror?.();
    }
  };
  socket.onerror = () => handlers.onerror?.();
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
