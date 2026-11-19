import { api } from './api';

export const recommendationService = {
  async getRecommendations({ status = 'PENDING', category = null, rec_type = null, limit = 50 } = {}) {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (category) params.append('category', category);
    if (rec_type) params.append('rec_type', rec_type);
    if (limit) params.append('limit', limit);
    const q = params.toString() ? `?${params.toString()}` : '';
    return api.get(`/recommendations${q}`);
  },

  async generateRecommendations() {
    return api.post('/recommendations/generate');
  },

  async acceptRecommendation(id) {
    return api.post(`/recommendations/${id}/accept`);
  },

  async dismissRecommendation(id) {
    return api.post(`/recommendations/${id}/dismiss`);
  },

  async completeRecommendation(id) {
    return api.post(`/recommendations/${id}/complete`);
  },
};
