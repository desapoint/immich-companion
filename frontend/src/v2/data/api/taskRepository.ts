import { requestJson } from '../../../lib/api/http';
import { openJsonSocket, type JsonSocketSubscription } from '../../../lib/api/taskStream';
import type {
  TaskConnectionState,
  TaskRecord,
  TaskRepository,
  TaskState,
  TaskSubscription,
} from '../syncContracts';

type ApiTask = {
  id: string;
  task_type: string;
  status: TaskState;
  payload?: Record<string, unknown>;
  checkpoint?: Record<string, unknown>;
  counters?: Record<string, number>;
  progress?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: { type?: string; message?: string } | null;
  attempt?: number;
  next_attempt_at?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
};

type TaskHandlers = Parameters<TaskRepository['subscribe']>[0];

const TASK_STATES = new Set<TaskState>([
  'queued',
  'running',
  'retrying',
  'recovering',
  'cancel_requested',
  'cancelled',
  'completed',
  'failed',
]);
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const RECONNECT_JITTER = 0.2;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isApiTask(value: unknown): value is ApiTask {
  if (!isRecord(value)) return false;
  return typeof value.id === 'string'
    && value.id.length > 0
    && typeof value.task_type === 'string'
    && value.task_type.length > 0
    && typeof value.status === 'string'
    && TASK_STATES.has(value.status as TaskState);
}

export function taskReconnectDelayMs(attempt: number, random = Math.random): number {
  const boundedAttempt = Math.max(0, Math.floor(attempt));
  const base = Math.min(RECONNECT_BASE_MS * 2 ** boundedAttempt, RECONNECT_MAX_MS);
  const factor = 1 - RECONNECT_JITTER + random() * RECONNECT_JITTER * 2;
  return Math.min(RECONNECT_MAX_MS, Math.round(base * factor));
}

function normalizeTask(task: ApiTask): TaskRecord {
  return {
    id: task.id,
    taskType: task.task_type,
    status: task.status,
    payload: task.payload ?? {},
    checkpoint: task.checkpoint ?? {},
    counters: task.counters ?? {},
    progress: task.progress ?? {},
    result: task.result ?? null,
    error: task.error ?? null,
    attempt: task.attempt ?? 0,
    nextAttemptAt: task.next_attempt_at ?? null,
    createdAt: task.created_at ?? '',
    startedAt: task.started_at ?? null,
    completedAt: task.completed_at ?? null,
  };
}

function validatedTask(value: unknown): TaskRecord {
  if (!isApiTask(value)) throw new Error('Task response did not match the expected task contract.');
  return normalizeTask(value);
}

export function createTaskRepository(): TaskRepository {
  const subscribers = new Set<TaskHandlers>();
  let socket: JsonSocketSubscription | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempt = 0;
  let connectionState: TaskConnectionState = 'disconnected';
  let hasConnected = false;

  const publishState = (state: TaskConnectionState): void => {
    connectionState = state;
    for (const handlers of subscribers) handlers.onConnectionState(state);
  };

  const publishError = (error: Error): void => {
    for (const handlers of subscribers) handlers.onError?.(error);
  };

  const publishTask = (task: TaskRecord): void => {
    for (const handlers of subscribers) handlers.onTask(task);
  };

  const stopSocket = (): void => {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = null;
    socket?.close();
    socket = null;
    reconnectAttempt = 0;
    hasConnected = false;
    connectionState = 'disconnected';
  };

  const connect = (reconnecting = false): void => {
    if (subscribers.size === 0 || socket) return;
    publishState(reconnecting ? 'reconnecting' : 'connecting');
    socket = openJsonSocket<unknown>('/api/tasks/stream', {
      onopen: () => {
        const recovered = hasConnected;
        reconnectAttempt = 0;
        hasConnected = true;
        publishState('connected');
        if (recovered) {
          for (const handlers of subscribers) handlers.onRecovered?.();
        }
      },
      onmessage: (value) => {
        if (!isApiTask(value)) {
          publishError(new Error('Ignored malformed task update from the live task stream.'));
          return;
        }
        publishTask(normalizeTask(value));
      },
      oninvalid: (error) => publishError(error),
      onclose: () => {
        socket = null;
        if (subscribers.size === 0) return;
        publishState('reconnecting');
        const delay = taskReconnectDelayMs(reconnectAttempt++);
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect(true);
        }, delay);
      },
    });
  };

  return {
    get: async (taskId, signal) => validatedTask(await requestJson<unknown>(`/api/tasks/${encodeURIComponent(taskId)}`, { signal })),
    cancel: async (taskId) => validatedTask(await requestJson<unknown>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' })),
    list: async (taskType, limit = 10, signal) => {
      const values = await requestJson<unknown>(`/api/tasks?task_type=${encodeURIComponent(taskType)}&limit=${limit}`, { signal });
      if (!Array.isArray(values)) throw new Error('Task list response did not match the expected task contract.');
      return values.map(validatedTask);
    },
    subscribe(handlers): TaskSubscription {
      let closed = false;
      subscribers.add(handlers);
      if (subscribers.size === 1) connect();
      else handlers.onConnectionState(connectionState);

      return {
        close() {
          if (closed) return;
          closed = true;
          subscribers.delete(handlers);
          handlers.onConnectionState('disconnected');
          if (subscribers.size === 0) stopSocket();
        },
      };
    },
  };
}
