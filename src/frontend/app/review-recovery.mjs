const list = value => Array.isArray(value) ? value : [];
const unique = values => [...new Set(values.filter(value => typeof value === 'string' && value.length))];
export function needsReconfirmation(request) {
  return list(request?.questions).some(question => !question.reviewed && !!question.reviewed_at);
}
export function recommendedEvidence(request) {
  return unique(list(request?.questions).filter(question => question.reviewed).flatMap(question => list(question.evidence_ids)));
}
export function retainEvidenceSelection(selectedIds, documents) {
  const valid = new Set(list(documents).map(document => document.id));
  return unique(list(selectedIds)).filter(id => valid.has(id));
}
export function evidenceSelection(request, selectedIds, documents) {
  const recommendedIds = retainEvidenceSelection(recommendedEvidence(request), documents);
  const selected = new Set(retainEvidenceSelection(selectedIds, documents));
  return {recommendedIds, selectedRecommendedCount: recommendedIds.filter(id => selected.has(id)).length,
    excludedIds: recommendedIds.filter(id => !selected.has(id)), noAttachments: selected.size === 0};
}
function safePreview(value) {
  if (typeof value !== 'string' || !value.trim() || value.trim().startsWith('#')) return false;
  // Relative token routes and ordinary web links are supported; executable schemes are not.
  if (value !== value.trim() || /[\u0000-\u0020\u007f\\]/.test(value)) return false;
  try { const url = new URL(value, 'https://approved.invalid'); return ['https:', 'http:'].includes(url.protocol); }
  catch { return false; }
}
export function packQuestionEvidence(question, snapshot) {
  const referenced = new Set(unique([...list(question?.evidence_ids), ...list(question?.metrics).flatMap(metric => list(metric.evidence_ids))]));
  const selected = new Set(list(snapshot?.selected_evidence_ids ?? snapshot?.evidence_ids));
  const seen = new Set();
  return list(snapshot?.evidence).filter(document => {
    if (!referenced.has(document.id) || !selected.has(document.id) || seen.has(document.id) || !safePreview(document.preview_url)) return false;
    seen.add(document.id); return true;
  });
}
export function latestApprovedPack(shares, requestId) {
  return list(shares).filter(share => share.questionnaire_id === requestId)
    .reduce((latest, share) => !latest || (Date.parse(share.created_at) || 0) > (Date.parse(latest.created_at) || 0) ? share : latest, undefined);
}
export async function reloadRequestContext(api, requestId, role) {
  const [request, documents, shares] = await Promise.all([
    api(`/questionnaires/${encodeURIComponent(requestId)}`), api('/documents'),
    role === 'owner' ? api('/shares') : Promise.resolve([]),
  ]);
  return {request, documents:list(documents), shares:list(shares)};
}
export async function createAndMatchRequest(api, body, onCreated) {
  const request = await api('/questionnaires', {method:'POST', body:JSON.stringify(body)});
  await onCreated(request);
  try { return await api(`/questionnaires/${encodeURIComponent(request.id)}/map`, {method:'POST'}); }
  catch (error) { throw new Error(`Request saved. Matching could not finish: ${error instanceof Error ? error.message : String(error)}. Retry matching or select disclosures manually.`, {cause:error}); }
}
