import { ArrowRight, Check, ChevronRight, FileText, Plus, ShieldCheck } from 'lucide-react';

import { categoryLabel } from './record-fields.mjs';
import { recentRequests } from './presentation.mjs';

type Data = Record<string, any>;
type Props = {
  readiness: Data; breakdown: Data; documents: Data[]; requests: Data[]; gaps: Data[];
  periodLabel: string; titles: Record<string, string>; onUpload: () => void;
  onReview: (doc: Data) => void; onRecords: () => void;
  onRequest: (request: Data) => void; onAllRequests: () => void; onGap: (code: string) => void;
};

export function FlowSteps({ current, customer = false }: { current: number; customer?: boolean }) {
  const steps = customer ? ['Customer request', 'Review answers', 'Owner approval'] : ['Add records', 'Check data', 'Updated profile'];
  return <ol className="figma-flow" aria-label={customer ? 'Customer response progress' : 'Monthly preparation progress'}>
    {steps.map((label, i) => <li key={label} aria-current={i === current ? 'step' : undefined} className={i === current ? 'current' : i < current ? 'done' : ''}>
      <span>{i < current ? <Check size={12} /> : i + 1}</span>{label}
    </li>)}
  </ol>;
}

export function DesktopOverview(p: Props) {
  const pending = p.documents.filter(d => !d.confirmed);
  const next = pending[0];
  return <div className="figma-overview">
    <FlowSteps current={!p.documents.length ? 0 : pending.length ? 1 : 2} />
    <section className="snapshot-stats" aria-label="Monthly data summary">
      <div><span>Data readiness</span><strong>{p.readiness.complete}<small>/{p.readiness.total || 11}</small></strong><p>{p.readiness.complete} of 11 disclosures complete</p></div>
      <div><span>Bills to review</span><strong>{pending.length}</strong><p>{next?.type ? `${categoryLabel(next.type)} · ${p.periodLabel}` : 'All uploaded records reviewed'}</p></div>
      <div><span>Estimated disclosures</span><strong>{p.breakdown.estimated || 0}</strong><p>Visible, but not counted complete</p></div>
    </section>
    <div className="snapshot-body">
      <section className="panel monthly-readiness">
        <h2>Monthly readiness</h2><p className="section-description">Only reviewed, supported information counts toward readiness.</p>
        <div className="readiness-line"><span>Reviewed disclosures</span><span className="status-tag complete">{p.readiness.complete} complete</span></div>
        {next && <button className="readiness-line" onClick={() => p.onReview(next)}><span>{categoryLabel(next.type)} record / pending records</span><span className="status-tag attention">{pending.length} pending review <ChevronRight size={13}/></span></button>}
        {p.gaps.map(g => <button className="readiness-line" key={g.code} onClick={() => p.onGap(g.code)}><span>{p.titles[g.code] || g.title}</span><span className={`status-tag ${g.badge === 'estimated' ? 'attention' : 'neutral'}`}>{g.badge === 'estimated' ? 'Estimated' : g.partial ? 'Partial' : 'Needs information'}<ChevronRight size={13}/></span></button>)}
        <div className="readiness-legend">{Object.entries(p.breakdown).map(([status, count]) => <span key={status}><b>{String(count)}</b> {status}</span>)}</div>
        <p className="field-note">This measures data coverage, not ESG performance. Estimates and partial information stay outside the complete count.</p>
      </section>
      <div className="snapshot-actions">
        <section className="panel next-task"><h2>One check moves you forward</h2><span className="status-tag attention">{!p.documents.length ? 'Add your first records' : next ? 'Needs your review' : 'Monthly records reviewed'}</span><p>{!p.documents.length ? 'Upload monthly bills to start preparing your evidence-backed profile.' : next ? 'Compare the original bill with the recorded quantities. Confirm only what the evidence supports.' : 'Your records are ready to reuse. Review remaining gaps or open a customer questionnaire.'}</p><button className="button primary full" onClick={() => !p.documents.length ? p.onUpload() : next ? p.onReview(next) : p.onRecords()}>{!p.documents.length ? 'Add records' : next ? 'Review next bill' : 'Open records'}<ArrowRight size={16}/></button>{next && <span className="next-file"><FileText size={14}/>{next.name}</span>}</section>
        <section className="request-shortcuts"><div className="flex-between"><h2>Customer requests</h2><button className="text-button" onClick={p.onAllRequests}>View all<ArrowRight size={14}/></button></div>{!p.requests.length&&<p>No customer requests yet.</p>}{recentRequests(p.requests).map(r => <button key={r.id} onClick={() => p.onRequest(r)}><div><strong>{r.customer}</strong><small>{r.period} · {r.status?.replaceAll('_', ' ') || 'Draft'}</small></div><ArrowRight size={16}/></button>)}<p>Answers stay private until the owner approves sharing.</p></section>
      </div>
    </div>
    <div className="snapshot-footer"><p>{p.periodLabel} only · Partial-year coverage</p><button className="button primary" onClick={p.onUpload}><Plus size={16}/>Add records</button></div>
  </div>;
}
