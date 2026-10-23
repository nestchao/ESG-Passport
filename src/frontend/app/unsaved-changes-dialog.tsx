import {useEffect,useRef} from 'react';

export function UnsavedChangesDialog({onKeep,onDiscard}:{onKeep:()=>void;onDiscard:()=>void}){
  const ref=useRef<HTMLElement>(null);
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement;
    const buttons=Array.from(ref.current?.querySelectorAll<HTMLButtonElement>('button')||[]);
    buttons[0]?.focus();
    const key=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onKeep();}
      if(event.key==='Tab'){
        const first=buttons[0],last=buttons[buttons.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    };
    document.addEventListener('keydown',key,true);
    return()=>{document.removeEventListener('keydown',key,true);if(previous?.isConnected)previous.focus();};
  },[onKeep,onDiscard]);
  return <div className="draft-confirm-backdrop"><section ref={ref} className="draft-confirm panel" role="alertdialog" aria-modal="true" aria-labelledby="unsaved-title" aria-describedby="unsaved-description">
    <h2 id="unsaved-title">You have unsaved changes</h2>
    <p id="unsaved-description">Keep editing to save your work, or discard these changes and continue. Nothing will be saved or shared automatically.</p>
    <div className="draft-confirm-actions"><button className="button primary" onClick={onKeep}>Keep editing</button><button className="button secondary" onClick={onDiscard}>Discard changes</button></div>
  </section></div>;
}
