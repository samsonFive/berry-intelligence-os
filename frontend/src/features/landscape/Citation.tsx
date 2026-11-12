import { SourceLink } from '../../components/ui';
import { useInvestigation } from '../../state/InvestigationProvider';
import type { DetailType } from '../../contracts/investigation';
import type { SourceMetadata } from './models';

export function Citation({ id, source, parent }: { id: string; source?: SourceMetadata; parent?: { type: DetailType; id: string } }) {
  const { dispatch } = useInvestigation();
  return <SourceLink href={`/intelligence/${encodeURIComponent(id)}?personal=1`}
    onOpen={() => {
      if (parent) dispatch({ type: 'openDetail', detail: parent, origin: 'direct' });
      dispatch({ type: 'openDetail', detail: { type: 'source', id }, origin: 'direct' });
    }}
    title={source?.title}>{source?.source_name ?? 'Supporting source'}{source?.number ? ` [${source.number}]` : ''}</SourceLink>;
}
