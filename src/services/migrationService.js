import { api } from './api';

export const migrationService = {
  async importFromLocalStorage(tasks = [], goals = [], habits = [], timeblocks = {}, overwrite = false) {
    return await api.post('/migration/import', {
      tasks,
      goals,
      habits,
      timeblocks,
      overwrite,
    });
  },

  async getStatus() {
    return await api.get('/migration/status');
  },
};
