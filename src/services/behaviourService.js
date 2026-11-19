import { api } from './api';

export const behaviourService = {
  async getSummary(tzOffset = -new Date().getTimezoneOffset()) {
    return api.get(`/behaviour/summary?tz_offset=${tzOffset}`);
  },

  async getTaskCompletion(tzOffset = -new Date().getTimezoneOffset()) {
    return api.get(`/behaviour/task-completion?tz_offset=${tzOffset}`);
  },

  async getPostponements() {
    return api.get('/behaviour/postponements');
  },

  async getTimeEstimation() {
    return api.get('/behaviour/time-estimation');
  },

  async getProductivityHours(tzOffset = -new Date().getTimezoneOffset()) {
    return api.get(`/behaviour/productivity-hours?tz_offset=${tzOffset}`);
  },

  async getHabitConsistency() {
    return api.get('/behaviour/habit-consistency');
  },

  async getDailyPlanning() {
    return api.get('/behaviour/daily-planning');
  },

  async recordActivity(activityData) {
    return api.post('/behaviour/activity', activityData);
  },

  async getActivities(params = {}) {
    const q = new URLSearchParams(params).toString();
    return api.get(`/behaviour/activities${q ? `?${q}` : ''}`);
  },
};
