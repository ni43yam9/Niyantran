import { api } from './api';

export const goalService = {
  async getGoals(params = {}) {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.priority) query.append('priority', params.priority);
    if (params.goalType || params.type) query.append('goalType', params.goalType || params.type);
    if (params.category) query.append('category', params.category);
    if (params.search) query.append('search', params.search);
    if (params.skip !== undefined) query.append('skip', String(params.skip));
    if (params.limit !== undefined) query.append('limit', String(params.limit));

    const queryString = query.toString();
    const endpoint = queryString ? `/goals?${queryString}` : '/goals';
    return await api.get(endpoint);
  },

  async getGoalById(goalId) {
    return await api.get(`/goals/${goalId}`);
  },

  async createGoal(goalData) {
    return await api.post('/goals', goalData);
  },

  async updateGoal(goalId, goalData) {
    return await api.put(`/goals/${goalId}`, goalData);
  },

  async deleteGoal(goalId) {
    return await api.delete(`/goals/${goalId}`);
  },

  async updateProgress(goalId, progress, status = null) {
    return await api.patch(`/goals/${goalId}/progress`, {
      progress,
      ...(status ? { status } : {}),
    });
  },
};
