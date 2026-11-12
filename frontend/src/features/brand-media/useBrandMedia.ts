import { useQuery } from '@tanstack/react-query';
import { getBrandMedia } from './api';

/** Explicit detail/cohort IDs only. Browsing and hover never acquire imagery. */
export function useBrandMedia(ids: readonly string[]) {
  const selected = [...new Set(ids)];
  const query = useQuery({
    queryKey: ['entity-brand-media', selected.join(',')],
    queryFn: ({ signal }) => getBrandMedia(selected, signal), enabled: selected.length > 0 && selected.length <= 20,
    staleTime: 0, gcTime: 0, retry: false, refetchOnMount: 'always', refetchOnWindowFocus: true,
    refetchInterval: 60_000,
  });
  // A failed refresh must not keep previously eligible imagery on screen.
  return query.isError ? undefined : query.data?.entities;
}
