import useSWR from 'swr';
import { api } from '@/services/api';

export function useStats() {
  const { data, error, isLoading } = useSWR(
    'statistics',
    api.getStatistics,
    {
      refreshInterval: 30000, // Refresh every 30 seconds
    }
  );

  return {
    stats: data,
    isLoading,
    isError: error,
  };
}