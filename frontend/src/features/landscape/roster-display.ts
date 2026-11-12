export type RosterPageSize = 25 | 50 | 100 | 'all';
/** Only actual companies count; tier decorations never consume display rows. */
export function rosterDisplayPage<T>(rows: readonly T[], size: RosterPageSize, index: number) {
  const limit = size === 'all' ? Math.max(1, rows.length) : size;
  const count = Math.max(1, Math.ceil(rows.length / limit));
  const page = Math.min(Math.max(0, Math.floor(index)), count - 1), start = page * limit;
  return { rows: rows.slice(start, start + limit), index: page, count, start, end: Math.min(start + limit, rows.length), total: rows.length };
}
