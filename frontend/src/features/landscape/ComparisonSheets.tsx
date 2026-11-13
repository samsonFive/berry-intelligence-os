import { useMemo, type ReactNode } from 'react';
import { Badge, EntityButton } from '../../components/ui';
import { useInvestigation } from '../../state/InvestigationProvider';
import { BrandMediaGallery } from '../brand-media/BrandMedia';
import { VerifiedCompanyLogo } from '../brand-media/VerifiedCompanyLogo';
import { useBrandMedia } from '../brand-media/useBrandMedia';
import { WorkspaceSheet, useComparisonSheetKey, type WorkspaceSheetColumn, type WorkspaceSheetRow, type WorkspaceSheetCell } from '../grids/WorkspaceSheet';
import { Citation } from './Citation';
import type { ComparisonModel, LandscapeModel } from './models';

const unknown = <span className="berry-unknown" aria-label="Unknown: no recorded observation">—</span>;
const cell = (text: string, content: ReactNode): WorkspaceSheetCell => ({ text, content });

export function ComparisonSheets({ result, model, onReady }: { result: ComparisonModel; model: LandscapeModel; onReady: (ready: boolean) => void }) {
  const { dispatch } = useInvestigation();
  const ids = result.comparison_kind === 'company' ? result.companies.map(row => row.id) : result.varieties.map(row => row.id);
  const viewKey = useComparisonSheetKey(result.comparison_kind, ids);
  const media = useBrandMedia(result.comparison_kind === 'company' ? ids : []);
  const columns = useMemo<WorkspaceSheetColumn[]>(() => [
    { id: 'dimension', label: result.comparison_kind === 'company' ? 'Recorded dimension' : 'Recorded observation', width: 220, frozen: true },
    ...(result.comparison_kind === 'company' ? result.companies.map(company => ({ id: `company.${company.id}`, label: company.name, width: 300,
      header: <div className="berry-comparison-identity"><VerifiedCompanyLogo id={company.id} name={company.name} companyIds={ids} inspectable />
        <EntityButton compact name={company.name} onClick={() => dispatch({ type: 'focusEntity', entity: { id: company.id, type: 'company' }, origin: 'grid' })} /></div> }))
      : result.varieties.map(variety => { const name = model.nodes[variety.id]?.label ?? variety.identity?.display_name ?? variety.identity?.name ?? variety.id;
        return { id: `variety.${variety.id}`, label: name, width: 340, header: <EntityButton compact name={name}
          onClick={() => dispatch({ type: 'focusEntity', entity: { id: variety.id, type: 'variety' }, origin: 'grid' })} /> }; })),
  ], [result, model.nodes, dispatch]);
  const rows = useMemo<WorkspaceSheetRow[]>(() => {
    const output: WorkspaceSheetRow[] = [];
    const add = (id: string, label: string, cells: Record<string, WorkspaceSheetCell>) => output.push({ id, cells: { dimension: cell(label, label), ...cells } });
    if (result.comparison_kind === 'company') {
      const companies = result.companies;
      if (companies.some(company => media?.[company.id]?.packaging.length)) add('packaging', 'Retail packaging', Object.fromEntries(companies.map(company =>
        [`company.${company.id}`, cell(company.name + ' Retail packaging', <BrandMediaGallery compact model={media?.[company.id]} />)])));
      add('berries', 'Declared berry portfolio', Object.fromEntries(companies.map(company => [`company.${company.id}`, cell(company.berries.join(' · '), company.berries.join(' · ') || unknown)])));
      for (const role of result.role_matrix) add(`role.${role.bucket}`, role.label, Object.fromEntries(companies.map(company => {
        const parties = company.roles[role.bucket] ?? [];
        return [`company.${company.id}`, cell(parties.map(party => party.name || model.nodes[party.id]?.label || party.id).join(' · '), parties.length
          ? <ul className="berry-comparison-list berry-cell-grid">{parties.map(party => <li key={party.id}><button type="button" className="berry-text-button"
            onClick={() => dispatch({ type: 'openDetail', detail: { type: 'variety', id: party.id }, origin: 'grid' })}>{party.name || model.nodes[party.id]?.label || party.id}</button></li>)}</ul> : unknown)];
      })));
      add('geography', 'Recorded geographic context', Object.fromEntries(companies.map(company => [`company.${company.id}`, cell(company.geographies.map(geo => geo.name).join(' · '), <>
        {company.geographies.length ? <ul className="berry-comparison-list berry-cell-grid berry-cell-grid--places">{company.geographies.map(geo => <li key={geo.id}><button type="button" className="berry-text-button"
          onClick={() => dispatch({ type: 'openDetail', detail: { type: 'geography', id: geo.id }, origin: 'grid' })}>{geo.name}</button></li>)}</ul> : unknown}
        <p className="berry-material-caveat">Profile geography includes distinct company/observation bases; inspect before inferring growing.</p></>)])));
      add('rights', 'Published rights records', Object.fromEntries(companies.map(company => [`company.${company.id}`, cell(company.rights_published.map(row => [row.title, row.kind, row.id].filter(Boolean).join(' ')).join(' · '), company.rights_published.length
        ? <ul className="berry-comparison-list berry-cell-grid berry-cell-grid--sources">{company.rights_published.map(row => <li key={row.id}><Citation id={row.id} />{row.kind && <span className="berry-material-caveat"> {row.kind}</span>}</li>)}</ul> : unknown)])));
    } else {
      result.dimensions.forEach((dimension, dimensionIndex) => add(`observation.${dimensionIndex}`, dimension.name, Object.fromEntries(result.varieties.map(variety => {
        const value = dimension.cells.find(item => item.variety_id === variety.id);
        return [`variety.${variety.id}`, cell(value?.has_data ? value.rows.map(row => [row.statement, row.fact_status, ...(row.does_not_prove ?? [])].filter(Boolean).join(' ')).join(' · ') : '',
          value?.has_data ? value.rows.map((row, index) => <div key={`${row.id}-${index}`} className="berry-observation"><p>{row.statement}</p>
            {row.fact_status && <Badge>{row.fact_status}</Badge>}{row.evidence_id && <Citation id={row.evidence_id} />}
            {!!row.does_not_prove?.length && <p className="berry-material-caveat">{row.does_not_prove.join(' · ')}</p>}</div>) : unknown)];
      }))));
      add('commercial-markets', 'Observed commercial markets', Object.fromEntries(result.varieties.map(variety => [`variety.${variety.id}`, cell(variety.countries_observed.map(geo => geo.name).join(' · '), <>
        {variety.countries_observed.map(geo => geo.name).join(' · ') || unknown}<p className="berry-material-caveat">Observed market does not establish growing origin.</p></>)])));
    }
    return output;
  }, [result, model.nodes, media, dispatch]);
  if (!viewKey) return <p role="status">Preparing comparison columns…</p>;
  return <><WorkspaceSheet key={viewKey} label={`Recorded ${result.comparison_kind === 'company' ? 'company' : 'cultivar'} comparison`} viewKey={viewKey} columns={columns} rows={rows} onReady={onReady} />
    {result.comparison_kind === 'variety' && !result.dimensions.length && <p className="berry-scope-note berry-comparison-footnote">No comparable sourced trait dimensions are recorded for these selected cultivars. Missing observations are unknown.</p>}</>;
}
