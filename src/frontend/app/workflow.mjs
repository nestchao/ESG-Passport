export function reviewSummary(questions = [], dirtyIds = []) {
  const dirty = new Set(dirtyIds);
  const reviewed = questions.filter(q => q.reviewed && !dirty.has(q.id)).length;
  return {
    total: questions.length,
    reviewed,
    estimated: questions.filter(q => q.badge === 'estimated' || q.metrics?.some(m => m.badge === 'estimated')).length,
    missing: questions.filter(q => q.badge === 'missing' || (!q.codes?.length && !q.manual_answer)).length,
    canContinue: questions.length > 0 && reviewed === questions.length,
  };
}
