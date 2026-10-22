import { test } from 'node:test';
import assert from 'node:assert/strict';
import { reviewSummary } from './workflow.mjs';

test('empty requests cannot move to approval', () => {
  assert.equal(reviewSummary([], []).canContinue, false);
});
test('an edited mapping must be saved even if previously reviewed', () => {
  const result = reviewSummary([{ id: 'q1', reviewed: true, codes: ['E1.2'] }], ['q1']);
  assert.equal(result.reviewed, 0);
  assert.equal(result.canContinue, false);
});
test('explicitly reviewed unavailable answers may continue to owner', () => {
  const result = reviewSummary([{ id: 'q1', reviewed: true, codes: [], badge: 'missing' }], []);
  assert.equal(result.canContinue, true);
  assert.equal(result.missing, 1);
});
test('estimates count once per answer and remain visible', () => {
  const result = reviewSummary([{ id: 'q1', reviewed: true, codes: ['E1.1'], badge: 'estimated', metrics: [{ badge: 'estimated' }] }], []);
  assert.equal(result.estimated, 1);
  assert.equal(result.canContinue, true);
});
test('an owner manual declaration is not an unsupported gap', () => {
  assert.equal(reviewSummary([{ id: 'q1', reviewed: true, codes: [], manual_answer: 'Owner response', badge: 'declared' }], []).missing, 0);
});
