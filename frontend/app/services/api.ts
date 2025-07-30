import { API_ENDPOINTS } from '@/lib/constants';
import type { FindingsResponse, Statistics, UploadResponse, DocumentWithFindings } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
    throw new Error(error.detail || `HTTP error! status: ${response.status}`);
  }
  return response.json();
}

export const api = {
  async uploadPDF(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}${API_ENDPOINTS.upload}`, {
      method: 'POST',
      body: formData,
    });

    return handleResponse<UploadResponse>(response);
  },

  async getFindings(page = 1, pageSize = 20): Promise<FindingsResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    const response = await fetch(`${API_URL}${API_ENDPOINTS.findings}?${params}`);
    return handleResponse<FindingsResponse>(response);
  },

  async getDocumentFindings(documentId: string): Promise<DocumentWithFindings> {
    const response = await fetch(`${API_URL}${API_ENDPOINTS.findingsById(documentId)}`);
    return handleResponse<DocumentWithFindings>(response);
  },

  async getStatistics(): Promise<Statistics> {
    const response = await fetch(`${API_URL}${API_ENDPOINTS.stats}`);
    return handleResponse<Statistics>(response);
  },
};