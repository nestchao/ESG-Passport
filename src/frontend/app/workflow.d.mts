export function reviewSummary(questions?: Record<string, any>[], dirtyIds?: string[]): {
  total: number; reviewed: number; estimated: number; missing: number; canContinue: boolean;
};
