import { api } from './api';

export const analyticsService = {
  async getOverview(tzOffset = -new Date().getTimezoneOffset()) {
    return api.get(`/analytics/overview?tz_offset=${tzOffset}`);
  },

  async getDaily(dateStr = null, tzOffset = -new Date().getTimezoneOffset()) {
    const q = dateStr ? `&date=${dateStr}` : '';
    return api.get(`/analytics/daily?tz_offset=${tzOffset}${q}`);
  },

  async getWeekly(startDate = null, tzOffset = -new Date().getTimezoneOffset()) {
    const q = startDate ? `&start_date=${startDate}` : '';
    return api.get(`/analytics/weekly?tz_offset=${tzOffset}${q}`);
  },

  async getMonthly(year = null, month = null) {
    const params = new URLSearchParams();
    if (year) params.append('year', year);
    if (month) params.append('month', month);
    const q = params.toString() ? `?${params.toString()}` : '';
    return api.get(`/analytics/monthly${q}`);
  },

  async getTimeAnalytics(tzOffset = -new Date().getTimezoneOffset()) {
    return api.get(`/analytics/time?tz_offset=${tzOffset}`);
  },

  async getGoalAnalytics() {
    return api.get('/analytics/goals');
  },

  async getInsights(tzOffset = -new Date().getTimezoneOffset()) {
    return api.get(`/analytics/insights?tz_offset=${tzOffset}`);
  },
};
