#!/usr/bin/env python3
"""
TrueArch Live Evaluation Harness - Human/Messy Prompts
===========================================================

This script performs a REAL evaluation by calling the Gemini API.
It loops through human-like, messy prompts across
two models: gemini-1.5-pro-latest and gemini-1.5-flash-latest.

It compares:
  Variant A: Raw Gemini (no TrueArch)
  Variant C: Gemini with TrueArch architectural intelligence injected (via local python engine to bypass network port bindings)

Run:
    python benchmark/human_messy_benchmark.py
"""

import os
import time
import json
from datetime import datetime

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import local TrueArch engine to bypass local network port binding issues in sandbox
from src.recommendation.stack_engine import StackRecommendationEngine
from src.recommendation.models import StackQuery
from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: Missing google-genai SDK. Please run: pip install google-genai")
    exit(1)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyD7AbCha25YuGoEMCqkwHklIUSRxIEeGYw")
client = genai.Client(api_key=GEMINI_API_KEY)

# Initialize TrueArch Engine locally
loader = FrameworkLoader(data_dir="data/frameworks")
frameworks = loader.load_all()
scoring_engine = ScoringEngine()
for fw in frameworks.values():
    fw.computed_scores = scoring_engine.compute_scores(fw)

engine = StackRecommendationEngine(frameworks)

MODELS = ["gemini-pro-latest", "gemini-flash-latest"]

# 5 Human-like, poorly-written or vague prompts
TASKS = [
    {
        "id": "messy_1_vague",
        "description": "need a fast api backend with some ai stuff and redis i think, deploy on aws",
        "payload": {
            "problem": "need a fast api backend with some ai stuff and redis i think, deploy on aws",
            "language": "python",
            "priority": "performance"
        }
    },
    {
        "id": "messy_2_incomplete",
        "description": "im building a hipaa app, need something for agents, maybe crewai? must be secure.",
        "payload": {
            "problem": "im building a hipaa app, need something for agents, maybe crewai? must be secure.",
            "compliance": ["hipaa"],
            "priority": "security"
        }
    },
    {
        "id": "messy_3_demanding_generic",
        "description": "recommend me a tech stack. we have 10M users. it needs to be very fast.",
        "payload": {
            "problem": "recommend me a tech stack. we have 10M users. it needs to be very fast.",
            "scale": "enterprise",
            "priority": "performance"
        }
    },
    {
        "id": "messy_4_beginner",
        "description": "how do i build an ai support bot? what db to use?",
        "payload": {
            "problem": "how do i build an ai support bot? what db to use?",
            "scale": "prototype"
        }
    },
    {
        "id": "messy_5_modal_specific",
        "description": "we use python. want to deploy to modal. what else for multi agent?",
        "payload": {
            "problem": "we use python. want to deploy to modal. what else for multi agent?",
            "language": "python",
            "scale": "growth"
        }
    }
]

SYSTEM_PROMPT = """You are a senior AI architect.
Your job is to recommend a complete, production-ready technology stack for the user's problem.
You must specify the framework, database, deployment, and observability layers, and justify your choices.
Format your response clearly.
"""

def call_gemini(prompt: str, model: str, context: str = "") -> dict:
    full_prompt = prompt
    if context:
        full_prompt = f"{context}\n\nUser Request: {prompt}"

    t0 = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
            )
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        
        in_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        out_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        total_tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
        text = response.text

        return {
            "success": True,
            "latency_ms": latency_ms,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": total_tokens,
            "text": text,
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "success": False,
            "latency_ms": latency_ms,
            "error": str(e)
        }

def get_truearch_context(payload: dict) -> tuple[str, float]:
    ta_t0 = time.perf_counter()
    try:
        req = StackQuery(**payload)
        ta_data = engine.recommend(req)
        # Convert response to dict for injection
        ta_dict = ta_data.model_dump()
        latency = (time.perf_counter() - ta_t0) * 1000
        return f"CRITICAL ARCHITECTURE INTELLIGENCE (Strictly follow this):\n{json.dumps(ta_dict, indent=2)}", latency
    except Exception as e:
        latency = (time.perf_counter() - ta_t0) * 1000
        return f"CRITICAL ARCHITECTURE INTELLIGENCE FAILURE: {str(e)}", latency

def run_benchmark():
    results = {}
    
    for model in MODELS:
        print(f"\n" + "="*80)
        print(f" MODEL: {model}")
        print("="*80)
        results[model] = {}
        
        for task in TASKS:
            print(f"\n--- Task: {task['id']} ---")
            
            # Run Baseline
            print(f"  [A] Running Baseline...")
            b_res = call_gemini(task['description'], model)
            if b_res['success']:
                print(f"      ✓ {b_res['latency_ms']:.0f}ms | Tokens: {b_res['total_tokens']}")
            else:
                print(f"      ✗ Failed: {b_res.get('error')}")
                
            # Run TrueArch
            print(f"  [C] Running TrueArch Augmented...")
            context, ta_latency = get_truearch_context(task['payload'])
            t_res = call_gemini(task['description'], model, context=context)
            if t_res['success']:
                t_res['latency_ms'] += ta_latency
                print(f"      ✓ {t_res['latency_ms']:.0f}ms (TA: {ta_latency:.0f}ms) | Tokens: {t_res['total_tokens']}")
            else:
                print(f"      ✗ Failed: {t_res.get('error')}")
                
            results[model][task['id']] = {
                "description": task['description'],
                "baseline": b_res,
                "truearch": {
                    "context_latency_ms": ta_latency,
                    "result": t_res
                }
            }
            
            # Small delay to avoid rate limits
            time.sleep(2)
            
    # Save results
    out_file = f"benchmark/human_messy_results_{int(time.time())}.json"
    os.makedirs("benchmark", exist_ok=True)
    with open(out_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "models": MODELS,
            "results": results
        }, f, indent=2)
    print(f"\n[✓] Full benchmark results saved to: {out_file}")

if __name__ == "__main__":
    run_benchmark()
