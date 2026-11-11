/** The legacy Learn reading grammar, projected as text nodes rather than HTML.
 * Links require captured citation membership. Image suggestions never load media.
 */
import type { LearningResource } from './models.ts';

export type Inline = { kind: 'text' | 'source_gap'; text: string }
  | { kind: 'strong' | 'em'; children: Inline[] }
  | { kind: 'link'; text: string; url: string }
  | { kind: 'citation'; text: string; url: string; title: string };
export type ReadingBlock = { kind: 'heading'; level: number; text: Inline[] }
  | { kind: 'paragraph'; text: Inline[] }
  | { kind: 'list'; ordered: boolean; items: Inline[][]; numbers: number[] }
  | { kind: 'table'; headers: Inline[][]; rows: Inline[][][] };
const MAX_TEXT = 2_000_000;
const MAX_BLOCKS = 4096;

export function safeSourceHref(value: unknown): string | undefined {
  if (typeof value !== 'string' || value.length > 3000 || /[\u0000-\u0020\\]/.test(value)) return undefined;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && !!url.hostname && !url.username && !url.password ? value : undefined;
  } catch { return undefined; }
}

export function inlineText(nodes: Inline[]): string {
  return nodes.map(node => 'children' in node ? inlineText(node.children) : node.text).join('');
}

export function parseInline(text: string, sources: LearningResource[] = [], depth = 0): Inline[] {
  if (depth >= 8) return [{ kind: 'text', text }];
  const allowed = new Set(sources.map(source => safeSourceHref(source.url)).filter(Boolean));
  const refs = new Map(sources.flatMap(source => (source.reference_ids ?? []).map(ref => [ref, source] as const)));
  const pattern = /\[web:\d+\]|!?\[([^\]\n]{1,500})\]\((https?:\/\/[^\s)]+)\)|\*\*([^*\n]+)\*\*|(?<!\*)\*([^*\n]+)\*(?!\*)/g;
  const nodes: Inline[] = [];
  let start = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index!;
    if (index > start) nodes.push({ kind: 'text', text: text.slice(start, index) });
    const raw = match[0];
    if (raw.startsWith('[web:')) {
      const source = refs.get(raw.slice(1, -1));
      const url = safeSourceHref(source?.url);
      nodes.push(url ? { kind: 'citation', text: raw.slice(5, -1), url, title: source?.title || 'Captured source' }
        : { kind: 'source_gap', text: 'Source link unavailable' });
    } else if (raw.startsWith('**')) nodes.push({ kind: 'strong', children: parseInline(match[3], sources, depth + 1) });
    else if (raw.startsWith('*')) nodes.push({ kind: 'em', children: parseInline(match[4], sources, depth + 1) });
    else {
      const url = safeSourceHref(match[2]);
      const label = inlineText(parseInline(match[1], sources, depth + 1));
      if (url && allowed.has(url)) nodes.push({ kind: 'link', text: label + (raw.startsWith('!') ? ' (image source)' : ''), url });
      else nodes.push({ kind: 'text', text: label + ' (link not verified)' });
    }
    start = index + raw.length;
  }
  if (start < text.length) nodes.push({ kind: 'text', text: text.slice(start) });
  return nodes;
}

export function parseLessonMarkdown(text: string, sources: LearningResource[] = [], title = ''): ReadingBlock[] {
  if (text.length > MAX_TEXT) throw new Error('This lesson exceeds the bounded reader. Open the retained Learn page.');
  const blocks: ReadingBlock[] = [];
  let paragraph: string[] = [], items: Inline[][] = [], numbers: number[] = [];
  const add = (block: ReadingBlock) => {
    if (blocks.length >= MAX_BLOCKS) throw new Error('This lesson has too many sections for the bounded reader. Open the retained Learn page.');
    blocks.push(block);
  };
  const flush = () => {
    if (paragraph.length) add({ kind: 'paragraph', text: parseInline(paragraph.join(' '), sources) });
    if (items.length) add({ kind: 'list', ordered: numbers.length > 0, items, numbers });
    paragraph = []; items = []; numbers = [];
  };
  const cells = (line: string) => {
    const values = line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|');
    if (values.length > 32) throw new Error('This table exceeds the bounded reader. Open the retained Learn page.');
    return values.map(value => parseInline(value.trim(), sources));
  };
  const lines = text.split(/\r?\n/);
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    if (line.trim().startsWith('|') && /^\s*\|[\s:|\-]+\|?\s*$/.test(lines[index + 1] ?? '')) {
      flush(); const headers = cells(line); const rows: Inline[][][] = []; index++;
      while (lines[index + 1]?.trim().startsWith('|')) rows.push(cells(lines[++index]));
      add({ kind: 'table', headers, rows }); continue;
    }
    const heading = /^(#{1,6})\s+(.+)/.exec(line);
    const bullet = /^\s*[-*]\s+(.+)/.exec(line);
    const ordered = /^\s*(\d{1,6})\.\s+(.+)/.exec(line);
    if (heading) { flush(); add({ kind: 'heading', level: heading[1].length, text: parseInline(heading[2], sources) }); }
    else if (bullet || ordered) {
      if (paragraph.length || (items.length && !!numbers.length !== !!ordered)) flush();
      items.push(parseInline(ordered ? ordered[2] : bullet![1], sources));
      if (ordered) numbers.push(Number(ordered[1]));
    } else if (!line.trim()) flush();
    else { if (items.length) flush(); paragraph.push(line); }
  }
  flush();
  const normalize = (value: string) => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase();
  if (title && blocks[0]?.kind === 'heading' && normalize(inlineText(blocks[0].text)) === normalize(title)) blocks.shift();
  return blocks;
}
