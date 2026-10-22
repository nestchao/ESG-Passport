export const DEFAULT_PERIOD: '2026-09';
export function isValidPeriod(value: unknown): value is string;
/** Throws RangeError for invalid periods. Dates use inclusive YYYY-MM-DD bounds. */
export function monthBounds(period: string): {start: string; end: string};
/** English month and four-digit year, independent of the browser timezone. */
export function monthLabel(period: string): string;
export function previousMonth(period: string): string | null;
export function selectedPeriod(search: string | URLSearchParams): string;
/** Returns a leading-question-mark query string without mutating history or input. */
export function periodSearch(search: string | URLSearchParams, period: string): string;
export function periodPath(path: string, period: string, extra?: Record<string,string | number | boolean | null | undefined>): string;
export type RecordDraft = {name?: string; period?: string; activities?: Record<string,any>[]};
export function recordDraftKey(draft: RecordDraft): string;
export function validateRecordMetadata(draft: {name?: string; period?: string}): Record<string,string>;
/** Returns the original array for stale/equal versions; otherwise a new array. */
export function applyRecordUpdate<T extends {id: string | number; version?: number}>(records: T[], updated: T): T[];
export function defaultDeclaration(code: string): Record<string,any>;
