import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { EMPTY_CONTEXT, splitIds, type Berry, type InvestigationContext } from "../contracts/investigation";
import { getInvestigation } from "../api/client";
import { useInvestigation } from "../state/InvestigationProvider";

export function InvestigationScopeBar() {
  const { context, dispatch } = useInvestigation();
  const [draft, setDraft] = useState(context);
  const [geographyQuery, setGeographyQuery] = useState("");
  const geographySelector = useRef<HTMLDetailsElement>(null);
  const geographyLabelId = useId();
  const geographySummaryId = useId();
  const options = useQuery({
    queryKey: ["investigation-options"],
    queryFn: ({ signal }) => getInvestigation<{ countries: Array<{ id: string; name?: string; label?: string }> }>("/options", EMPTY_CONTEXT, 0, signal),
    staleTime: 5 * 60_000,
  });
  const countries = options.data?.data.countries ?? [];
  const selectedCountries = splitIds(draft.countries);
  const unlistedCountries = selectedCountries.filter(id => !countries.some(country => country.id === id));
  const selectedLabels = selectedCountries.map(id => {
    const country = countries.find(item => item.id === id);
    return country?.name ?? country?.label ?? "Unavailable geography";
  });
  const geographySummary = options.isPending ? "Loading geographies…" : !selectedLabels.length ? "All geographies"
    : selectedLabels.length <= 3 ? selectedLabels.join(" · ") : `${selectedLabels.slice(0, 3).join(" · ")} +${selectedLabels.length - 3}`;
  const visibleCountries = countries.filter(country => (country.name ?? country.label ?? "").toLowerCase().includes(geographyQuery.trim().toLowerCase()));
  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (geographySelector.current?.open && event.target instanceof Node && !geographySelector.current.contains(event.target))
        geographySelector.current.open = false;
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);
  useEffect(() => setDraft(previous => ({ ...previous, berry: context.berry, countries: context.countries,
    geo_basis: context.geo_basis, actor_roles: context.actor_roles, relationship_types: context.relationship_types,
    news_from: context.news_from, news_to: context.news_to })),
  [context.berry, context.countries, context.geo_basis, context.actor_roles, context.relationship_types, context.news_from, context.news_to]);
  const apply = (event: FormEvent) => {
    event.preventDefault();
    if (geographySelector.current) geographySelector.current.open = false;
    dispatch({ type: "applyScope", scope: draft, origin: "direct" });
  };
  const set = (field: keyof InvestigationContext, value: string) => setDraft(previous => ({ ...previous, [field]: value }));
  const toggleGeography = (id: string) => setDraft(previous => {
    const selected = splitIds(previous.countries);
    return { ...previous, countries: (selected.includes(id) ? selected.filter(item => item !== id) : [...selected, id]).join(",") };
  });
  return <form className="berry-scopebar" data-region="investigation-scope" onSubmit={apply} aria-label="Investigation scope">
    <label className="berry-scope-field">Berry<select value={draft.berry} onChange={event => set("berry", event.target.value as Berry)}>{["all", "berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"].map(berry => <option key={berry} value={berry}>{berry === "all" ? "All berries" : berry.slice(6, 7).toUpperCase() + berry.slice(7)}</option>)}</select></label>
    <div className="berry-country-field"><span id={geographyLabelId} className="berry-field-label">Geography</span>
      <details className="berry-country-selector" ref={geographySelector} onKeyDown={event => {
        if (event.key === "Escape" && event.currentTarget.open) {
          event.preventDefault(); event.stopPropagation(); event.currentTarget.open = false;
          event.currentTarget.querySelector("summary")?.focus();
        }
      }}>
        <summary className="berry-button berry-button--secondary" aria-labelledby={`${geographyLabelId} ${geographySummaryId}`} title={selectedLabels.length ? selectedLabels.join(" · ") : "All geographies"}><span id={geographySummaryId}>{geographySummary}</span></summary>
        <div className="berry-country-options">
          <label>Find a geography<input type="search" value={geographyQuery} onChange={event => setGeographyQuery(event.target.value)} onKeyDown={event => { if (event.key === "Enter") event.preventDefault(); }} placeholder="Country or region" /></label>
          <button type="button" className="berry-button berry-button--ghost berry-button--small" aria-pressed={!selectedCountries.length} onClick={() => set("countries", "")}>All geographies</button>
          {options.isError && <p role="status">Geography choices could not be loaded. <button type="button" onClick={() => void options.refetch()}>Try again</button></p>}
          <fieldset><legend>Countries and regions</legend>
            {visibleCountries.map(country => <label key={country.id}><input type="checkbox" checked={selectedCountries.includes(country.id)} onChange={() => toggleGeography(country.id)} /><span>{country.name ?? country.label ?? "Geography"}</span></label>)}
            {unlistedCountries.map((id, index) => <label key={id}><input type="checkbox" checked onChange={() => toggleGeography(id)} /><span>Unavailable selected geography {index + 1}</span></label>)}
            {!options.isPending && !options.isError && !visibleCountries.length && <p>No geography choices match.</p>}
          </fieldset>
          <p>Choose geographies, then Apply scope.</p>
        </div>
      </details>
    </div>
    <button type="submit" className="berry-button berry-button--primary">Apply scope</button>
    <details className="berry-scope-advanced"><summary>Scope options</summary>
      <p>Country and region selections retain their recorded geographic meaning.</p>
      <label>Geographic basis<select value={draft.geo_basis} onChange={event => set("geo_basis", event.target.value)}><option value="company_connections">Recorded company connections</option><option value="source_geography">Source geography</option></select></label>
      <label>Published from<input type="date" value={draft.news_from} onChange={event => set("news_from", event.target.value)} /></label>
      <label>Published through<input type="date" value={draft.news_to} onChange={event => set("news_to", event.target.value)} /></label>
      <p>Publication dates apply to developments. Standing portfolios retain their recorded context.</p>
    </details>
  </form>;
}
