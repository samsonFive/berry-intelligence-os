export type RosterPageSize = 25 | 50 | 100 | 'all';
export function rosterResultSummary(matched: number, searched: number, companySet: number, complete: boolean, companySearch = false): string {
  const matches = matched === 1 ? 'match' : 'matches';
  const result = !complete ? `${matched} ${matches} on this page`
    : matched !== searched ? `${matched} ${matches} of ${searched} companies`
      : companySearch ? `${searched} search ${matches}` : `${searched} companies`;
  return searched !== companySet ? `${result} · ${companySet} in company set` : result;
}
/** Only actual companies count; tier decorations never consume display rows. */
export function rosterDisplayPage<T>(rows: readonly T[], size: RosterPageSize, index: number) {
  const limit = size === 'all' ? Math.max(1, rows.length) : size;
  const count = Math.max(1, Math.ceil(rows.length / limit));
  const page = Math.min(Math.max(0, Math.floor(index)), count - 1), start = page * limit;
  return { rows: rows.slice(start, start + limit), index: page, count, start, end: Math.min(start + limit, rows.length), total: rows.length };
}
