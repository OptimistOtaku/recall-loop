export type Node = {
  id: string; project: string; type: 'memory'|'session'|'artifact'|'outcome'; label: string;
  kind: string; body: string; status: string; created: string; props: Record<string, any>;
  position?: {x:number;y:number;z:number;pinned:boolean}; x?:number;y?:number;z?:number;
  fx?:number;fy?:number;fz?:number;
};
export type Link = {id:string;project:string;source:string|Node;target:string|Node;kind:string;origin:string;reason?:string};
export type GraphData = {nodes:Node[];links:Link[];version:number;total:number;undo_count:number};
export type SearchResult = {retrieval_id:string;results:(Node & {path?:{from:string;relationship:string};score:number})[];warnings:{message:string}[];mode:string};
export const endpointId = (x:string|Node) => typeof x === 'string' ? x : x.id;
export async function api<T=any>(path:string, options?:RequestInit):Promise<T> {
  const r=await fetch(path,{...options, headers:{'Content-Type':'application/json',...options?.headers}});
  if(!r.ok){const body=await r.json().catch(()=>({detail:r.statusText}));throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
  return r.json();
}
export const send=(method:string, body?:unknown):RequestInit=>({method,body:body===undefined?undefined:JSON.stringify(body)});
