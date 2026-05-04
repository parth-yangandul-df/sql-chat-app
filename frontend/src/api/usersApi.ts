import { api } from './client';
import type { User, UserCreate, UserUpdate } from '../types/api';

export const usersApi = {
  list: () => api.get<User[]>('/users').then(r => r.data),

  create: (data: UserCreate) =>
    api.post<User>('/users', data).then(r => r.data),

  update: (id: string, data: UserUpdate) =>
    api.patch<User>(`/users/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete<void>(`/users/${id}`).then(r => r.data),
};