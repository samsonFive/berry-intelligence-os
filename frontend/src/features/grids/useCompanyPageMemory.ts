import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';
import { SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import { parseInvestigation, sameContext } from '../../contracts/investigation';
import { useInvestigation } from '../../state/InvestigationProvider';
import { COMPANY_COLUMNS_PER_PAGE } from './company-pages';
import { CompanyPageMemory, companyUniverseIdentity } from './company-page-memory';
import type { CompanyPageEntry } from './company-page-memory';

const memory = new CompanyPageMemory();
// This listener outlives a grid/lens mount. Ordinary bfcache return retains the
// UI indexes; an explicit private-session transition invalidates every old epoch.
if (typeof window !== 'undefined') window.addEventListener(SESSION_TRANSITION_EVENT, () => memory.clear());

export function useCompanyPageMemory(companies: readonly { id: string }[]) {
  const location = useLocation();
  const navigation = useNavigationType();
  const { context } = useInvestigation();
  const universe = useMemo(() => companyUniverseIdentity(companies), [companies]);
  const count = Math.max(1, Math.ceil(companies.length / COMPANY_COLUMNS_PER_PAGE));
  const contextMatches = sameContext(parseInvestigation(location.search).context, context);
  const epoch = useRef(memory.epoch).current;
  const [mounted, setMounted] = useState<CompanyPageEntry | null>(null);
  const request = { key: location.key, universe, count, contextMatches, epoch };
  const ready = contextMatches && epoch === memory.epoch;
  const index = ready && mounted?.key === location.key && mounted.universe === universe
    ? Math.min(count - 1, mounted.index) : memory.resolve(request, navigation, mounted);

  useLayoutEffect(() => {
    const current = { key: location.key, universe, count, contextMatches, epoch };
    if (!memory.remember(current, index)) return;
    setMounted(previous => previous?.key === location.key && previous.universe === universe && previous.index === index && previous.epoch === epoch
      ? previous : { key: location.key, universe, index, epoch });
  }, [location.key, universe, count, contextMatches, epoch, index]);

  const setIndex = useCallback((next: number) => {
    if (!memory.remember({ key: location.key, universe, count, contextMatches, epoch }, next)) return;
    setMounted({ key: location.key, universe, index: Math.max(0, Math.min(count - 1, Number.isSafeInteger(next) ? next : 0)), epoch });
  }, [location.key, universe, count, contextMatches, epoch]);
  return { index, setIndex, ready };
}
