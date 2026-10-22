type Data=Record<string,any>;
export function approvalKey(recipient:string,ids:string[]):string;
export function declarationKey(answer:Data,ids:string[]):string;
export function questionDraftChanged(question:Data,draft:{codes:string[];manual:string}):boolean;
export function createDraftNavigator(options:{isDirty:()=>boolean;onDiscard:()=>void}):{
  request(action:()=>void,options?:{dirty?:boolean;discard?:()=>void}):boolean;
  keepEditing():void;discardAndContinue():void;
};
export function warnBeforeUnload(event:BeforeUnloadEvent):void;
