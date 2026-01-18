import os
import json
import csv
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # loads .env into environment

client = OpenAI()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

# --- Your design context (edit if you want) ---
HMW = "How might we make choosing investments feel as safe and reassuring as using a Ring Doorbell?"
TARGET = "young adults / beginner investors"
EMOTION = "safety"
ANALOGY = "Ring Doorbell (monitoring, alerts, event history, zones/sensitivity, shared access, two-way talk, modes, privacy)"

CATEGORIES = ["Onboarding", "Decision Support", "Risk Alerts", "Education", "Social Support", "Post-Decision Support"]

def call_llm(prompt: str) -> str:
    resp = client.responses.create(
        model=MODEL,
        input=prompt
    )
    return resp.output_text

def safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def try_parse_json(text: str):
    """Try to extract JSON if the model includes extra text."""
    text_stripped = text.strip()
    # First try direct parse
    try:
        return json.loads(text_stripped)
    except json.JSONDecodeError:
        pass
    # Try to find a JSON array substring
    start = text_stripped.find("[")
    end = text_stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text_stripped[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
    return None

def build_initial_prompt() -> str:
    return f"""You are generating concept ideas for a design project.

PRIMARY GOAL (non-negotiable):
Make choosing investments FEEL emotionally safe and reassuring for {TARGET}.
Interpret "safe and reassuring" as: calm, non-overwhelming, confidence-building, low-regret, low-shame, protective, and supportive.

HMW: {HMW}
Audience: {TARGET}
Desired emotion: {EMOTION}
Reference analogy: {ANALOGY}

IMPORTANT:
Ring Doorbells evoke safety through mechanisms like passive monitoring, timely alerts, visibility/clarity, event history, user-controlled sensitivity, shared access, and quick access to help.
Use these as MECHANISMS to create the feeling of safety, not as superficial feature copying.

TASK:
Generate exactly 25 concept ideas for a service that helps young adults choose what to invest in.

For EACH idea, include:
1) Idea name (3–6 words)
2) Ring mechanism used (choose one): Live View, Motion Alerts, Event History/Playback, Motion Zones/Sensitivity, Shared Access, Two-Way Talk, Modes (Home/Away), Snapshot/Check-in, Privacy Controls
3) Safety mechanism (one sentence explaining how it reduces anxiety/uncertainty/regret)
4) A concrete user interaction (what the user does in the product)

Constraints:
- No generic clichés (e.g., “AI-powered personalized investing” without specifics).
- Prioritize psychological safety: reduce fear of loss, fear of being wrong, and fear of not knowing enough.
- Keep ideas implementable and distinct.

Output format:
Numbered list 1–25. Keep each idea compact but specific.
"""


def build_critique_prompt(prev_prompt: str, prev_output: str, iteration_num: int, want_structured_next: bool) -> str:
    structured_note = ""
    if want_structured_next:
        structured_note = f"""
IMPORTANT: The next prompt should request STRUCTURED OUTPUT as JSON array with fields:
idea_name, ring_feature, what_user_does, safety_mechanism, category (one of: {", ".join(CATEGORIES)}).
"""

    return f"""You are acting as a facilitator improving an AI brainstorming prompt.

CONTEXT
HMW: {HMW}
Audience: {TARGET}
Desired emotion: {EMOTION}
Analogy: {ANALOGY}

PREVIOUS PROMPT (Iteration {iteration_num})
{prev_prompt}

PREVIOUS OUTPUT (Iteration {iteration_num})
{prev_output}

YOUR JOB
1) Critique the OUTPUT for: repetition, vagueness, missing directions, weak connection to Ring, lack of safety mechanism clarity, lack of emotional safety, and feasibility.
2) Critique the PROMPT for what caused those issues.
3) Propose 5-8 concrete constraints or additions that would improve the next iteration.
4) Rewrite an improved prompt for the NEXT iteration.

REQUIREMENTS FOR THE REWRITTEN PROMPT
- Must still generate exactly 25 ideas.
- Must force explicit mapping to a Ring feature (choose from: Live View, Motion Alerts, Event History/Playback, Motion Zones/Sensitivity, Shared Access, Two-Way Talk, Modes Home/Away, Snapshot/Check-in, Privacy Controls).
- Must demand a one-sentence “why this increases safety” (or safety mechanism) per idea.
- Must keep outputs legible and easy to cluster.
{structured_note}

FORMAT
Return in exactly two sections:

[CRITIQUE]
(bullets)

[REVISED_PROMPT]
(the full next prompt text)
"""

def extract_revised_prompt(critique_text: str) -> str:
    marker = "[REVISED_PROMPT]"
    idx = critique_text.find(marker)
    if idx == -1:
        # Fallback: return entire critique as "prompt" (not ideal but avoids crash)
        return critique_text.strip()
    return critique_text[idx + len(marker):].strip()

def export_csv_from_ideas(ideas, csv_path: str):
    fieldnames = ["idea_name", "ring_feature", "what_user_does", "safety_mechanism", "category"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in ideas:
            writer.writerow({k: item.get(k, "") for k in fieldnames})

def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = f"ai_concept_dev_self_refine_{run_id}"
    safe_mkdir(out_dir)

    md_log = []
    artifacts = {}

    # -------------------------
    # Iteration 1: Broad ideas
    # -------------------------
    prompt_1 = build_initial_prompt()
    output_1 = call_llm(prompt_1)

    write_text(os.path.join(out_dir, "prompt_1.txt"), prompt_1)
    write_text(os.path.join(out_dir, "output_1.txt"), output_1)

    md_log.append("## Iteration 1 Prompt\n\n" + prompt_1)
    md_log.append("## Iteration 1 Output\n\n" + output_1)

    artifacts["iteration_1"] = {"prompt": prompt_1, "output": output_1}

    # -----------------------------------------
    # Critique 1 -> Generate improved Prompt 2
    # -----------------------------------------
    critique_1_prompt = build_critique_prompt(prompt_1, output_1, iteration_num=1, want_structured_next=False)
    critique_1 = call_llm(critique_1_prompt)
    prompt_2 = extract_revised_prompt(critique_1)

    write_text(os.path.join(out_dir, "critique_1.txt"), critique_1)
    write_text(os.path.join(out_dir, "prompt_2.txt"), prompt_2)

    md_log.append("\n---\n\n## Critique 1 (and Prompt 2)\n\n" + critique_1)
    artifacts["critique_1"] = {"critique_and_rewrite": critique_1, "prompt_2": prompt_2}

    # -------------------------
    # Iteration 2: Improved ideas
    # -------------------------
    output_2 = call_llm(prompt_2)
    write_text(os.path.join(out_dir, "output_2.txt"), output_2)

    md_log.append("\n---\n\n## Iteration 2 Prompt\n\n" + prompt_2)
    md_log.append("## Iteration 2 Output\n\n" + output_2)

    artifacts["iteration_2"] = {"prompt": prompt_2, "output": output_2}

    # ---------------------------------------------------
    # Critique 2 -> Generate improved Prompt 3 (STRUCTURED)
    # ---------------------------------------------------
    critique_2_prompt = build_critique_prompt(prompt_2, output_2, iteration_num=2, want_structured_next=True)
    critique_2 = call_llm(critique_2_prompt)
    prompt_3 = extract_revised_prompt(critique_2)

    write_text(os.path.join(out_dir, "critique_2.txt"), critique_2)
    write_text(os.path.join(out_dir, "prompt_3.txt"), prompt_3)

    md_log.append("\n---\n\n## Critique 2 (and Prompt 3)\n\n" + critique_2)
    artifacts["critique_2"] = {"critique_and_rewrite": critique_2, "prompt_3": prompt_3}

    # -------------------------
    # Iteration 3: Structured JSON
    # -------------------------
    output_3_raw = call_llm(prompt_3)
    write_text(os.path.join(out_dir, "output_3_raw.txt"), output_3_raw)

    parsed = try_parse_json(output_3_raw)
    if parsed is not None:
        # Save pretty JSON + CSV
        json_path = os.path.join(out_dir, "output_3.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        csv_path = os.path.join(out_dir, "ideas_final.csv")
        export_csv_from_ideas(parsed, csv_path)
    else:
        # If JSON parse fails, leave raw file for evidence; you can rerun or manually fix prompt_3.
        pass

    md_log.append("\n---\n\n## Iteration 3 Prompt\n\n" + prompt_3)
    md_log.append("## Iteration 3 Output (raw)\n\n" + output_3_raw)

    artifacts["iteration_3"] = {"prompt": prompt_3, "output_raw": output_3_raw, "parsed_json_ok": parsed is not None}

    # Save one combined markdown artifact and JSON log
    write_text(os.path.join(out_dir, "prompts_and_critiques.md"), "\n\n".join(md_log))
    with open(os.path.join(out_dir, "run_artifacts.json"), "w", encoding="utf-8") as f:
        json.dump(artifacts, f, indent=2)

    print(f"Done. Saved artifacts to: {out_dir}")
    if parsed is None:
        print("Note: Iteration 3 JSON parsing failed. See output_3_raw.txt and prompt_3.txt (tighten JSON instruction and rerun).")

if __name__ == "__main__":
    main()
