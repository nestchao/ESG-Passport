import {activityKey} from './record-fields.mjs';

export const DEFAULT_PERIOD = '2026-09';
const COLLECTIONS = new Set(['/profile','/documents','/declarations','/questionnaires','/shares']);
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

export function isValidPeriod(value) {
  return typeof value === 'string' && /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value);
}
function requirePeriod(period) {
  if (!isValidPeriod(period)) throw new RangeError('Choose a reporting month from 0001-01 to 9999-12.');
}
export function monthBounds(period) {
  requirePeriod(period);
  const year = Number(period.slice(0,4)), month = Number(period.slice(5));
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = month === 2 ? (leap ? 29 : 28) : [4,6,9,11].includes(month) ? 30 : 31;
  return {start:`${period}-01`,end:`${period}-${days}`};
}
export function monthLabel(period) {
  requirePeriod(period);
  return `${MONTHS[Number(period.slice(5))-1]} ${period.slice(0,4)}`;
}
export function previousMonth(period) {
  requirePeriod(period);
  if (period === '0001-01') return null;
  const year = Number(period.slice(0,4)), month = Number(period.slice(5));
  return month === 1 ? `${String(year-1).padStart(4,'0')}-12` : `${period.slice(0,4)}-${String(month-1).padStart(2,'0')}`;
}
export function selectedPeriod(search) {
  const period = new URLSearchParams(search).get('period');
  return isValidPeriod(period) ? period : DEFAULT_PERIOD;
}
// Pure query transformation: callers decide whether/when to update browser history.
export function periodSearch(search,period) {
  requirePeriod(period);
  const query = new URLSearchParams(search);
  query.set('period',period);
  return `?${query}`;
}
// Only monthly collection endpoints get an implicit period. Details and public shares
// retain their own scope; an explicit extra.period can be used when required.
export function periodPath(path,period,extra={}) {
  const hashAt = path.indexOf('#');
  const hash = hashAt < 0 ? '' : path.slice(hashAt);
  const base = hashAt < 0 ? path : path.slice(0,hashAt);
  const queryAt = base.indexOf('?');
  const pathname = queryAt < 0 ? base : base.slice(0,queryAt);
  const query = new URLSearchParams(queryAt < 0 ? '' : base.slice(queryAt+1));
  if (COLLECTIONS.has(pathname)) {requirePeriod(period);query.set('period',period);}
  for (const [key,value] of Object.entries(extra)) {
    if (value == null) query.delete(key); else query.set(key,String(value));
  }
  return `${pathname}${query.size ? `?${query}` : ''}${hash}`;
}
export function recordDraftKey({name,period,type,activities=[]}) {
  return JSON.stringify([name ?? '',period ?? '',type ?? '',activityKey(activities)]);
}
export function validateRecordMetadata({name,period}) {
  const errors = {};
  if (!String(name ?? '').trim()) errors.name = 'Enter a record name.';
  if (!isValidPeriod(period)) errors.period = 'Choose a valid reporting month.';
  return errors;
}
// Equal versions are also ignored: an older request must never overwrite saved data.
export function applyRecordUpdate(records,updated) {
  const index = records.findIndex(record=>String(record.id) === String(updated.id));
  if (index < 0) return [...records,updated];
  const existingVersion = Number(records[index].version ?? 0);
  const nextVersion = Number(updated.version ?? 0);
  if (!Number.isFinite(nextVersion) || nextVersion <= existingVersion) return records;
  return records.map((record,i)=>i === index ? updated : record);
}
export function defaultDeclaration(code) {
  switch (code) {
    case 'S4.1': return {injuries:'',fatalities:'',description:''};
    case 'G1.1': return {directors:''};
    case 'G2.1': return {policies:['Code of Conduct','Anti-Corruption Policy','Whistleblowing Policy','Health and Safety Policy'].map(name=>({name,status:'unknown'}))};
    case 'G3.1': return {year:''};
    default: return {count:'',description:''};
  }
}
