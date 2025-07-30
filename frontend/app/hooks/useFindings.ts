import useSWR from 'swr';
import { api } from '@/services/api';

export function useFindings(page = 1, pageSize = 20) {
  const { data, error, isLoading, mutate } = useSWR(
    ['findings', page, pageSize],
    () => api.getFindings(page, pageSize),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    findings: data,
    isLoading,
    isError: error,
    mutate,
  };
}