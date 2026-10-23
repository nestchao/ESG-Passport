'use client';
import {useEffect,useId,useRef,useState} from 'react';
import {Check,ChevronDown,ClipboardCheck,Eye,ShieldCheck} from 'lucide-react';

type Role='owner'|'clerk'|'customer';
const ROLES=[
 {value:'owner' as Role,label:'Owner',description:'Manage data, approve and share packs',Icon:ShieldCheck},
 {value:'clerk' as Role,label:'Admin clerk',description:'Prepare records and customer answers',Icon:ClipboardCheck},
 {value:'customer' as Role,label:'Customer',description:'View an approved supplier pack',Icon:Eye},
];

export function RoleSwitcher({value,onChange,disabled=false}:{value:Role;onChange:(role:Role)=>void;disabled?:boolean}) {
 const [open,setOpen]=useState(false);
 const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),items=useRef<(HTMLButtonElement|null)[]>([]);
 const menuId=useId(),selected=ROLES.findIndex(role=>role.value===value),pendingFocus=useRef(0);
 const current=ROLES[selected]||ROLES[0],Icon=current.Icon;
 useEffect(()=>{
  if(!open)return;
  items.current[pendingFocus.current]?.focus();
  const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
  document.addEventListener('pointerdown',outside);
  return ()=>document.removeEventListener('pointerdown',outside);
 },[open]);
 useEffect(()=>{if(disabled)setOpen(false);},[disabled]);
 const close=(restoreFocus=false)=>{setOpen(false);if(restoreFocus)trigger.current?.focus();};
 const show=(index:number)=>{if(disabled)return;pendingFocus.current=index;setOpen(true);};
 const choose=(next:Role)=>{close(true);if(next!==value)onChange(next);};
 return <div className="workspace-role-switcher" ref={root} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))close();}}>
  <button ref={trigger} type="button" className={`workspace-role-trigger${open?' is-open':''}`} disabled={disabled}
   aria-label={`Workspace role: ${current.label}`} aria-haspopup="menu" aria-expanded={open} aria-controls={open?menuId:undefined}
   onClick={()=>open?close():show(Math.max(selected,0))}
   onKeyDown={event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();show(event.key==='ArrowDown'?0:ROLES.length-1);}else if(event.key==='Escape'){event.preventDefault();close(true);}}}>
   <span className="workspace-role-avatar" aria-hidden="true"><Icon size={17}/></span>
   <span className="workspace-role-current"><small>Workspace role</small><strong>{current.label}</strong></span>
   <ChevronDown className="workspace-role-chevron" size={15} aria-hidden="true"/>
  </button>
  {open&&<div id={menuId} className="workspace-role-menu" role="menu" aria-label="Switch workspace role" onKeyDown={event=>{
   const index=items.current.indexOf(document.activeElement as HTMLButtonElement);
   if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close(true);}
   else if(event.key==='Tab')close();
   else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
    event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?ROLES.length-1:(index+(event.key==='ArrowDown'?1:-1)+ROLES.length)%ROLES.length;
    items.current[next]?.focus();
   }
  }}>
   <div className="workspace-role-menu-heading" role="presentation">Switch workspace role</div>
   {ROLES.map(({value:next,label,description,Icon:RoleIcon},index)=><button key={next} ref={element=>{items.current[index]=element;}} type="button"
    className={`workspace-role-option${next===value?' is-selected':''}`} role="menuitemradio" aria-checked={next===value} tabIndex={-1} onClick={()=>choose(next)}>
    <span className="workspace-role-option-icon" aria-hidden="true"><RoleIcon size={18}/></span>
    <span className="workspace-role-option-copy"><strong>{label}</strong><small>{description}</small></span>
    {next===value&&<Check size={17} className="workspace-role-check" aria-hidden="true"/>}
   </button>)}
  </div>}
 </div>;
}
