import os
import json
from datetime import datetime
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()  # loads .env into environment

client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

def call_llm(prompt: str) -> str:
    resp = client.responses.create(model=MODEL, input=prompt)
    return resp.output_text

def format_ideas_block(df: pd.DataFrame) -> str:
    # Compact but legible: include idea_name + ring_feature + short what_user_does
    lines = []
    for _, r in df.iterrows():
        lines.append(
            f"- {r['idea_name']} | ring_feature: {r['ring_feature']} | user: {r['what_user_does']}"
        )
    return "\n".join(lines)

def parse_json_loose(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first JSON object substring
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                return None
        return None

def prompt_cluster_v1(ideas_block: str) -> str:
    return f"""You are doing affinity diagramming on 25 design concepts for an investing-confidence project.

Goal emotion: SAFE + REASSURING.
Analogy: Ring Doorbell (monitoring, alerts, event history, zones, shared access, two-way talk, privacy).

TASK:
Cluster the 25 ideas into 5–8 affinity clusters.
Each cluster must be defined by a distinct "safety mechanism" (e.g., passive reassurance, guardrails, sensemaking, social reassurance, privacy, escalation).

OUTPUT FORMAT (JSON only):
{{
  "clusters": [
    {{
      "cluster_name": "...",
      "cluster_definition": "...(1 sentence)...",
      "safety_mechanism": "...(short)...",
      "idea_names": ["Idea 1", "Idea 2"]
    }}
  ],
  "notes": ["1–3 brief observations about the set"]
}}

RULES:
- Every idea_name must appear exactly once across all clusters.
- Cluster names must be short and non-overlapping.
- Keep it grounded: do not invent new ideas—only cluster what's provided.

IDEAS:
{ideas_block}
"""

def prompt_improve(prev_json: str, ideas_block: str) -> str:
    return f"""You previously created an affinity clustering for these ideas. Now act as a critique-and-improve facilitator.

INPUTS:
1) The original ideas (below)
2) Your previous clustering output (below)

YOUR JOB:
1) Critique the previous clustering for:
   - overlapping clusters
   - clusters that are too broad or too narrow
   - clusters that do not align with the target emotion (safe + reassuring)
   - whether the cluster lens is the best one for design insight
2) Propose a NEW clustering lens (choose one):
   - By timing (prevent / detect / respond / recover)
   - By user agency (passive / guided / social / expert)
   - By uncertainty type (knowledge / outcome / identity-shame / privacy / manipulation)
   - By interaction mode (alerts / dashboards / journaling / social / expert escalation)
3) Re-cluster the ideas using that new lens into 5–8 clusters.

OUTPUT FORMAT (JSON only):
{{
  "chosen_lens": "...",
  "clusters": [
    {{
      "cluster_name": "...",
      "cluster_definition": "...",
      "idea_names": ["..."]
    }}
  ],
  "what_improved": ["3 bullets describing improvements vs prior clustering"]
}}

RULES:
- Every idea must appear exactly once.
- Do not invent ideas.

IDEAS:
{ideas_block}

PREVIOUS CLUSTERING:
{prev_json}
"""

def main():
    df = pd.read_csv("ai_concept_dev_self_refine_20260118_141545/ideas_final.csv")
    ideas_block = format_ideas_block(df)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = f"affinity_cluster_iterations_{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    # Iteration 1
    p1 = prompt_cluster_v1(ideas_block)
    o1 = call_llm(p1)
    j1 = parse_json_loose(o1)

    with open(os.path.join(out_dir, "prompt_1.txt"), "w", encoding="utf-8") as f: f.write(p1)
    with open(os.path.join(out_dir, "output_1_raw.txt"), "w", encoding="utf-8") as f: f.write(o1)
    if j1:
        with open(os.path.join(out_dir, "output_1.json"), "w", encoding="utf-8") as f: json.dump(j1, f, indent=2)

    prev_json_text = json.dumps(j1, indent=2) if j1 else o1

    # Iteration 2
    p2 = prompt_improve(prev_json_text, ideas_block)
    o2 = call_llm(p2)
    j2 = parse_json_loose(o2)

    with open(os.path.join(out_dir, "prompt_2.txt"), "w", encoding="utf-8") as f: f.write(p2)
    with open(os.path.join(out_dir, "output_2_raw.txt"), "w", encoding="utf-8") as f: f.write(o2)
    if j2:
        with open(os.path.join(out_dir, "output_2.json"), "w", encoding="utf-8") as f: json.dump(j2, f, indent=2)

    prev_json_text = json.dumps(j2, indent=2) if j2 else o2

    # Iteration 3
    p3 = prompt_improve(prev_json_text, ideas_block)
    o3 = call_llm(p3)
    j3 = parse_json_loose(o3)

    with open(os.path.join(out_dir, "prompt_3.txt"), "w", encoding="utf-8") as f: f.write(p3)
    with open(os.path.join(out_dir, "output_3_raw.txt"), "w", encoding="utf-8") as f: f.write(o3)
    if j3:
        with open(os.path.join(out_dir, "output_3.json"), "w", encoding="utf-8") as f: json.dump(j3, f, indent=2)

    print(f"Done. Saved clustering iterations to: {out_dir}")
    if not j3:
        print("Note: Iteration 3 JSON parse failed—use output_3_raw.txt as artifact or tighten JSON-only instruction.")

if __name__ == "__main__":
    main()
