export function replaceDeclaration(current,saved){
 const index=current.findIndex(item=>item.code===saved.code&&item.period===saved.period);
 if(index<0)return [...current,saved];
 if(Number(current[index].version)>Number(saved.version))return current;
 return current.map((item,i)=>i===index?saved:item);
}
