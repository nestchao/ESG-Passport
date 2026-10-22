export type WorkspaceSection = 'profile'|'documents'|'questionnaires'|'declarations'|'shares';
export type WorkspaceSectionState = {status:'loading'|'ready'|'error';value?:any;error?:string};
export function createWorkspaceLoader(): {
  invalidate():void;
  accept(key:WorkspaceSection):void;
  load(options:{role:string;request:(key:WorkspaceSection)=>Promise<any>;onState:(key:WorkspaceSection,state:WorkspaceSectionState)=>void}):Promise<boolean>;
};
