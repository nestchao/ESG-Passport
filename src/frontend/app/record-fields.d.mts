export function categoryLabel(code:string):string;
export function allowedCategories(documentType:string):string[];
export function allowedUnits(category:string):string[];
export function cleanDecimal(value:unknown):string;
export function normaliseActivities<T extends Record<string,any>>(rows:T[]):(T & {quantity:string})[];
export function activityKey(rows:Record<string,any>[]):string;
export function validateActivities(rows:Record<string,any>[],documentType:string,period:string):Record<string,string>;

export function reclassifyActivities(rows:Record<string,any>[],type:string):Record<string,any>[];

export function unclassifiedWasteTransferRows(document:Record<string,any>):Record<string,any>[];
