export function replaceRequest(requests, updated) {
  const existing = requests.find(request => request.id === updated.id);
  if (existing && existing.version > updated.version) return requests;
  return existing ? requests.map(request => request.id === updated.id ? updated : request) : [...requests, updated];
}

export async function saveQuestionReview(api, requestId, questionId, body) {
  await api(`/questions/${encodeURIComponent(questionId)}/review`, {method:'PUT',body:JSON.stringify(body)});
  return api(`/questionnaires/${encodeURIComponent(requestId)}`);
}

export async function loadApproval(api, requestId, token) {
  const [request, shares, pack] = await Promise.all([
    api(`/questionnaires/${encodeURIComponent(requestId)}`),
    api('/shares'),
    api(`/shares/${encodeURIComponent(token)}`),
  ]);
  return {request, shares, pack};
}
