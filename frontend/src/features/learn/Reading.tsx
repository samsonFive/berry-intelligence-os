import { Fragment, useMemo } from 'react';
import type { LearningResource, LearningSection } from './models';
import { parseLessonMarkdown, safeSourceHref } from './markdown';
import type { Inline } from './markdown';
import './learn-reading.css';

function InlineText({ nodes }: { nodes: Inline[] }) {
  return <>{nodes.map((node, index) => {
    if ('children' in node) return node.kind === 'strong'
      ? <strong key={index}><InlineText nodes={node.children} /></strong> : <em key={index}><InlineText nodes={node.children} /></em>;
    if (node.kind === 'citation') return <sup key={index}><a href={node.url} title={node.title}
      aria-label={`Source: ${node.title}`} target="_blank" rel="noopener noreferrer">{node.text}</a></sup>;
    if (node.kind === 'link') return <a key={index} href={node.url} target="_blank" rel="noopener noreferrer">{node.text}</a>;
    if (node.kind === 'source_gap') return <span key={index} className="berry-learn-source-gap">{node.text}</span>;
    return <Fragment key={index}>{node.text}</Fragment>;
  })}</>;
}

/** Read-only: every body fragment is a React text node or an allowlisted element. */
export function LessonMarkdown({ text, citations, title = '' }: { text: string; citations: LearningResource[]; title?: string }) {
  const result = useMemo(() => {
    try { return { blocks: parseLessonMarkdown(text, citations, title), error: '' }; }
    catch (error) { return { blocks: [], error: error instanceof Error ? error.message : 'Open the retained Learn page to read this lesson.' }; }
  }, [text, citations, title]);
  if (result.error) return <p role="status">{result.error}</p>;
  return <div className="berry-learn-reading">{result.blocks.map((block, index) => {
    if (block.kind === 'heading') return block.level >= 4 ? <h4 key={index}><InlineText nodes={block.text} /></h4>
      : block.level === 3 ? <h3 key={index}><InlineText nodes={block.text} /></h3> : <h2 key={index}><InlineText nodes={block.text} /></h2>;
    if (block.kind === 'paragraph') return <p key={index}><InlineText nodes={block.text} /></p>;
    if (block.kind === 'list') return block.ordered
      ? <ol key={index}>{block.items.map((item, itemIndex) => <li value={block.numbers[itemIndex]} key={itemIndex}><InlineText nodes={item} /></li>)}</ol>
      : <ul key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}><InlineText nodes={item} /></li>)}</ul>;
    return <div className="berry-learn-table-wrap" key={index}><table aria-label="Lesson table"><thead><tr>
      {block.headers.map((cell, cellIndex) => <th key={cellIndex} scope="col"><InlineText nodes={cell} /></th>)}</tr></thead><tbody>
      {block.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}><InlineText nodes={cell} /></td>)}</tr>)}</tbody></table></div>;
  })}</div>;
}

export function ConceptSections({ sections }: { sections: LearningSection[] }) {
  return <div className="berry-learn-reading">{sections.map(section => <section key={section.id} id={`learn-${section.id}`}>
    <h2>{section.title}</h2><p>{section.text}</p>
  </section>)}</div>;
}

export function LearningCitations({ sources, id = 'learning-sources' }: { sources: LearningResource[]; id?: string }) {
  return <section className="berry-learn-citations" id={id}><h2>Sources / provenance</h2>
    <p>Educational source links are separate from reviewed competitive evidence.</p>
    {sources.length ? <ol>{sources.map((source, index) => {
      const href = safeSourceHref(source.url);
      return <li key={index}>{href ? <a href={href} target="_blank" rel="noopener noreferrer">{source.title || 'Captured source'}</a>
        : <span>{source.title || 'Source link unavailable'}</span>}{source.publisher && <small>{source.publisher}</small>}</li>;
    })}</ol> : <p>No source citations were captured. This educational draft needs source checking.</p>}
  </section>;
}
