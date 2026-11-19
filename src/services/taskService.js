import { api } from './api';

export const taskService = {
  async getTasks(params = {}) {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.priority) query.append('priority', params.priority);
    if (params.category) query.append('category', params.category);
    if (params.taskType) query.append('taskType', params.taskType);
    if (params.search) query.append('search', params.search);
    if (params.isToday !== undefined) query.append('isToday', String(params.isToday));
    if (params.isOverdue !== undefined) query.append('isOverdue', String(params.isOverdue));
    if (params.skip !== undefined) query.append('skip', String(params.skip));
    if (params.limit !== undefined) query.append('limit', String(params.limit));

    const queryString = query.toString();
    const endpoint = queryString ? `/tasks?${queryString}` : '/tasks';
    return await api.get(endpoint);
  },

  async getTaskById(taskId) {
    return await api.get(`/tasks/${taskId}`);
  },

  async createTask(taskData) {
    return await api.post('/tasks', taskData);
  },

  async updateTask(taskId, taskData) {
    return await api.put(`/tasks/${taskId}`, taskData);
  },

  async deleteTask(taskId) {
    return await api.delete(`/tasks/${taskId}`);
  },

  async markComplete(taskId) {
    return await api.patch(`/tasks/${taskId}/complete`);
  },

  async markPending(taskId) {
    return await api.patch(`/tasks/${taskId}/pending`);
  },
};
