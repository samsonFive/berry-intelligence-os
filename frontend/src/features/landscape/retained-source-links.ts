import { safeHref } from './models.ts';
import type { RetainedSourceLink } from './models.ts';

export const RETAINED_LINK_LIMITATION = 'Similar reporting can share an origin. These links do not establish independent corroboration.';

function publicIpv4(parts: number[]): boolean {
  const [a, b, c] = parts;
  return !(a === 0 || a === 10 || a === 127 || a >= 224 || a === 169 && b === 254
    || a === 172 && b >= 16 && b <= 31 || a === 192 && b === 168
    || a === 100 && b >= 64 && b <= 127 || a === 198 && (b === 18 || b === 19)
    || a === 192 && b === 0 && (c === 0 || c === 2)
    || a === 198 && b === 51 && c === 100 || a === 203 && b === 0 && c === 113);
}

/** Validate only; the canonical server filters public URLs. Never resolve or rewrite a retained URL. */
function publicHttp(value: string): boolean {
  if (value.length > 4096 || /[\u0000-\u0020\\]/.test(value) || !/^https?:\/\//i.test(value) || !safeHref(value, '')) return false;
  const parsed = new URL(value);
  const host = parsed.hostname.toLowerCase().replace(/\.$/, '').replace(/^\[|\]$/g, '');
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.local') || host.endsWith('.internal')) return false;
  // URL parsing canonicalizes numeric IPv4 spellings before these checks.
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) return publicIpv4(host.split('.').map(Number));
  if (host.includes(':')) {
    if (host.startsWith('::ffff:')) {
      const words = host.slice(7).split(':').map(word => Number.parseInt(word, 16));
      return words.length === 2 && words.every(Number.isFinite)
        && publicIpv4([words[0] >> 8, words[0] & 255, words[1] >> 8, words[1] & 255]);
    }
    return !/^(?:0*:)*(?:0*|0*1)$/.test(host) && !/^(?:f[cd]|fe[89ab]|ff)/.test(host)
      && !/^(?:2001:db8:|2001:2:|100:)/.test(host);
  }
  return !!host;
}

/** Optional metadata only: retain server order and exact fields, without counting corroboration. */
export function retainedSourceLinks(value: unknown): RetainedSourceLink[] {
  if (!Array.isArray(value)) return [];
  const result: RetainedSourceLink[] = [];
  for (const raw of value.slice(0, 128)) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const { url, label, kind } = raw;
    if (typeof url !== 'string' || typeof label !== 'string' || !label.trim()
      || typeof kind !== 'string' || !kind.trim() || !publicHttp(url)) continue;
    result.push({ url, label, kind });
    if (result.length === 16) break;
  }
  return result;
}
