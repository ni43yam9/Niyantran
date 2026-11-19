import { api } from './api';

export const habitService = {
  async getHabits(includeArchived = false) {
    const query = includeArchived ? '?includeArchived=true' : '';
    return api.get(`/habits${query}`);
  },

  async getHabitById(id) {
    return api.get(`/habits/${id}`);
  },

  async createHabit(habitData) {
    return api.post('/habits', habitData);
  },

  async updateHabit(id, updateData) {
    return api.put(`/habits/${id}`, updateData);
  },

  async deleteHabit(id) {
    return api.delete(`/habits/${id}`);
  },

  async toggleHabitLog(id, dateStr, completed = null) {
    let url = `/habits/${id}/toggle?date=${dateStr}`;
    if (completed !== null && completed !== undefined) {
      url += `&completed=${completed}`;
    }
    return api.post(url);
  },
};
