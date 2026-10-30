import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import ForceGraph3D from '3d-force-graph';
import * as THREE from 'three';
import {Search, X, List, Pause, Play, Eye, Orbit, LocateFixed, ZoomIn, ZoomOut, ChevronRight} from 'lucide-react';
import type {GraphData,Node,Link} from './types';
import {endpointId} from './types';
import {reconcileNode,sessionGroups} from './graphModel';

export const colors:Record<string,string>={memory:'#f6c77b',session:'#92a9ff',artifact:'#64dacb',outcome:'#e2a6ea'};
const relations:Record<string,string>={prerequisite_for:'#7fe2cf',related_to:'#9caeff',contradicts:'#ff8f9e',supersedes:'#f6c77b',derived_from:'#647da5',references:'#537c8c',observed_outcome:'#ac81bb'};
const pretty=(s:string)=>s.replaceAll('_',' ');
const escape=(s:string)=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const hash=(s:string)=>{let n=2166136261;for(const c of s)n=Math.imul(n^c.charCodeAt(0),16777619);return (n>>>0)/4294967296;};
function dispose(object:THREE.Object3D){object.traverse((child:any)=>{child.geometry?.dispose();for(const m of Array.isArray(child.material)?child.material:[child.material]){if(m?.map?.userData.owned)m.map.dispose();m?.dispose();}});}
function glowTexture(){const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d')!;const g=x.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'rgba(255,255,255,1)');g.addColorStop(.12,'rgba(255,255,255,.7)');g.addColorStop(.35,'rgba(255,255,255,.15)');g.addColorStop(1,'rgba(255,255,255,0)');x.fillStyle=g;x.fillRect(0,0,128,128);return new THREE.CanvasTexture(c);}
function textSprite(text:string,color='#e6edff',size=52){
 const c=document.createElement('canvas'),measure=c.getContext('2d')!;
 const value=text.length>48?text.slice(0,47)+'…':text;
 measure.font='500 24px "DM Sans Variable",sans-serif';c.width=Math.ceil(measure.measureText(value).width)+24;c.height=54;
 const x=c.getContext('2d')!;x.font='500 24px "DM Sans Variable",sans-serif';x.shadowBlur=8;x.shadowColor='#020612';x.fillStyle=color;x.fillText(value,12,35);
 const texture=new THREE.CanvasTexture(c);texture.userData.owned=true;
 const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthTest:false,depthWrite:false,sizeAttenuation:false}));
 const height=.048*Math.max(.85,size/52);sprite.scale.set(height*c.width/54,height,1);sprite.center.set(0,.5);sprite.renderOrder=10;return sprite;
}

export type GraphHandle={reset:()=>void;focus:(id:string)=>void;pin:(id:string,pinned:boolean)=>void;positions:()=>any[];benchmark:()=>Promise<{fps:number;nodes:number;links:number;durationMs:number}>};
type Props={visible:boolean;data:GraphData;selected:string|null;highlight:string[];onNode:(node:Node)=>void;onLink:(link:Link)=>void;onPositions:(positions:any[])=>void;resetKey:number};
const Graph=forwardRef<GraphHandle,Props>(function Graph({visible,data,selected,highlight,onNode,onLink,onPositions,resetKey},ref){
 const host=useRef<HTMLDivElement>(null),graph=useRef<any>(null),nodes=useRef(new Map<string,Node>()),meshes=useRef(new Map<string,THREE.Object3D>()),factory=useRef<any>(null);
 const linkObjects=useRef(new Map<string,THREE.Object3D>()),groups=useRef(new Map<string,string>()),anchors=useRef(new Map<string,THREE.Vector3>());
 const [unsupported,setUnsupported]=useState(false),[navigator,setNavigator]=useState(false),[nodeQuery,setNodeQuery]=useState(''),[nodeType,setNodeType]=useState('');
 const [labels,setLabels]=useState('auto'),[evidence,setEvidence]=useState(true),[suggestions,setSuggestions]=useState(false),[paused,setPaused]=useState(false),[flat,setFlat]=useState(false),[hover,setHover]=useState<string|null>(null);
 const [reduced,setReduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);
 const live=useRef({selected,highlight,labels,evidence,suggestions,paused,flat,reduced,hover,visible});live.current={selected,highlight,labels,evidence,suggestions,paused,flat,reduced,hover,visible};
 const callbacks=useRef({onNode,onLink,onPositions});callbacks.current={onNode,onLink,onPositions};
 const positions=()=>[...nodes.current.values()].map(n=>({id:n.id,x:n.x||0,y:n.y||0,z:n.z||0,pinned:n.fx!==undefined}));
 function focusNode(id:string){const n=nodes.current.get(id),g=graph.current;if(!n||!g)return;const p={x:n.x||0,y:n.y||0,z:n.z||0};const direction=new THREE.Vector3().subVectors(g.camera().position,new THREE.Vector3(p.x,p.y,p.z)).normalize();if(!direction.length())direction.set(0,.2,1);direction.multiplyScalar(210);g.cameraPosition({x:p.x+direction.x,y:p.y+direction.y,z:p.z+direction.z},p,live.current.reduced?0:650);}
 function zoom(factor:number){const g=graph.current;if(!g)return;const target=g.controls().target.clone(),offset=g.camera().position.clone().sub(target).multiplyScalar(factor);g.cameraPosition(target.clone().add(offset),target,live.current.reduced?0:260);}
 useImperativeHandle(ref,()=>({
  reset(){graph.current?.zoomToFit(live.current.reduced?0:650,55);},focus:focusNode,
  pin(id,pinned){const n=nodes.current.get(id);if(n){n.fx=pinned?n.x:undefined;n.fy=pinned?n.y:undefined;n.fz=pinned?n.z:undefined;graph.current?.d3ReheatSimulation();}},positions,
  benchmark(){return new Promise((resolve,reject)=>{const g=graph.current;if(!g){reject(new Error('WebGL unavailable'));return;}const start=performance.now(),frame=g.renderer().info.render.frame;function sample(){const duration=performance.now()-start;if(duration<5000){requestAnimationFrame(sample);return;}resolve({fps:Math.round((g.renderer().info.render.frame-frame)*1000/duration),nodes:nodes.current.size,links:g.graphData().links.length,durationMs:Math.round(duration)});}requestAnimationFrame(sample);});}
 }));
 useEffect(()=>{const media=matchMedia('(prefers-reduced-motion: reduce)'),change=()=>setReduced(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 useEffect(()=>{
  if(!host.current)return;let g:any;const decor=new THREE.Group(),glow=glowTexture();
  try{
   const canvas=document.createElement('canvas');if(!canvas.getContext('webgl2')){setUnsupported(true);glow.dispose();return;}
   g=new ForceGraph3D(host.current,{controlType:'orbit',rendererConfig:{antialias:true,alpha:true}});graph.current=g;
   g.backgroundColor('#050a16').showNavInfo(false).nodeId('id').nodeRelSize(4).linkHoverPrecision(3)
    .nodeLabel((n:Node)=>`<b>${escape(n.label)}</b><br>${escape(pretty(n.kind||n.type))} · Click to inspect · Double-click to focus`)
    .linkLabel((l:Link)=>`${escape(pretty(l.kind))} · ${escape(l.origin)} connection`)
    .nodeThreeObject(factory.current=(n:Node)=>{
      const state=live.current,active=n.id===state.selected||n.id===state.hover,near=state.highlight.includes(n.id),dim=!!state.selected&&!active&&!near;
      const key=[active,near,dim,state.labels,n.label,n.status,n.type,nodes.current.size<=200,state.highlight.indexOf(n.id)<10].join('|');
      const old=meshes.current.get(n.id);if(old?.userData.visualKey===key)return old;if(old)dispose(old);
      const size=n.type==='session'?4.4:n.type==='memory'?2.7:2.1,color=colors[n.type];
      const geometry=n.type==='session'?new THREE.IcosahedronGeometry(size,1):n.type==='artifact'?new THREE.OctahedronGeometry(size,0):n.type==='outcome'?new THREE.OctahedronGeometry(size,0):new THREE.SphereGeometry(size,12,8);
      const group=new THREE.Group();group.userData.visualKey=key;group.add(new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color,transparent:true,opacity:dim?.24:n.status==='superseded'?.35:1})));
      const halo=new THREE.Sprite(new THREE.SpriteMaterial({map:glow,color,transparent:true,opacity:dim?.1:active?.8:.35,blending:THREE.AdditiveBlending,depthWrite:false}));halo.scale.setScalar(size*(active?11:7));group.add(halo);
      if(n.type==='session'||active){const ring=new THREE.Mesh(new THREE.TorusGeometry(size+(active?2.4:1.7),.1,5,60),new THREE.MeshBasicMaterial({color,transparent:true,opacity:active?.8:.4}));ring.rotation.x=.5;group.add(ring);}
      const show=state.labels==='all'||state.labels==='auto'&&(active||n.type==='session'&&nodes.current.size<=200||near&&state.highlight.indexOf(n.id)<10);
      if(show&&state.labels!=='none'){const name=textSprite(n.label,dim?'#6b7894':active?'#ffffff':'#b9c8e8',active?62:52);name.position.set(size+3,size+5,0);group.add(name);}
      meshes.current.set(n.id,group);return group;
    }).nodeThreeObjectExtend(false)
    .linkVisibility((l:Link)=>l.origin==='suggestion'?live.current.suggestions:live.current.evidence||l.origin==='user')
    .linkColor((l:Link)=>{const state=live.current;const adjacent=[endpointId(l.source),endpointId(l.target)].includes(state.selected||'');return state.selected&&!adjacent?'#17243b':relations[l.kind]||'#45597b';})
    .linkWidth((l:Link)=>{const adjacent=[endpointId(l.source),endpointId(l.target)].includes(live.current.selected||'');return adjacent?.9:l.origin==='user'?.55:.13;}).linkOpacity(.65)
    .linkDirectionalArrowLength((l:Link)=>['prerequisite_for','supersedes'].includes(l.kind)?2.5:0).linkDirectionalArrowRelPos(.72)
    .linkThreeObjectExtend(true).linkThreeObject((l:Link)=>{
      const adjacent=[endpointId(l.source),endpointId(l.target)].includes(live.current.selected||'');
      const key=l.origin==='suggestion'?'suggestion':adjacent&&l.origin==='user'&&live.current.labels!=='none'?l.kind:'';
      const old=linkObjects.current.get(l.id);if(old?.userData.visualKey===key)return old;if(old){dispose(old);linkObjects.current.delete(l.id);}
      if(l.origin==='suggestion'){const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),new THREE.LineDashedMaterial({color:'#6c7fba',dashSize:2,gapSize:3,transparent:true,opacity:.5}));line.userData.visualKey=key;linkObjects.current.set(l.id,line);return line;}
      if(key){const sprite=textSprite(pretty(l.kind),relations[l.kind],42);sprite.center.set(.5,.5);sprite.userData.visualKey=key;linkObjects.current.set(l.id,sprite);return sprite;}return null;
    }).linkPositionUpdate((object:THREE.Object3D,p:any,l:Link)=>{if(l.origin==='suggestion'){const line=object as THREE.Line;line.geometry.setFromPoints([new THREE.Vector3(p.start.x,p.start.y,p.start.z),new THREE.Vector3(p.end.x,p.end.y,p.end.z)]);line.computeLineDistances();return true;}return false;})
    .onNodeClick((n:Node)=>callbacks.current.onNode(n)).onNodeRightClick((n:Node)=>focusNode(n.id))
    .onNodeHover((n:Node|null)=>{setHover(n?.id||null);if(host.current)host.current.style.cursor=n?'pointer':'grab';})
    .onLinkClick((l:Link)=>callbacks.current.onLink(l))
    .onNodeDragEnd((n:Node)=>{n.fx=n.x;n.fy=n.y;n.fz=n.z;callbacks.current.onPositions([{id:n.id,x:n.x||0,y:n.y||0,z:n.z||0,pinned:true}]);})
    .cooldownTicks(100).d3AlphaDecay(.035).d3VelocityDecay(.42);
   g.d3Force('charge')?.strength(-105);g.d3Force('link')?.distance((l:Link)=>l.kind==='derived_from'?48:70);
   g.d3Force('constellation',(alpha:number)=>{if(live.current.paused)return;for(const n of nodes.current.values()){const anchor=anchors.current.get(groups.current.get(n.id)||'');if(!anchor)continue;const p=n as any;const strength=n.type==='session'?.09:.015;if(n.fx===undefined)p.vx=(p.vx||0)+(anchor.x-(n.x||0))*alpha*strength;if(n.fy===undefined)p.vy=(p.vy||0)+(anchor.y-(n.y||0))*alpha*strength;if(n.fz===undefined&&!live.current.flat)p.vz=(p.vz||0)+(anchor.z-(n.z||0))*alpha*strength;}});
   let firstFit=false;g.onEngineStop(()=>{if(!nodes.current.size)return;if(!firstFit){g.zoomToFit(live.current.reduced?0:700,60);firstFit=true;}callbacks.current.onPositions(positions());});
   // Decorative sky is spatial context only. Stars are not knowledge nodes.
   const skyPositions:number[]=[],skyColors:number[]=[];
   for(let i=0;i<1700;i++){const u=hash('sky-u'+i),v=hash('sky-v'+i),r=800+hash('sky-r'+i)*900;const theta=u*Math.PI*2,phi=Math.acos(2*v-1);skyPositions.push(r*Math.sin(phi)*Math.cos(theta),r*Math.cos(phi),r*Math.sin(phi)*Math.sin(theta));const c=new THREE.Color(i%5===0?'#b4baff':i%7===0?'#f5d29f':'#8196bc');skyColors.push(c.r,c.g,c.b);}
   const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(skyPositions,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(skyColors,3));decor.add(new THREE.Points(geometry,new THREE.PointsMaterial({size:1.5,transparent:true,opacity:.7,vertexColors:true,sizeAttenuation:true,depthWrite:false})));
   const spiralPositions:number[]=[],spiralColors:number[]=[];
   for(let i=0;i<1800;i++){const t=hash('arm-r'+i),r=45+Math.sqrt(t)*600,angle=t*8+i%3*Math.PI*2/3+(hash('arm-w'+i)-.5)*.34;spiralPositions.push(Math.cos(angle)*r,Math.sin(angle)*r*.57,(hash('arm-z'+i)-.5)*30-420);const c=new THREE.Color(i%6===0?'#bb8fce':i%4===0?'#93bbdf':'#426593');spiralColors.push(c.r,c.g,c.b);}
   const spiralGeometry=new THREE.BufferGeometry();spiralGeometry.setAttribute('position',new THREE.Float32BufferAttribute(spiralPositions,3));spiralGeometry.setAttribute('color',new THREE.Float32BufferAttribute(spiralColors,3));decor.add(new THREE.Points(spiralGeometry,new THREE.PointsMaterial({size:1.8,transparent:true,opacity:.45,vertexColors:true,depthWrite:false})));
   for(let i=0;i<5;i++){const haze=new THREE.Sprite(new THREE.SpriteMaterial({map:glow,color:['#1e487e','#494583','#193f71','#5c345c','#204e64'][i],transparent:true,opacity:.14,blending:THREE.AdditiveBlending,depthWrite:false}));haze.position.set((i-2)*240,-90+i*35,-450-i*60);haze.scale.set(900,500,1);decor.add(haze);}
   for(const radius of [180,300,430]){const orbit=new THREE.Mesh(new THREE.RingGeometry(radius,radius+.25,128),new THREE.MeshBasicMaterial({color:'#5274a6',transparent:true,opacity:.1,side:THREE.DoubleSide,depthWrite:false}));orbit.rotation.x=-Math.PI*.43;orbit.position.y=-60;decor.add(orbit);}
   g.scene().add(decor);g.renderer().setPixelRatio(Math.min(devicePixelRatio,1.7));g.cameraPosition({x:0,y:170,z:490});g.controls().enableDamping=true;g.controls().dampingFactor=.12;g.controls().minDistance=20;g.controls().maxDistance=1800;
   const resize=new ResizeObserver(entries=>{const r=entries[0].contentRect;g.width(r.width).height(r.height);});resize.observe(host.current);
   const visibility=()=>document.hidden||!live.current.visible?g.pauseAnimation():g.resumeAnimation();document.addEventListener('visibilitychange',visibility);
   let clickTime=0;const doubleClick=(event:MouseEvent)=>{if(event.target instanceof HTMLCanvasElement&&live.current.hover){const time=performance.now();if(time-clickTime<330)focusNode(live.current.hover);clickTime=time;}};host.current.addEventListener('click',doubleClick);
   return()=>{resize.disconnect();document.removeEventListener('visibilitychange',visibility);host.current?.removeEventListener('click',doubleClick);g._destructor();meshes.current.forEach(dispose);meshes.current.clear();linkObjects.current.forEach(dispose);linkObjects.current.clear();dispose(decor);glow.dispose();graph.current=null;};
  }catch(error){console.error('Graph initialization failed',error);setUnsupported(true);g?._destructor();dispose(decor);glow.dispose();}
 },[]);
 useEffect(()=>{
  const g=graph.current;if(!g)return;groups.current=sessionGroups(data.nodes,data.links);const sessions=data.nodes.filter(n=>n.type==='session');anchors.current.clear();sessions.forEach((n,i)=>{const angle=i*Math.PI*2/Math.max(1,sessions.length)+.4,r=sessions.length===1?0:140;anchors.current.set(n.id,new THREE.Vector3(Math.cos(angle)*r,Math.sin(angle)*r*.5,Math.sin(angle*2)*45));});
  const wanted=new Set(data.nodes.map(n=>n.id));for(const id of nodes.current.keys())if(!wanted.has(id)){nodes.current.delete(id);const o=meshes.current.get(id);if(o)dispose(o);meshes.current.delete(id);}
  for(const n of data.nodes){const previous=nodes.current.get(n.id),next=reconcileNode(previous,n);if(!previous&&!n.position){const anchor=anchors.current.get(groups.current.get(n.id)||'')||new THREE.Vector3();const angle=hash(n.id)*Math.PI*2,r=n.type==='session'?0:25+hash(n.id+'r')*65;next.x=anchor.x+Math.cos(angle)*r;next.y=anchor.y+Math.sin(angle)*r;next.z=live.current.flat?0:anchor.z+(hash(n.id+'z')-.5)*75;}nodes.current.set(n.id,next);}
  const linkIds=new Set(data.links.map(l=>l.id));for(const [id,object] of linkObjects.current)if(!linkIds.has(id)){dispose(object);linkObjects.current.delete(id);}
  g.graphData({nodes:[...nodes.current.values()],links:data.links.map(l=>({...l,source:endpointId(l.source),target:endpointId(l.target)}))});if(live.current.paused)g.cooldownTicks(0);
 },[data]);
 useEffect(()=>{const g=graph.current;if(!g)return;g.nodeThreeObject((n:Node)=>factory.current(n));g.linkColor(g.linkColor()).linkWidth(g.linkWidth()).linkThreeObject(g.linkThreeObject());},[selected,highlight,labels,hover]);
 useEffect(()=>{if(graph.current){if(visible&&!document.hidden)graph.current.resumeAnimation();else graph.current.pauseAnimation();}},[visible]);
 useEffect(()=>{graph.current?.linkVisibility(graph.current.linkVisibility());},[evidence,suggestions]);
 useEffect(()=>{const g=graph.current;if(!g)return;g.numDimensions(flat?2:3);g.controls().enableRotate=!flat;g.cooldownTicks(paused?0:reduced?2:100);if(flat)g.cameraPosition({x:0,y:0,z:480},{x:0,y:0,z:0},reduced?0:650);if(!paused)g.d3ReheatSimulation();},[flat,paused,reduced]);
 useEffect(()=>{const g=graph.current;if(!g||!resetKey)return;for(const n of nodes.current.values()){n.fx=undefined;n.fy=undefined;n.fz=undefined;}setPaused(false);g.cooldownTicks(reduced?2:100);g.d3ReheatSimulation();},[resetKey]);
 const matches=data.nodes.filter(n=>(!nodeType||n.type===nodeType)&&(!nodeQuery||`${n.label} ${n.body} ${n.kind}`.toLowerCase().includes(nodeQuery.toLowerCase()))).sort((a,b)=>a.label.localeCompare(b.label));
 function navigate(n:Node){callbacks.current.onNode(n);focusNode(n.id);}
 return <>
  <div className="graph-host" ref={host} role="img" aria-label={`Interactive knowledge constellation: ${data.nodes.length} nodes. Use Browse nodes for keyboard navigation.`}/>
  <div className="sky-toolbar" aria-label="Graph display controls">
   <button className={navigator?'active':''} aria-expanded={navigator} onClick={()=>setNavigator(!navigator)}><List size={14}/>Browse nodes</button>
   <span className="sky-toolbar-divider"/>
   <label><Eye size={13}/><select aria-label="Graph labels" value={labels} onChange={e=>setLabels(e.target.value)}><option value="auto">Smart labels</option><option value="all">All labels</option><option value="none">No labels</option></select></label>
   <button aria-pressed={flat} className={flat?'active':''} onClick={()=>setFlat(!flat)}><Orbit size={14}/>{flat?'2D map':'3D space'}</button>
   <button aria-pressed={paused} onClick={()=>setPaused(!paused)} aria-label={paused?'Resume layout':'Freeze layout'}>{paused?<Play size={13}/>:<Pause size={13}/>}</button>
  </div>
  <div className="sky-layer-controls"><label><input type="checkbox" checked={evidence} onChange={e=>setEvidence(e.target.checked)}/>Evidence links</label><label><input type="checkbox" checked={suggestions} onChange={e=>setSuggestions(e.target.checked)}/>Suggestions</label></div>
  {(navigator||unsupported)&&<div className="node-navigator"><header><span>NODE DIRECTORY <b>{matches.length}</b></span>{!unsupported&&<button aria-label="Close node directory" onClick={()=>setNavigator(false)}><X size={14}/></button>}</header><label className="node-find"><Search size={14}/><input aria-label="Find a graph node" placeholder="Find a lesson, file, session…" value={nodeQuery} onChange={e=>setNodeQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&matches[0]){e.preventDefault();navigate(matches[0]);}}}/></label><select aria-label="Node type" value={nodeType} onChange={e=>setNodeType(e.target.value)}><option value="">All node types</option>{Object.keys(colors).map(k=><option key={k} value={k}>{pretty(k)}</option>)}</select><div className="node-directory-list">{matches.map(n=><button key={n.id} aria-label={`Navigate to ${n.label}`} aria-pressed={selected===n.id} onClick={()=>navigate(n)}><i style={{background:colors[n.type]}}/><span>{n.label}<small>{pretty(n.kind||n.type)}{n.position?.pinned?' · pinned':''}</small></span><ChevronRight size={12}/></button>)}{!matches.length&&<p>No nodes match this filter.</p>}</div><footer>{unsupported?'WebGL unavailable. All records remain accessible here.':'Select to inspect and fly to a node. Tab + Enter supported.'}</footer></div>}
  <div className="sky-zoom"><button aria-label="Zoom in" onClick={()=>zoom(.75)}><ZoomIn size={15}/></button><button aria-label="Zoom out" onClick={()=>zoom(1.35)}><ZoomOut size={15}/></button><button aria-label="Focus selected node" disabled={!selected} onClick={()=>selected&&focusNode(selected)}><LocateFixed size={15}/></button></div>
  <div className="sky-coordinate"><i/>{flat?'PLANAR VIEW':'CONSTELLATION VIEW'}<span>Decorative stars · knowledge nodes glow</span></div>
 </>;
});
export default Graph;
