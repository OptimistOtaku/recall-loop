"""Prepare a 500-node synthetic rendering workspace while the service is stopped."""
import argparse
from pathlib import Path
from recall_loop.service import MemoryService
from recall_loop.store import uid, now


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    args = p.parse_args()
    s = MemoryService(Path(args.data), embeddings=False)
    project = s.create_project("Performance lab · synthetic", project="performance-lab", sample=True)
    if s.store.nodes(project):
        print("Fixture already exists.")
        s.close()
        return
    with s.store.transaction() as db:
        sessions = [s.store.put_node(db, project, "session", f"Sample session {i+1}", props={"sample":True}) for i in range(40)]
        files = [s.store.put_node(db, project, "artifact", f"module-{i+1}.ts", props={"sample":True}) for i in range(180)]
        outcomes = [s.store.put_node(db, project, "outcome", f"Illustrative result {i+1}", props={"sample":True}) for i in range(80)]
        memories = []
        for i in range(200):
            text = f"Synthetic rendering fixture lesson {i+1}: validate module {i%180+1} before updating its dependent workflow."
            event = uid()
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)",(event,project,sessions[i%40],"user",text,now(),"Synthetic rendering fixture"))
            mid = s.store.put_node(db, project, "memory", f"Lesson {i+1}: module {i%180+1}", text,
                ["decision","correction","procedure","failed_approach","question"][i%5],
                {"sample":True,"evidence":[{"event_id":event,"quote":text}],"classification":"sample_user_stated"})
            memories.append(mid)
            s.store.put_edge(db, project, mid, sessions[i%40], "derived_from")
            s.store.put_edge(db, project, mid, files[i%180], "references")
            s.store.put_edge(db, project, mid, outcomes[i%80], "observed_outcome")
        for i,m in enumerate(memories):
            for delta in (1,7):
                s.store.put_edge(db, project, m, memories[(i+delta)%200], "related_to", "user")
    s.sync()
    print(f"Created {len(s.graph(project,500)['nodes'])} nodes.")
    s.close()


if __name__ == "__main__":
    main()
