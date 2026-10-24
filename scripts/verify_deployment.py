import json
from pathlib import Path
import httpx
url='https://recall-loop-demo.onrender.com'
with httpx.Client(base_url=url,timeout=60) as a, httpx.Client(base_url=url,timeout=60) as b:
    health=a.get('/health').raise_for_status().json()
    p=a.get('/api/projects').raise_for_status().json()[0]['id']
    p2=b.get('/api/projects').raise_for_status().json()[0]['id']
    assert p != p2
    assert b.get('/api/graph',params={'project':p}).status_code == 404
    graph=a.get('/api/graph',params={'project':p}).raise_for_status().json()
    result=a.post('/api/memories/search',json={'project':p,'query':'sign in callback session persistence redirect'}).raise_for_status().json()
    assert result['results'] and any('session' in r['label'].lower() for r in result['results'])
    memories=[n for n in graph['nodes'] if n['type']=='memory']
    pairs={(e['source'],e['target']) for e in graph['links']}
    s,t=next((s,t) for s in memories for t in memories if s['id']!=t['id'] and (s['id'],t['id']) not in pairs)
    edge=a.post('/api/relationships',json={'project':p,'source':s['id'],'target':t['id'],'kind':'prerequisite_for'}).raise_for_status().json()['id']
    updated=a.get('/api/graph',params={'project':p}).raise_for_status().json()
    assert any(e['id']==edge for e in updated['links'])
    a.post('/api/undo',json={'project':p}).raise_for_status()
    restored=a.get('/api/graph',params={'project':p}).raise_for_status().json()
    assert not any(e['id']==edge for e in restored['links'])
    assert a.post('/api/extract',json={'project':p,'session':'test'}).status_code==403
    report={'url':url,'health':health,'graph_nodes':len(graph['nodes']),'hybrid_search':'passed','relationship_create_and_undo':'passed','visitor_isolation':'passed','paid_extraction_disabled':'passed','deploy_id':'dep-dbeh90oae00c73d56q20','source_commit':'25c14149596f4a9fd7d6af50eda91afa31967b02'}
    Path('evaluation/deployment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
