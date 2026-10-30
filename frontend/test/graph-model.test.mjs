import test from 'node:test';
import assert from 'node:assert/strict';
import {reconcileNode} from '../src/graphModel.ts';

const memory={id:'lesson',type:'memory',label:'A real coding lesson',props:{},status:'active'};
test('a canonical unpin releases all three simulation constraints',()=>{
  const prior={...memory,x:12,y:24,z:36,fx:12,fy:24,fz:36,position:{x:12,y:24,z:36,pinned:true}};
  const next=reconcileNode(prior,{...memory,position:{x:12,y:24,z:36,pinned:false}});
  assert.equal(next.fx,undefined);
  assert.equal(next.fy,undefined);
  assert.equal(next.fz,undefined);
});
test('a metadata refresh preserves the live object and unpinned simulation position',()=>{
  const prior={...memory,x:80,y:90,z:100,position:{x:1,y:2,z:3,pinned:false}};
  const next=reconcileNode(prior,{...memory,label:'Corrected',position:{x:1,y:2,z:3,pinned:false}});
  assert.equal(next,prior);
  assert.deepEqual([next.x,next.y,next.z],[80,90,100]);
  assert.equal(next.label,'Corrected');
});
test('a canonical pin moves an existing node to the saved coordinates',()=>{
  const prior={...memory,x:1,y:2,z:3};
  const next=reconcileNode(prior,{...memory,position:{x:40,y:50,z:60,pinned:true}});
  assert.deepEqual([next.fx,next.fy,next.fz],[40,50,60]);
});
