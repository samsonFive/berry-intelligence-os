import { useQuery } from '@tanstack/react-query';
import { getInvestigation } from '../../api/client';
import { useInvestigation } from '../../state/InvestigationProvider';
import { serializeInvestigation } from '../../contracts/investigation';
import type { InvestigationContext } from '../../contracts/investigation';

export function useReadModel<T>(endpoint: string, context: InvestigationContext, enabled = true) {
  const { revision } = useInvestigation();
  return useQuery({
    queryKey: ['investigation', endpoint, serializeInvestigation(context)],
    queryFn: ({ signal }) => getInvestigation<T>(endpoint, context, revision, signal),
    enabled,
  });
}
