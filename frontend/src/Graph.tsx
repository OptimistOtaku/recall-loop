import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import ForceGraph3D from '3d-force-graph';
import * as THREE from 'three';
import type {GraphData,Node,Link} from './types';
import {endpointId} from './types';

export const colors:Record<string,string>={memory:'#efa85d',session:'#a2b5d5',artifact:'#93bbac',outcome:'#d2c1e1'};
const safeLabel=(s:string)=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#39;");
export type GraphHandle={reset:()=>void;focus:(id:string)=>void;pin:(id:string,pinned:boolean)=>void;positions:()=>any[];benchmark:()=>Promise<{fps:number;nodes:number;links:number;durationMs:number}>};
type Props={data:GraphData;selected:string|null;highlight:string[];onNode:(node:Node)=>void;onLink:(link:Link)=>void;onPositions:(positions:any[])=>void;resetKey:number};

const Graph=forwardRef<GraphHandle,Props>(function Graph({data,selected,highlight,onNode,onLink,onPositions,resetKey},ref){
  const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const host=useRef<HTMLDivElement>(null),graph=useRef<any>(null),nodes=useRef(new Map<string,Node>());
  const objects=useRef(new Map<string,THREE.Object3D>());
  const nodeFactory=useRef<((n:Node)=>THREE.Object3D)|null>(null);
  const dispose=(object:THREE.Object3D)=>object.traverse((child:any)=>{child.geometry?.dispose();const materials=Array.isArray(child.material)?child.material:[child.material];for(const m of materials){m?.map?.dispose();m?.dispose();}});
  const callbacks=useRef({onNode,onLink,onPositions});callbacks.current={onNode,onLink,onPositions};
  const selectedRef=useRef(selected),highlightRef=useRef(highlight);selectedRef.current=selected;highlightRef.current=highlight;
  const [unsupported,setUnsupported]=useState(false);
  useImperativeHandle(ref,()=>({
    reset(){graph.current?.zoomToFit(reduceMotion?0:650,65);},
    focus(id){const n=nodes.current.get(id);if(n&&graph.current)graph.current.cameraPosition({x:(n.x||0)+30,y:(n.y||0)+40,z:(n.z||0)+140},{x:n.x||0,y:n.y||0,z:n.z||0},reduceMotion?0:600);},
    pin(id,pinned){const n=nodes.current.get(id);if(n){n.fx=pinned?n.x:undefined;n.fy=pinned?n.y:undefined;n.fz=pinned?n.z:undefined;graph.current?.d3ReheatSimulation();}},
    positions(){return [...nodes.current.values()].map(n=>({id:n.id,x:n.x||0,y:n.y||0,z:n.z||0,pinned:n.fx!==undefined}));},
    benchmark(){return new Promise((resolve,reject)=>{const g=graph.current;if(!g){reject(new Error('WebGL graph unavailable'));return;}
      const start=performance.now(),frame=g.renderer().info.render.frame;
      const sample=()=>{const elapsed=performance.now()-start;if(elapsed<5000){requestAnimationFrame(sample);return;}
        resolve({fps:Math.round((g.renderer().info.render.frame-frame)*1000/elapsed),nodes:nodes.current.size,links:g.graphData().links.length,durationMs:Math.round(elapsed)});};requestAnimationFrame(sample);
    });}
  }));
  useEffect(()=>{
    if(!host.current)return;
    let g:any;
    try {
      const canvas=document.createElement('canvas');
      if(!canvas.getContext('webgl2')){setUnsupported(true);return;}
      const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
      g=new ForceGraph3D(host.current,{controlType:'orbit',rendererConfig:{antialias:true,alpha:true}});graph.current=g;
      g.backgroundColor('#151b1c').showNavInfo(false).nodeId('id')
       .nodeLabel((n:Node)=>safeLabel(n.label+' · '+n.type+(n.kind?' / '+n.kind.replaceAll('_',' '):'')))
       .nodeThreeObject(nodeFactory.current=(n:Node)=>{
          const old=objects.current.get(n.id);if(old)dispose(old);
          const lit=n.id===selectedRef.current||highlightRef.current.includes(n.id);
          const size=n.type==='memory'?3.2:n.type==='session'?5:2.7;
          const geometry=n.type==='session'?new THREE.IcosahedronGeometry(size,0):
            n.type==='artifact'?new THREE.BoxGeometry(size*1.4,size*1.4,size*1.4):
            n.type==='outcome'?new THREE.OctahedronGeometry(size,0):new THREE.SphereGeometry(size,12,8);
          const group=new THREE.Group();
          group.add(new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:colors[n.type],roughness:.5,
            metalness:.15,emissive:lit?colors[n.type]:'#000000',emissiveIntensity:lit?.5:0,
            transparent:true,opacity:n.status==='superseded'?.3:1})));
          if(lit){
            group.add(new THREE.Mesh(new THREE.TorusGeometry(size+2,.22,6,48),new THREE.MeshBasicMaterial({color:colors[n.type],transparent:true,opacity:.6})));
            const label=document.createElement('canvas');label.width=640;label.height=90;
            const c=label.getContext('2d')!;c.font='500 24px sans-serif';c.fillStyle='#f3eee3';
            c.fillText(n.label.length>43?n.label.slice(0,42)+'…':n.label,8,45);
            const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(label),depthWrite:false,transparent:true}));
            sprite.scale.set(75,10.5,1);sprite.position.set(37,10,0);group.add(sprite);
          }
          objects.current.set(n.id,group);return group;
       })
       .nodeThreeObjectExtend(false)
       .linkColor((l:Link)=>l.kind==='contradicts'?'#dc8d84':l.kind==='prerequisite_for'?'#aebfa3':'#536367')
       .linkOpacity(.42).linkWidth((l:Link)=>l.kind==='prerequisite_for'?.7:.35)
       .linkDirectionalArrowLength((l:Link)=>['prerequisite_for','supersedes'].includes(l.kind)?2.2:0)
       .linkDirectionalArrowRelPos(.8)
       .linkThreeObject((l:Link)=>{
          if(l.origin!=='suggestion')return null;
          const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),
            new THREE.LineDashedMaterial({color:'#6c7173',dashSize:2,gapSize:3,transparent:true,opacity:.55}));
          return line;
       })
       .linkPositionUpdate((object:THREE.Line,points:any,l:Link)=>{
          if(l.origin!=='suggestion')return false;
          object.geometry.setFromPoints([new THREE.Vector3(points.start.x,points.start.y,points.start.z),new THREE.Vector3(points.end.x,points.end.y,points.end.z)]);
          object.computeLineDistances();return true;
       })
       .onNodeClick((n:Node)=>callbacks.current.onNode(n)).onLinkClick((l:Link)=>callbacks.current.onLink(l))
       .onNodeDragEnd((n:Node)=>{n.fx=n.x;n.fy=n.y;n.fz=n.z;callbacks.current.onPositions([{id:n.id,x:n.x||0,y:n.y||0,z:n.z||0,pinned:true}]);})
       .cooldownTicks(reduced?1:100).d3AlphaDecay(.035).d3VelocityDecay(.35);
      g.d3Force('charge')?.strength(-85);g.d3Force('link')?.distance((l:Link)=>l.kind==='derived_from'?42:58);
      let firstFit=false;
      g.onEngineStop(()=>{
        if(!nodes.current.size)return;
        if(!firstFit){g.zoomToFit(reduced?0:600,75);firstFit=true;}
        callbacks.current.onPositions([...nodes.current.values()].map(n=>({id:n.id,x:n.x||0,y:n.y||0,z:n.z||0,pinned:n.fx!==undefined})));
      });
      g.scene().add(new THREE.AmbientLight('#e2e8dc',2));
      const grid=new THREE.GridHelper(1600,55,'#273335','#222c2e');grid.position.y=-145;grid.material.transparent=true;grid.material.opacity=.4;g.scene().add(grid);
      g.cameraPosition({x:30,y:100,z:340});
      const resize=new ResizeObserver(entries=>{const r=entries[0].contentRect;g.width(r.width).height(r.height);});resize.observe(host.current);
      const visibility=()=>document.hidden?g.pauseAnimation():g.resumeAnimation();document.addEventListener('visibilitychange',visibility);
      return()=>{resize.disconnect();document.removeEventListener('visibilitychange',visibility);g._destructor();objects.current.forEach(dispose);objects.current.clear();graph.current=null;};
    }catch{setUnsupported(true);if(g)g._destructor();}
  },[]);
  useEffect(()=>{
    if(!graph.current)return;
    const wanted=new Set(data.nodes.map(n=>n.id));for(const id of nodes.current.keys())if(!wanted.has(id)){nodes.current.delete(id);const o=objects.current.get(id);if(o)dispose(o);objects.current.delete(id);}
    for(const n of data.nodes){
      const previous=nodes.current.get(n.id);
      if(previous)Object.assign(previous,n);
      else {const next={...n};if(n.position){Object.assign(next,{x:n.position.x,y:n.position.y,z:n.position.z});
        if(n.position.pinned)Object.assign(next,{fx:n.position.x,fy:n.position.y,fz:n.position.z});}nodes.current.set(n.id,next);}
    }
    graph.current.graphData({nodes:[...nodes.current.values()],links:data.links.map(l=>({...l,source:endpointId(l.source),target:endpointId(l.target)}))});
  },[data]);
  useEffect(()=>{if(graph.current)graph.current.nodeThreeObject((n:Node)=>nodeFactory.current!(n));},[selected,highlight]);
  useEffect(()=>{if(!graph.current||!resetKey)return;for(const n of nodes.current.values()){n.fx=undefined;n.fy=undefined;n.fz=undefined;}
    graph.current.d3ReheatSimulation();graph.current.zoomToFit(reduceMotion?0:650,65);},[resetKey]);
  useEffect(()=>{graph.current?.cooldownTicks(reduceMotion?1:100);},[reduceMotion]);
  return <div className="graph-host" ref={host}>{unsupported&&<div className="fallback"><h2>Your connected knowledge</h2><p>WebGL is unavailable. Memories and relationships remain usable in this list.</p>{data.nodes.map(n=><button key={n.id} onClick={()=>onNode(n)}>{n.label}<small>{n.type}</small></button>)}</div>}</div>;
});
export default Graph;
