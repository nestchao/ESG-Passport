export type PublicDemoSample = {
 id:string;kind:'electricity'|'water'|'waste';title:string;file:string;image:string;month:string;
 date:string;period:string;quantity:string;unit:string;source:string;disclosure:string;metric:string;
 isEstimated:boolean;question:string;answer:string;caveat:string;
 suggestion:null|{category:string;label:string;basis:string;confidence:string};
};
export const PUBLIC_DEMO_SAMPLES:readonly PublicDemoSample[];
export const PUBLIC_DEMO_MONTHS:readonly string[];
export function demoSamplesForMonth(month:string):PublicDemoSample[];
