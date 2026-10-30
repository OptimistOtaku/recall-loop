import type {Node, Link} from './types';
const endpointId=(value:string|Node)=>typeof value==='string'?value:value.id;

// Preserve simulation identity and camera continuity when SSE refreshes metadata.
export function reconcileNode(previous: Node | undefined, incoming: Node): Node {
  const next = previous ? Object.assign(previous,incoming) : {...incoming};
  if (incoming.position) {
    const {x,y,z,pinned} = incoming.position;
    if (!previous || pinned) Object.assign(next,{x,y,z});
    Object.assign(next,{fx:pinned?x:undefined,fy:pinned?y:undefined,fz:pinned?z:undefined});
  } else if(previous) {
    next.fx=undefined; next.fy=undefined; next.fz=undefined;
  }
  return next;
}

export function sessionGroups(nodes: Node[], links: Link[]): Map<string,string> {
  const groups = new Map(nodes.filter(n=>n.type==='session').map(n=>[n.id,n.id]));
  for (const l of links) if(l.kind==='derived_from') groups.set(endpointId(l.source),endpointId(l.target));
  for (const l of links) {
    const s=endpointId(l.source),t=endpointId(l.target);
    if(groups.has(s)&&!groups.has(t)) groups.set(t,groups.get(s)!);
  }
  return groups;
}
