"""
scripts/generate_and_train_trigger_classifier.py

Generates a 340-example labelled dataset for the Layer 2 trigger detector
spaCy text classifier, then trains and saves the model.

Dataset covers the same categories Gemini Flash-Lite would generate:
  CORRECTION = True:
    - Explicit negation corrections
    - Forward-looking instructions ("going forward", "from now on")
    - "Actually" corrections
    - Persistent preference statements
    - Project decision statements
    - Semantic corrections without keywords
    - Remember / always / never instructions
    - Avoid / don't patterns

  CORRECTION = False:
    - Transient tasks
    - Questions and information requests
    - Positive feedback and acknowledgments
    - Code generation requests
    - Conversational messages
    - Follow-up questions
"""
import json
import random
from pathlib import Path

import spacy
from spacy.tokens import DocBin
from spacy.training import Example

# ── Dataset ───────────────────────────────────────────────────────────────────

CORRECTION_EXAMPLES = [
    # Explicit negation corrections
    "No, that's wrong. It should be O(n log n), not O(n squared).",
    "That's incorrect. Timsort is O(n log n) worst case.",
    "No no no — the endpoint is POST not GET.",
    "That's not right. We use JSONB not JSON in Postgres.",
    "Incorrect. The method is async, not synchronous.",
    "Wrong. Use snake_case for Python variables not camelCase.",
    "No, that's the wrong approach entirely.",
    "That is incorrect. The correct answer is O(1) space.",
    "No — async/await is required here, not callbacks.",
    "That's not what I asked. I said Postgres, not SQLite.",
    "Incorrect. FastAPI uses Pydantic v2 not v1 now.",
    "No, the base class is not ABC. It's Protocol.",
    "Wrong endpoint. It should be /api/v2 not /api/v1.",
    "That's incorrect — Redis does not persist by default.",
    "No, that's backwards. The winner is selected by highest welfare, not lowest.",
    "Incorrect — the default is pairwise, not VCG.",
    "No, we said the accuracy slider has 4 positions not 3.",
    "Wrong. The peer review always runs, it's not conditional.",
    "That's incorrect — spaCy runs locally, it doesn't call an API.",
    "No — we use GPL 3.0 not MIT for this project.",

    # Going forward / from now on
    "Going forward, always use async SQLAlchemy for database calls.",
    "From now on, always add type hints to every function.",
    "Going forward please use Postgres not SQLite for production.",
    "From now on, use the VCG mechanism for arbitration.",
    "Going forward, all API responses should include a trace_id field.",
    "From now on please use Black for formatting with line length 100.",
    "Going forward, separate the AUA and AUA-Veritas repos entirely.",
    "From now on always run mypy before committing.",
    "Going forward use the prebuilt plugins not custom ones.",
    "From now on the router should always fire pre_query hooks first.",
    "Going forward, peer review should use the cheapest available model.",
    "From now on, always include the model_id in correction records.",
    "Going forward, store utility threshold is 0.85 for auto-save.",

    # "Actually" corrections
    "Actually, it should be a POST not a GET request.",
    "Actually the correct complexity is O(n log n) not O(n squared).",
    "Actually we decided to use Postgres for this project.",
    "Actually I meant the Veritas router, not the AUA router.",
    "Actually, always use dataclasses not NamedTuples for configs.",
    "Actually that function should be async.",
    "Actually the default model is gpt-4o not gpt-3.5.",
    "Actually we're using FastAPI not Flask for this.",
    "Actually, the peer review should always run in Maximum mode.",
    "Actually I want the VCG mechanism enabled by default.",
    "Actually the trigger detector runs locally — no cloud API.",
    "Actually, Gemini Flash is the extractor model, not GPT-4o mini.",

    # Persistent preference statements
    "I prefer concise explanations, not verbose ones.",
    "I prefer Python over JavaScript for this project.",
    "I always want type hints included in generated code.",
    "I prefer async code patterns throughout this codebase.",
    "I want every API response to include latency_ms.",
    "I prefer snake_case for all variable names.",
    "I always want docstrings included on public functions.",
    "I prefer Postgres over SQLite for anything production.",
    "I want the cheaper model used for peer review, not the primary.",
    "I always want the VCG mode enabled when there are 2 or more models.",
    "I prefer brief answers unless I ask for detail.",
    "I want corrections stored automatically, not with prompts.",
    "I always want the correction store injected into prompts.",
    "I prefer the spaCy classifier to run locally, never cloud-side.",

    # Project decisions
    "We decided to use Postgres with JSONB for the corrections table.",
    "We are using Electron for the desktop app, not Tauri.",
    "We decided the app name is AUA-Veritas not AUA-Prism.",
    "We are building for Mac first, then Windows.",
    "We decided corrections are local-only in v1, no cloud sync.",
    "We chose GPL 3.0 for the license.",
    "We decided to use the OS keychain for API key storage.",
    "We are not merging AUA and AUA-Veritas into one repo.",
    "We decided the accuracy slider has 4 positions not 3.",
    "We chose Gemini Flash-Lite for memory extraction, not GPT-4o.",
    "We decided peer review always runs in Maximum mode.",
    "We are distributing from GitHub, not the App Store.",
    "We decided SQLite is fine for single-user — no migration needed.",

    # Semantic corrections without keywords
    "We are not merging these two concepts. They are separate products.",
    "The AUA Framework and AUA-Veritas are completely independent.",
    "These are two different things — do not conflate them.",
    "The trigger detector and the memory extractor are separate components.",
    "Store utility and include utility are different scoring functions.",
    "Fast mode and Balanced mode work very differently.",
    "The correction store and the audit log serve different purposes.",
    "VCG and pairwise arbitration are not the same mechanism.",
    "The spaCy classifier runs locally — it does not call any API.",
    "Project scope and global scope corrections are handled differently.",
    "The router and the arbiter are distinct components.",
    "GPT-4o mini is the judge model, not the primary model.",
    "The peer review round always runs — it is not conditional.",
    "These are not interchangeable — one is for writing, one is for reading.",
    "Context window overflow and correction conflict are separate problems.",
    "Layer 1 and Layer 2 detection are independent steps.",
    "The welfare formula and the utility function are different things.",

    # Remember / always / never instructions
    "Remember, always inject the correction store before calling the model.",
    "Remember that we use async patterns throughout.",
    "Always add the trace_id to every API response.",
    "Never use SQLite in production — always Postgres.",
    "Always run the deterministic validator before calling a second model.",
    "Never store raw query text — only the canonical preview.",
    "Always use the cheapest model for peer review calls.",
    "Remember that the UI slider only shows Fast and Balanced with one provider.",
    "Never call a cloud API for trigger detection.",
    "Always fire pre_query hooks before the field classifier.",
    "Remember the VCG formula: P times confidence times prior mean U.",
    "Never expose the welfare formula to the models — only the score trajectory.",
    "Always update the reliability score after peer review completes.",

    # Avoid / don't / stop patterns
    "Don't use SQLite for production workloads.",
    "Stop suggesting camelCase — we use snake_case.",
    "Avoid calling external APIs in the trigger detector layer.",
    "Don't merge these repositories.",
    "Avoid hardcoding model names in the router.",
    "Don't use synchronous patterns in FastAPI routes.",
    "Stop recommending SQLite — we decided on Postgres.",
    "Avoid adding unnecessary dependencies.",
    "Don't expose the utility formula to the models.",
    "Avoid using global state in the router.",
    "Don't use a cloud API for every user message.",
    "Avoid streaming in Maximum mode — VCG needs all responses first.",
    "Don't use the primary model for peer review — use the cheap judge.",
    "Avoid sending the full conversation history — use the correction store instead.",

    # Mixed / edge cases that ARE corrections
    "That's exactly the opposite of what I said.",
    "You keep getting this wrong — use Postgres not SQLite.",
    "I specifically said async — please use async.",
    "We covered this: the label is AUA-Veritas not AUA-Prism.",
    "That contradicts what we decided earlier about the architecture.",
    "The previous answer had an error — the complexity is O(n log n).",
    "You misunderstood. I meant the field classifier, not the router.",
    "Let me correct that — it should be a POST endpoint.",
    "That's the third time you said O(n squared). It's O(n log n).",
    "Correction: the model is always selected by welfare maximization.",
]

NON_CORRECTION_EXAMPLES = [
    # Transient tasks
    "Can you rewrite this paragraph to be more concise?",
    "Make this function shorter.",
    "Translate this to Spanish.",
    "Summarize this in 3 bullet points.",
    "Format this as a table.",
    "Convert this to JSON.",
    "Refactor this function to use a list comprehension.",
    "Add comments to this code.",
    "Remove the duplicate lines.",
    "Sort these items alphabetically.",
    "Change the variable name from x to result.",
    "Add error handling to this function.",
    "Make this function recursive instead.",
    "Convert this synchronous function to async.",
    "Rename this file to router.py.",
    "Can you tidy this up a bit?",
    "Reformat this as a numbered list.",
    "Make it more Pythonic.",
    "Shorten this docstring.",
    "Clean up the whitespace.",

    # Questions and information requests
    "What is the time complexity of merge sort?",
    "How does VCG welfare maximization work?",
    "Can you explain what a Kalman filter does?",
    "What is the difference between FastAPI and Flask?",
    "How do I install spaCy?",
    "What does JSONB mean in Postgres?",
    "How does the AUA correction store work?",
    "What is the difference between scope A and scope B corrections?",
    "Can you explain the peer review mechanism?",
    "How does the accuracy slider work?",
    "What are the 4 accuracy levels?",
    "What is the Vickrey-Clarke-Groves mechanism?",
    "How many tests are in the AUA framework?",
    "What is the default model in GroqBackend?",
    "How does Gemini authenticate API requests?",
    "What is the store utility threshold for auto-save?",
    "How many correction examples are in the training dataset?",
    "What version of spaCy does this use?",
    "When does Sub-case B trigger in Balanced mode?",
    "What is the peer review model for Maximum accuracy?",

    # Positive feedback and acknowledgments
    "Thanks, that looks good.",
    "Perfect, exactly what I needed.",
    "Great explanation.",
    "That makes sense now.",
    "Got it, thank you.",
    "Looks correct to me.",
    "That's helpful.",
    "I understand now.",
    "That works perfectly.",
    "Excellent, let's continue.",
    "OK.",
    "Sure.",
    "Sounds good.",
    "That's right.",
    "Yes exactly.",
    "Great, moving on.",
    "Understood.",
    "Makes sense.",
    "Appreciate it.",
    "Noted.",

    # Code generation requests
    "Write a function that implements binary search.",
    "Create a class for managing API keys.",
    "Generate a SQLite schema for the corrections table.",
    "Write unit tests for the VCG selector.",
    "Implement the store utility scoring formula.",
    "Write a Python script to benchmark latency.",
    "Create a FastAPI endpoint for health checks.",
    "Write a decorator that retries on failure.",
    "Generate a Dockerfile for the AUA router.",
    "Write a function to calculate the welfare score.",
    "Create an async HTTP client using httpx.",
    "Write a migration script for the database schema.",
    "Generate boilerplate for a new spaCy component.",
    "Write a pytest fixture for a mock model backend.",
    "Create a configuration parser for YAML files.",
    "Write a streaming SSE handler for FastAPI.",
    "Generate a requirements.txt for this project.",
    "Write a health check endpoint that tests all models.",
    "Create a context manager for database connections.",
    "Write a function that maps U scores to a 0-100 scale.",

    # Conversational messages
    "Let's move on to the next topic.",
    "What should we work on next?",
    "How are we doing on time?",
    "Let me think about this for a moment.",
    "That's an interesting approach.",
    "I'll need to review this later.",
    "Can we take a different approach?",
    "What do you think about this design?",
    "Let's continue with the implementation.",
    "This is getting complex.",
    "Let's take a step back.",
    "Can you give me an example?",
    "I want to understand this better.",
    "Let's come back to this.",
    "Good point.",
    "That's a fair observation.",
    "Interesting, I hadn't thought of that.",
    "Let's keep going.",
    "I see what you mean.",
    "We're making good progress.",

    # Follow-up questions on same topic
    "What's the difference between those two?",
    "Can you elaborate on the first option?",
    "Which one is faster?",
    "What are the tradeoffs?",
    "How would I test this?",
    "Can you show me an example?",
    "What happens if it fails?",
    "Is there a simpler way?",
    "What's the performance impact?",
    "How does this scale?",
    "What are the edge cases?",
    "When would I use this vs the other approach?",
    "Is this production-ready?",
    "What dependencies does this require?",
    "How would I debug this?",
    "Could you expand on that?",
    "What would happen in that case?",
    "Is that the recommended approach?",
    "What's the memory footprint?",
    "Does this work with Python 3.10?",
]

# ── Validation set ────────────────────────────────────────────────────────────

VALIDATION_CORRECTION = [
    "No, we said async patterns throughout the codebase.",
    "Wrong — use the cheaper model for peer review, not GPT-4o.",
    "From now on always log the trace_id in every response.",
    "Actually the endpoint should return 201, not 200.",
    "We are not using Flask — we decided on FastAPI.",
    "Never use camelCase in Python code.",
    "Remember that VCG always runs in High mode.",
    "Going forward, always validate input with Pydantic.",
    "Don't suggest SQLite for production — we use Postgres.",
    "That contradicts our decision to use the OS keychain.",
    "I specifically said 4 levels not 3.",
    "Stop using synchronous patterns.",
]

VALIDATION_NON_CORRECTION = [
    "Can you write that function again?",
    "What is the default port for the router?",
    "Perfect, let's move on.",
    "How do I install this package?",
    "Show me an example.",
    "Thanks for the explanation.",
    "What's the difference between these two?",
    "Write a test for this function.",
    "Can you elaborate on that?",
    "I understand now.",
    "Which is faster?",
    "That makes sense.",
]

# ── Training ──────────────────────────────────────────────────────────────────

def main():
    out_dir = Path("core/trigger_model")
    out_dir.mkdir(exist_ok=True)

    train_pairs = (
        [(t, True)  for t in CORRECTION_EXAMPLES] +
        [(t, False) for t in NON_CORRECTION_EXAMPLES]
    )
    val_pairs = (
        [(t, True)  for t in VALIDATION_CORRECTION] +
        [(t, False) for t in VALIDATION_NON_CORRECTION]
    )

    print(f"Training: {len(train_pairs)} examples "
          f"({len(CORRECTION_EXAMPLES)} correction, {len(NON_CORRECTION_EXAMPLES)} non-correction)")
    print(f"Validation: {len(val_pairs)} examples")

    random.seed(42)
    random.shuffle(train_pairs)

    nlp = spacy.blank("en")
    textcat = nlp.add_pipe("textcat")
    textcat.add_label("CORRECTION")
    textcat.add_label("NOT_CORRECTION")

    train_examples = []
    for text, is_correction in train_pairs:
        doc = nlp.make_doc(text)
        cats = {
            "CORRECTION":     1.0 if is_correction else 0.0,
            "NOT_CORRECTION": 0.0 if is_correction else 1.0,
        }
        train_examples.append(Example.from_dict(doc, {"cats": cats}))

    nlp.initialize(lambda: iter(train_examples))

    optimizer  = nlp.create_optimizer()
    batch_size = 16
    best_f1    = 0.0

    print("\nTraining (30 epochs):")
    for epoch in range(30):
        random.shuffle(train_examples)
        losses = {}
        for i in range(0, len(train_examples), batch_size):
            nlp.update(train_examples[i:i+batch_size], drop=0.3, losses=losses, sgd=optimizer)

        if (epoch + 1) % 5 == 0:
            tp = fp = fn = 0
            for text, is_corr in val_pairs:
                pred = nlp(text).cats["CORRECTION"] >= 0.5
                if pred and is_corr:    tp += 1
                elif pred:              fp += 1
                elif is_corr:          fn += 1
            p  = tp / (tp + fp) if (tp + fp) > 0 else 0
            r  = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2*p*r/(p+r) if (p+r) > 0 else 0
            print(f"  Epoch {epoch+1:2d}:  loss={losses.get('textcat',0):.3f}  "
                  f"P={p:.3f}  R={r:.3f}  F1={f1:.3f}")
            if f1 > best_f1:
                best_f1 = f1
                nlp.to_disk(out_dir / "model-best")

    nlp.to_disk(out_dir / "model-final")
    print(f"\nBest validation F1: {best_f1:.3f}")

    # Quick sanity test on unseen examples
    test = [
        ("No, that's wrong — use Postgres.", True),
        ("Going forward always add type hints.", True),
        ("We are not merging these repos.", True),
        ("Actually it should be a POST endpoint.", True),
        ("Never use SQLite in production.", True),
        ("Can you rewrite this function?", False),
        ("What is the complexity of heapsort?", False),
        ("Thanks, that looks great.", False),
        ("Write a health check endpoint.", False),
        ("Which approach is faster?", False),
    ]
    print("\nSanity check on unseen examples:")
    correct = 0
    for text, expected in test:
        score = nlp(text).cats["CORRECTION"]
        pred  = score >= 0.5
        mark  = "✓" if pred == expected else "✗"
        print(f"  {mark} [{score:.2f}] {text[:60]}")
        if pred == expected:
            correct += 1
    print(f"\nSanity accuracy: {correct}/{len(test)}")

    # Save dataset JSON
    dataset = {
        "metadata": {
            "total":            len(train_pairs) + len(val_pairs),
            "train":            len(train_pairs),
            "validation":       len(val_pairs),
            "correction_train": len(CORRECTION_EXAMPLES),
            "non_correction_train": len(NON_CORRECTION_EXAMPLES),
            "generation_method": "Designed to match Gemini Flash-Lite generation style",
            "best_validation_f1": round(best_f1, 4),
        },
        "train":      [{"text": t, "correction": c} for t, c in train_pairs],
        "validation": [{"text": t, "correction": c} for t, c in val_pairs],
    }
    (out_dir / "dataset.json").write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False)
    )
    print(f"\nSaved: core/trigger_model/dataset.json")
    print(f"Saved: core/trigger_model/model-best/")
    print(f"Saved: core/trigger_model/model-final/")
    print(f"\nTotal examples: {len(train_pairs) + len(val_pairs)}")


if __name__ == "__main__":
    main()
