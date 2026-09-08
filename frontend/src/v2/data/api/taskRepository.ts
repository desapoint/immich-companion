import { requestJson } from '../../../lib/api/http';
import { openJsonSocket, type JsonSocketSubscription } from '../../../lib/api/taskStream';
import type { TaskRecord, TaskRepository, TaskState, TaskSubscription } from '../syncContracts';

type ApiTask = {
  id: string;
  task_type: string;
  status: TaskState;
  payload: Record<string, unknown>;
  checkpoint: Record<string, unknown>;
  counters: Record<string, number>;
  progress: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: { type?: string; message?: string } | null;
  attempt: number;
  next_attempt_at: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

function normalizeTask(task: ApiTask): TaskRecord {
  return {
    id: task.id,
    taskType: task.task_type,
    status: task.status,
    payload: task.payload ?? {},
    checkpoint: task.checkpoint ?? {},
    counters: task.counters ?? {},
    progress: task.progress ?? {},
    result: task.result,
    error: task.error,
    attempt: task.attempt,
    nextAttemptAt: task.next_attempt_at,
    createdAt: task.created_at,
    startedAt: task.started_at,
    completedAt: task.completed_at,
  };
}

export function createTaskRepository(): TaskRepository {
  return {
    get: async (taskId, signal) => normalizeTask(await requestJson<ApiTask>(`/api/tasks/${encodeURIComponent(taskId)}`, { signal })),
    cancel: async (taskId) => normalizeTask(await requestJson<ApiTask>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' })),
    list: async (taskType, limit = 10, signal) => {
      const tasks = await requestJson<ApiTask[]>(`/api/tasks?task_type=${encodeURIComponent(taskType)}&limit=${limit}`, { signal });
      return tasks.map(normalizeTask);
    },
    subscribe(handlers): TaskSubscription {
      let closed = false;
      let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
      let socket: JsonSocketSubscription | null = null;

      const connect = (reconnecting = false) => {
        if (closed) return;
        handlers.onConnectionState(reconnecting ? 'reconnecting' : 'connecting');
        socket = openJsonSocket<ApiTask>('/api/tasks/stream', {
          onopen: () => handlers.onConnectionState('connected'),
          onmessage: (task) => {
            if (task.id) handlers.onTask(normalizeTask(task));
          },
          onerror: () => handlers.onError?.(new Error('Task update connection encountered an error.')),
          onclose: () => {
            socket = null;
            if (closed) return;
            handlers.onConnectionState('reconnecting');
            reconnectTimer = setTimeout(() => connect(true), 2000);
          },
        });
      };

      connect();
      return {
        close() {
          closed = true;
          if (reconnectTimer) clearTimeout(reconnectTimer);
          socket?.close();
          socket = null;
          handlers.onConnectionState('disconnected');
        },
      };
    },
  };
}
