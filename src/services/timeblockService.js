import { api } from './api';

export const timeblockService = {
  async getTimeblocks(dateStr = null, status = null) {
    const params = new URLSearchParams();
    if (dateStr) params.append('date', dateStr);
    if (status) params.append('status', status);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return api.get(`/timeblocks${queryString}`);
  },

  async getTimeblockById(id) {
    return api.get(`/timeblocks/${id}`);
  },

  async createTimeblock(blockData) {
    return api.post('/timeblocks', blockData);
  },

  async updateTimeblock(id, updateData) {
    return api.put(`/timeblocks/${id}`, updateData);
  },

  async deleteTimeblock(id) {
    return api.delete(`/timeblocks/${id}`);
  },

  async getPlannedVsActual(startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return api.get(`/timeblocks/analytics/planned-vs-actual${queryString}`);
  },
};
