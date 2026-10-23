export type BrowserOcrResult={category:string;quantity:string;unit:string;period_start:string;period_end:string;document_date:string;supplier:string;source_reference:string;notes:string[];rawText:string;verified:boolean};
export function parseBrowserBill(text:string,category:string,month:string):BrowserOcrResult;
