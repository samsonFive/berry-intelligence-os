import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { InvestigationApiError } from '../../api/client';
import { clearPrivateSession, SESSION_TRANSITION_EVENT } from '../../app/PrivateQueryProvider';
import { Button } from '../../components/ui';
import { CompanyTierConflict, EDITABLE_COMPANY_TIERS, saveCompanyTier } from './company-tier';
import type { MonitoringCompany } from './models';

/** Tier is the existing analyst mark; saving does not dispatch selector actions. */
export function CompanyTierControl({ company, disabled, saved }: { company: MonitoringCompany; disabled: boolean; saved: (message: string) => void }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState(company.assigned_tier), [pending, setPending] = useState(false);
  const [error, setError] = useState(''), [conflict, setConflict] = useState(false), [ended, setEnded] = useState(false);
  const serial = useRef(0), request = useRef<AbortController | null>(null);
  useEffect(() => { setDraft(company.assigned_tier); setError(''); setConflict(false); }, [company.id, company.assigned_tier]);
  useEffect(() => {
    const clear = () => { serial.current++; request.current?.abort(); setPending(false); setEnded(true); };
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    return () => { serial.current++; request.current?.abort(); window.removeEventListener(SESSION_TRANSITION_EVENT, clear); };
  }, []);
  const reload = () => client.invalidateQueries({ predicate: query => query.queryKey[0] === 'investigation' && typeof query.queryKey[1] === 'string' && query.queryKey[1].startsWith('/monitoring?') });
  const save = async () => {
    if (disabled || pending || conflict || ended || !company.assigned_tier || draft === company.assigned_tier) return;
    const attempt = ++serial.current, controller = new AbortController(); request.current = controller;
    setPending(true); setError('');
    try {
      const result = await saveCompanyTier(company.id, draft, company.assigned_tier, controller.signal);
      if (serial.current !== attempt) return;
      saved(`${company.label} assigned to ${result.assigned_tier_label}. The roster has been refreshed by tier.`);
      await reload();
    } catch (cause) {
      if (serial.current !== attempt || controller.signal.aborted) return;
      if (cause instanceof InvestigationApiError && cause.requiresSession) clearPrivateSession();
      if (cause instanceof CompanyTierConflict) { setConflict(true); setError(`${cause.message} Current saved tier: ${cause.current.assigned_tier_label}.`); }
      else setError(cause instanceof Error ? cause.message : 'The company tier could not be saved.');
    } finally { if (serial.current === attempt) setPending(false); }
  };
  if (!company.assigned_tier) return <span className="berry-material-caveat">Assigned tier unavailable</span>;
  const legacy = !EDITABLE_COMPANY_TIERS.some(option => option.value === company.assigned_tier);
  return <div className="berry-company-tier" data-assigned-tier={company.assigned_tier}>
    <label>Tier<select aria-label={`Assigned tier for ${company.label}`} value={draft} disabled={disabled || pending || conflict || ended} onChange={event => setDraft(event.target.value)}>
      {EDITABLE_COMPANY_TIERS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      {legacy && <option value={company.assigned_tier}>{company.assigned_tier_label} · retained legacy</option>}
    </select></label>
    <Button size="small" variant="ghost" busy={pending} disabled={disabled || pending || conflict || ended || draft === company.assigned_tier} aria-label={`Save tier for ${company.label}`} onClick={() => void save()}>Save tier</Button>
    {error && <p className="berry-roster-tier-error" role="alert">{error}</p>}
    {conflict && <Button size="small" variant="ghost" onClick={() => void reload()}>Reload roster</Button>}
  </div>;
}
