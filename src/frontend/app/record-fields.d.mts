export function categoryLabel(code:string):string;
export function allowedCategories(documentType:string):string[];
export function allowedUnits(category:string):string[];
export function cleanDecimal(value:unknown):string;
export function normaliseActivities<T extends Record<string,any>>(rows:T[]):(T & {quantity:string})[];
export function activityKey(rows:Record<string,any>[]):string;
export function validateActivities(rows:Record<string,any>[],documentType:string,period:string):Record<string,string>;
