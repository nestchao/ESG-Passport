export function policyRows(value) {
  return (Array.isArray(value?.policies) ? value.policies : []).map(policy => ({
    name: policy.name,
    label: policy.status === 'in place' ? 'In place' : policy.status === 'not in place' ? 'Not in place' : 'Unknown',
    tone: policy.status === 'in place' ? 'complete' : policy.status === 'not in place' ? 'neutral' : 'attention',
  }));
}

export function declarationText(code, value) {
  if (value == null || value === '') return 'No owner declaration recorded.';
  if (code === 'G3.1') return String(value);
  if (typeof value !== 'object') return Number(value).toLocaleString('en-MY');
  const labels = {count:'Incidents',injuries:'Injuries',fatalities:'Fatalities'};
  return Object.entries(value).map(([key, item]) => key === 'description' ? String(item) : `${labels[key] || key}: ${item}`).join(' · ');
}

export function recentRequests(requests) {
  const time = value => Date.parse(value || '') || 0;
  return [...requests].sort((a,b) =>
    (time(b.updated_at) || time(b.created_at)) - (time(a.updated_at) || time(a.created_at)) ||
    time(b.created_at) - time(a.created_at) || String(b.id).localeCompare(String(a.id))
  ).slice(0,3);
}

export function customerPortalMessage(pack) {
  return pack ? 'Your owner-approved answers and selected evidence.' : 'Open the share link provided by the supplier.';
}
