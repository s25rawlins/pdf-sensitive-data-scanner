export const API_ENDPOINTS = {
  upload: '/upload',
  findings: '/findings',
  findingsById: (id: string) => `/findings/${id}`,
  stats: '/findings/stats/summary',
} as const;

export const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
export const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
};