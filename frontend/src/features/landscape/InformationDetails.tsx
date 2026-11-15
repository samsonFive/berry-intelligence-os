import type { InformationFlags } from './models';

/** Source qualifications remain available without creating another inventory. */
export function InformationDetails({ information, reviewed = false, note }: { information?: InformationFlags; reviewed?: boolean; note?: string }) {
  const reviewLabel = (information?.review_status || (reviewed ? 'reviewed' : 'unreviewed')).replaceAll('_', ' ');
  return <details className="news-coverage information-details"><summary>Confidence &amp; source details</summary><dl>
    <dt>Review</dt><dd>{reviewLabel.charAt(0).toUpperCase() + reviewLabel.slice(1)}</dd>
    <dt>Confidence</dt><dd>{information?.confidence_label || 'Not assessed'}</dd>
    {information?.verification_status && <><dt>Verification</dt><dd>{information.verification_status.replaceAll('_', ' ')}</dd></>}
  </dl>{note && <p>{note}</p>}{!!information?.caveats?.length && <ul>{information.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}</ul>}</details>;
}
