import { investigationHref, isNativeSurfacePath } from '../contracts/investigation';
import type { InvestigationContext } from '../contracts/investigation';

/** Explicit expansion keeps a bounded native return without changing selectors. */
export function legacyHref(href: string, pathname: string, context: InvestigationContext): string {
  if (!href.startsWith('/') || href.startsWith('//') || href.includes('\\')) throw new Error('Use a local compatibility destination.');
  const url = new URL(href, window.location.origin);
  const surface = isNativeSurfacePath(pathname) ? pathname : '/app/landscape';
  url.searchParams.set('return_to', investigationHref(surface, context));
  return url.pathname + url.search;
}
