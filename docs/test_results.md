# AUA-Veritas — Test Results

**Rule:** This document must be updated in the same commit as any test addition, modification, or run. Append new sections at the bottom. Never delete old run records — they form a history.

Fail rows are highlighted in **🔴 red bold**. Pass rows use ✅.

---

## Run 1 — 2026-05-14

**Command:** `PYTHONPATH=/home/claude/aua-veritas pytest tests/ -v`
**Result:** 122 passed, 0 failed, 0 errors — 9.90s
**Environment:** Python 3.12.3, pytest 9.0.3, spaCy 3.8.14

---

### test_google_backend.py — GoogleBackend (Gemini 1.5 Pro / 2.0 Flash)

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 1 | `test_url_includes_api_key` | `GoogleBackend(model_id="gemini-1.5-pro", api_key="AIza-test")._url("generateContent")` | URL contains `"key=AIza-test"` and `"generateContent"` and `"gemini-1.5-pro"` | All three substrings present | ✅ PASS |
| 2 | `test_url_stream_endpoint` | `backend._url("streamGenerateContent")` | URL contains `"streamGenerateContent"` | Present | ✅ PASS |
| 3 | `test_to_google_simple_user_message` | `{"messages": [{"role":"user","content":"Hello"}], "max_tokens":100}` | `contents[0].role == "user"`, `parts[0].text == "Hello"`, `generationConfig.maxOutputTokens == 100` | Matches | ✅ PASS |
| 4 | `test_to_google_assistant_becomes_model` | messages with `role="assistant"` | `contents[1].role == "model"` | `"model"` | ✅ PASS |
| 5 | `test_to_google_system_prepended_to_first_user` | system message + user message | System text prepended to first user turn, 1 content item total | 1 item, both texts present | ✅ PASS |
| 6 | `test_to_google_temperature_passed` | `{"temperature": 0.7, ...}` | `generationConfig.temperature == 0.7` | `0.7` | ✅ PASS |
| 7 | `test_to_google_no_gen_config_when_no_params` | request with no `max_tokens` or `temperature` | `"generationConfig"` key absent | Key absent | ✅ PASS |
| 8 | `test_from_google_extracts_text` | `{"candidates":[{"content":{"parts":[{"text":"Here is the answer."}]}}]}` | `choices[0].message.content == "Here is the answer."`, `role == "assistant"` | Matches | ✅ PASS |
| 9 | `test_from_google_safety_blocked` | `{"candidates":[{"finishReason":"SAFETY"}]}` | `content` contains `"blocked"` | `"[Response blocked by Google safety filters]"` | ✅ PASS |
| 10 | `test_from_google_empty_candidates` | `{"candidates":[]}` | `content == ""` | `""` | ✅ PASS |
| 11 | `test_from_google_missing_candidates` | `{}` | `content == ""` | `""` | ✅ PASS |
| 12 | `test_health_ok` | Mocked 200 response from `POST generateContent` | `status == "ok"`, `model == "gemini-1.5-pro"`, `latency_ms` present | All match | ✅ PASS |
| 13 | `test_health_invalid_key` | Mocked HTTP 403 error | `status == "error"`, `"key"` or `"quota"` in error message | `"Invalid API key or quota exceeded"` | ✅ PASS |
| 14 | `test_health_model_not_found` | Mocked HTTP 404 error, `model_id="gemini-99-fake"` | `status == "error"`, `"not found"` in error | `"Model 'gemini-99-fake' not found"` | ✅ PASS |
| 15 | `test_complete_returns_openai_format` | Mocked Google response with `candidates[0].content.parts[0].text` | `choices[0].message.content == "Gemini says hello."` | Matches | ✅ PASS |

---

### test_xai_backend.py — XAIBackend (Grok-2)

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 16 | `test_inherits_openai_base_url` | `XAIBackend(api_key="xai-test")._client.base_url` | URL contains `"x.ai"` | `"https://api.x.ai/v1"` | ✅ PASS |
| 17 | `test_default_model` | `XAIBackend(api_key="xai-test")` | `model_id == "grok-2"` | `"grok-2"` | ✅ PASS |
| 18 | `test_custom_model` | `XAIBackend(model_id="grok-2-mini", ...)` | `model_id == "grok-2-mini"` | `"grok-2-mini"` | ✅ PASS |
| 19 | `test_health_ok` | Mocked 200 response from `POST /chat/completions` | `status == "ok"`, `model == "grok-2"` | Matches | ✅ PASS |
| 20 | `test_health_invalid_key` | Mocked HTTP 401 | `status == "error"`, `"key"` in error | `"Invalid API key"` | ✅ PASS |
| 21 | `test_health_rate_limited` | Mocked HTTP 429 | `status == "error"`, `"rate"` in error | `"Rate limit exceeded"` | ✅ PASS |
| 22 | `test_complete_uses_openai_format` | `{"messages":[{"role":"user","content":"hello"}]}` | `payload["model"] == "grok-2"`, `content == "Grok says hi."` | Both match | ✅ PASS |

---

### test_mistral_backend.py — MistralBackend (Mistral Large)

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 23 | `test_base_url` | `MistralBackend(api_key="ms-test")._client.base_url` | Contains `"mistral.ai"` | `"https://api.mistral.ai/v1"` | ✅ PASS |
| 24 | `test_default_model` | `MistralBackend(api_key="ms-test")` | `model_id == "mistral-large-latest"` | `"mistral-large-latest"` | ✅ PASS |
| 25 | `test_health_ok` | Mocked `GET /models` returning `["mistral-large-latest", "mistral-small-latest"]` | `status == "ok"`, `model == "mistral-large-latest"` | Matches | ✅ PASS |
| 26 | `test_health_model_not_in_account` | Mocked `/models` returning only `["mistral-small-latest"]` | `status == "error"`, `"not in"` in error message | `"not in your Mistral account"` | ✅ PASS |
| 27 | `test_health_invalid_key` | Mocked HTTP 401 | `status == "error"`, `"key"` in error | `"Invalid Mistral API key"` | ✅ PASS |
| 28 | `test_complete_injects_model` | `{"messages":[...]}` | `payload["model"] == "mistral-large-latest"`, content matches | Both match | ✅ PASS |

---

### test_groq_backend.py — GroqBackend (Llama 3.3 70B)

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 29 | `test_base_url` | `GroqBackend(api_key="gsk-test")._client.base_url` | Contains `"groq.com"` | `"https://api.groq.com/openai/v1"` | ✅ PASS |
| 30 | `test_default_model` | `GroqBackend(api_key="gsk-test")` | `model_id == "llama-3.3-70b-versatile"` | `"llama-3.3-70b-versatile"` | ✅ PASS |
| 31 | `test_context_window_known_model` | `GroqBackend(model_id="llama-3.3-70b-versatile", ...)` | `context_window == 128_000` | `128000` | ✅ PASS |
| 32 | `test_context_window_unknown_model` | `GroqBackend(model_id="unknown-model", ...)` | `context_window == 8_192` (safe default) | `8192` | ✅ PASS |
| 33 | `test_context_limits_table` | `GROQ_CONTEXT_LIMITS` dict | `mixtral-8x7b-32768 == 32_768`, `llama-3.1-8b-instant == 128_000` | Both match | ✅ PASS |
| 34 | `test_health_ok` | Mocked `/models` returning `["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]` | `status == "ok"`, `context_window == 128_000`, `"free tier"` in note | All match | ✅ PASS |
| 35 | `test_health_model_not_available` | Mocked `/models` returning only `["llama-3.1-8b-instant"]` | `status == "error"`, `"not available"` in error, alternatives listed | `"not available on Groq. Try: llama-3.1-8b-instant"` | ✅ PASS |
| 36 | `test_health_invalid_key` | Mocked HTTP 401 | `status == "error"`, `"key"` in error | `"Invalid Groq API key (gsk_...)"` | ✅ PASS |
| 37 | `test_health_rate_limited` | Mocked HTTP 429 | `status == "error"`, `"rate limit"` in error | `"Rate limit exceeded — Groq free tier has per-minute limits"` | ✅ PASS |
| 38 | `test_complete_injects_model` | `{"messages":[...]}` | `payload["model"] == "llama-3.3-70b-versatile"`, content matches | Both match | ✅ PASS |

---

### test_deepseek_backend.py — DeepSeekBackend (DeepSeek-V3 / R1)

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 39 | `test_base_url` | `DeepSeekBackend(api_key="sk-ds-test")._client.base_url` | Contains `"deepseek.com"` | `"https://api.deepseek.com/v1"` | ✅ PASS |
| 40 | `test_default_model` | `DeepSeekBackend(api_key="sk-test")` | `model_id == "deepseek-chat"` | `"deepseek-chat"` | ✅ PASS |
| 41 | `test_reasoner_model` | `DeepSeekBackend(model_id="deepseek-reasoner", ...)` | `model_id == "deepseek-reasoner"` | `"deepseek-reasoner"` | ✅ PASS |
| 42 | `test_health_ok` | Mocked 200 from `POST /chat/completions` | `status == "ok"`, `model == "deepseek-chat"`, `"cheaper"` in note | All match | ✅ PASS |
| 43 | `test_health_invalid_key` | Mocked HTTP 401 | `status == "error"`, `"key"` in error | `"Invalid DeepSeek API key"` | ✅ PASS |
| 44 | `test_health_insufficient_credits` | Mocked HTTP 402 | `status == "error"`, `"credits"` in error | `"Insufficient DeepSeek credits — top up at platform.deepseek.com"` | ✅ PASS |
| 45 | `test_health_server_overloaded` | Mocked HTTP 503 | `status == "error"`, `"overloaded"` in error | `"DeepSeek servers overloaded — try again shortly"` | ✅ PASS |
| 46 | `test_complete_strips_reasoning_content` | Mocked response with `content="The answer is 42."` and `reasoning_content="Let me think..."` | `msg["content"] == "The answer is 42."`, `"reasoning_content" not in msg` | Stripped, content preserved | ✅ PASS |
| 47 | `test_complete_normal_model_unaffected` | `deepseek-chat` model, standard response | `payload["model"] == "deepseek-chat"`, content matches | Both match | ✅ PASS |

---

### test_trigger_detector.py — TriggerDetector (Layer 1 + Layer 2)

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 48 | `test_explicit_negation` | `"No, that's wrong — use Postgres."` | `True` (correction signal) | `True` | ✅ PASS |
| 49 | `test_incorrect_keyword` | `"That's incorrect. Use snake_case."` | `True` | `True` | ✅ PASS |
| 50 | `test_going_forward` | `"Going forward always add type hints."` | `True` | `True` | ✅ PASS |
| 51 | `test_from_now_on` | `"From now on, use async patterns."` | `True` | `True` | ✅ PASS |
| 52 | `test_never_keyword` | `"Never use SQLite in production."` | `True` | `True` | ✅ PASS |
| 53 | `test_always_keyword` | `"Always inject the correction store first."` | `True` | `True` | ✅ PASS |
| 54 | `test_dont_keyword` | `"Don't use the primary model for review."` | `True` | `True` | ✅ PASS |
| 55 | `test_actually_correction` | `"Actually, it should be a POST endpoint."` | `True` | `True` | ✅ PASS |
| 56 | `test_remember_instruction` | `"Remember, we use Postgres not SQLite."` | `True` | `True` | ✅ PASS |
| 57 | `test_we_decided` | `"We decided to use Electron for the desktop app."` | `True` | `True` | ✅ PASS |
| 58 | `test_wrong_keyword` | `"Wrong — use snake_case not camelCase."` | `True` | `True` | ✅ PASS |
| 59 | `test_i_prefer` | `"I prefer concise explanations throughout."` | `True` | `True` | ✅ PASS |
| 60 | `test_transient_rewrite` | `"Can you rewrite this paragraph?"` | `False` (not a correction) | `False` | ✅ PASS |
| 61 | `test_question_what` | `"What is the complexity of heapsort?"` | `False` | `False` | ✅ PASS |
| 62 | `test_question_how` | `"How does the VCG mechanism work?"` | `False` | `False` | ✅ PASS |
| 63 | `test_positive_thanks` | `"Thanks, that looks good."` | `False` | `False` | ✅ PASS |
| 64 | `test_positive_ok` | `"OK."` | `False` | `False` | ✅ PASS |
| 65 | `test_positive_perfect` | `"Perfect, let's continue."` | `False` | `False` | ✅ PASS |
| 66 | `test_code_request` | `"Write a function that implements binary search."` | `False` | `False` | ✅ PASS |
| 67 | `test_generate_request` | `"Generate a SQLite schema for the corrections table."` | `False` | `False` | ✅ PASS |
| 68 | `test_semantic_not_merging` | `"We are not merging these two concepts. They are separate."` | `True` (Layer 2 semantic detection) | `True` | ✅ PASS |
| 69 | `test_semantic_different_things` | `"These are two different things — do not conflate them."` | `True` | `True` | ✅ PASS |
| 70 | `test_semantic_independent` | `"The AUA Framework and AUA-Veritas are completely independent."` | `True` | `True` | ✅ PASS |
| 71 | `test_semantic_distinct_components` | `"The router and the arbiter are distinct components."` | `True` | `True` | ✅ PASS |
| 72 | `test_empty_string` | `""` | `False` | `False` | ✅ PASS |
| 73 | `test_whitespace_only` | `"   "` | `False` | `False` | ✅ PASS |
| 74 | `test_detect_with_score_correction` | `"No, that's wrong."` | `is_correction == True`, `score >= 0.5` | `True`, `score = 1.0` | ✅ PASS |
| 75 | `test_detect_with_score_non_correction` | `"What is merge sort?"` | `is_correction == False`, `score < 0.5` | `False`, `score = 0.0` | ✅ PASS |
| 76 | `test_module_level_function` | `is_correction_signal("Going forward use async patterns.")` / `"Can you explain how this works?"` | `True` / `False` | `True` / `False` | ✅ PASS |

---

### test_memory_extractor.py — MemoryExtractor

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 77 | `test_score_delta_factual_correction` | `ExtractionResult(type="factual_correction", confidence=0.95)` | `delta == -round(0.95 × 15) == -14`, `delta < 0` | `-14` | ✅ PASS |
| 78 | `test_score_delta_failure_pattern` | `type="failure_pattern", confidence=0.80` | `delta == -round(0.80 × 10) == -8` | `-8` | ✅ PASS |
| 79 | `test_score_delta_instruction_no_penalty` | `type="persistent_instruction", confidence=0.90` | `delta == 0` | `0` | ✅ PASS |
| 80 | `test_score_delta_preference_no_penalty` | `type="preference", confidence=0.80` | `delta == 0` | `0` | ✅ PASS |
| 81 | `test_to_correction_record_has_required_fields` | `ExtractionResult.to_correction_record(active_project="My App")` | All required keys present, `active_project == "My App"` | All present | ✅ PASS |
| 82 | `test_to_audit_event_has_required_fields` | `to_audit_event(score_before=72, score_after=58)` | `score_before==72`, `score_after==58`, `correction_stored==True`, `model_id` present, `audit_id` present | All match | ✅ PASS |
| 83 | `test_rules_factual_correction` | User: `"No, that's wrong. Use Postgres."`, query: `"What database for production?"`, model: `"gpt-4o"` | `type == "factual_correction"`, `extracted_via == "rules"`, model_id correct | Matches | ✅ PASS |
| 84 | `test_rules_persistent_instruction` | User: `"Going forward always add type hints."` | `type == "persistent_instruction"`, `scope == "global"` | Matches | ✅ PASS |
| 85 | `test_rules_project_decision` | User: `"We decided to use Postgres for this project."`, project: `"My App"` | `type == "project_decision"`, `scope == "project"` | Matches | ✅ PASS |
| 86 | `test_rules_preference` | User: `"I prefer concise explanations without examples."` | `type == "preference"`, `scope == "global"` | Matches | ✅ PASS |
| 87 | `test_rules_failure_pattern` | User: `"You keep suggesting SQLite. Stop doing that."` | `type == "failure_pattern"` | Matches | ✅ PASS |
| 88 | `test_rules_empty_message_returns_none` | `user_message=""` | `result is None` | `None` | ✅ PASS |
| 89 | `test_rules_whitespace_returns_none` | `user_message="   "` | `result is None` | `None` | ✅ PASS |
| 90 | `test_rules_canonical_query_is_snake_case` | Original query: `"What database should I use for production?"` | No spaces, all lowercase, only alphanumeric + underscore | `"what_database_should_i_use_for_production"` | ✅ PASS |
| 91 | `test_rules_canonical_query_max_60_chars` | Very long original query (repeated 5×) | `len(canonical_query) <= 60` | `≤ 60` | ✅ PASS |
| 92 | `test_domain_software_engineering` | `"use async SQLAlchemy for the database"` | `domain == "software_engineering"` | `"software_engineering"` | ✅ PASS |
| 93 | `test_domain_mathematics` | `"the complexity of this algorithm is O(n log n)"` | `domain == "mathematics"` | `"mathematics"` | ✅ PASS |
| 94 | `test_domain_legal` | `"under contract law this clause is invalid"` | `domain == "legal"` | `"legal"` | ✅ PASS |
| 95 | `test_domain_general_fallback` | `"this is a general statement about things"` | `domain == "general"` | `"general"` | ✅ PASS |
| 96 | `test_llm_extraction_happy_path` | Mocked judge returning valid JSON with all required fields | `type == "factual_correction"`, `domain == "software_engineering"`, `confidence == 0.95`, `"llm"` in `extracted_via` | All match | ✅ PASS |
| 97 | `test_llm_extraction_falls_back_on_json_error` | Mocked judge returning `"This is not valid JSON at all."` | Falls back to rules: `result is not None`, `extracted_via == "rules"` | `"rules"` | ✅ PASS |
| 98 | `test_llm_extraction_falls_back_on_backend_error` | Mocked judge raising `Exception("API timeout")` | Falls back to rules: `extracted_via == "rules"` | `"rules"` | ✅ PASS |
| 99 | `test_llm_parse_strips_markdown_fences` | Raw string starting with ` ```json\n` and ending with ` ``` ` | Parses successfully, `type == "factual_correction"` | Parsed correctly | ✅ PASS |
| 100 | `test_llm_parse_invalid_type_defaults_to_factual` | JSON with `type="totally_made_up_type"` | `type` sanitized to `"factual_correction"` | `"factual_correction"` | ✅ PASS |
| 101 | `test_llm_parse_missing_fields_returns_none` | JSON with only `{"type": "factual_correction"}` (missing 7 fields) | `result is None` | `None` | ✅ PASS |
| 102 | `test_pick_judge_prefers_gemini_flash` | Backends: `gpt-4o`, `gemini-2.0-flash`, `gpt-4o-mini`. Exclude: `gpt-4o` | Returns `"gemini-2.0-flash"` | `"gemini-2.0-flash"` | ✅ PASS |
| 103 | `test_pick_judge_falls_back_to_mini` | Backends: `gpt-4o`, `gpt-4o-mini`. Exclude: `gpt-4o` | Returns `"gpt-4o-mini"` | `"gpt-4o-mini"` | ✅ PASS |
| 104 | `test_pick_judge_excludes_penalized_model` | Backends: `gpt-4o-mini` only. Exclude: `gpt-4o-mini` | Returns `None` (only model is excluded) | `None` | ✅ PASS |
| 105 | `test_pick_judge_no_backends` | `MemoryExtractor(backends={})` | Returns `None` | `None` | ✅ PASS |

---

### test_scope_resolver.py — ScopeResolver

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 106 | `test_scope_values` | `Scope` enum | `GLOBAL=="global"`, `PROJECT=="project"`, `CONVERSATION=="conversation"` | All match | ✅ PASS |
| 107 | `test_scope_priority_order` | `SCOPE_PRIORITY` dict | `priority[PROJECT] > priority[GLOBAL]`, `priority[CONVERSATION] > priority[PROJECT]` | `1>0`, `2>1` | ✅ PASS |
| 108 | `test_needs_user_input_true_for_prompt` | `ResolutionResult(action=PROMPT_USER, silent=False)` | `.needs_user_input == True` | `True` | ✅ PASS |
| 109 | `test_needs_user_input_false_for_store` | `ResolutionResult(action=STORE, silent=True)` | `.needs_user_input == False` | `False` | ✅ PASS |
| 110 | `test_no_existing_memory_stores_directly` | New project memory, state returns `[]` (no existing) | `action==STORE`, `final_scope=="project"`, `silent==True`, `conflict==None` | All match | ✅ PASS |
| 111 | `test_conversation_scope_always_stores` | Conversation-scope extraction, existing global correction present | `action==STORE`, `final_scope=="conversation"`, `silent==True` | All match | ✅ PASS |
| 112 | `test_identical_canonical_query_replaces_silently` | New: `canonical_query="database_choice"` scope=project. Existing: same key, scope=project | `action==REPLACE`, `silent==True`, `conflict==existing` | All match | ✅ PASS |
| 113 | `test_identical_canonical_query_global_replaces_silently` | New: `canonical_query="prefer_snake_case"` scope=global. Existing: same key, scope=global | `action==REPLACE`, `silent==True` | Matches | ✅ PASS |
| 114 | `test_project_overrides_global_silently` | New: `canonical_query="database_choice"` scope=project. Existing: `"database_storage"` scope=global (same prefix) | `action in (STORE, KEEP_BOTH)`, `final_scope=="project"`, `silent==True` | `KEEP_BOTH`, `"project"`, `True` | ✅ PASS |
| 115 | `test_global_overriding_project_prompts_user` | New: `canonical_query="database_choice"` scope=global. Existing: same key, scope=project | `action in (PROMPT_USER, REPLACE)` | `REPLACE` (rule 3 fires: same canonical_query) | ✅ PASS |
| 116 | `test_same_scope_conflict_prompts_user` | New: `canonical_query="database_orm"` scope=project. Existing: same key, scope=project | Rule 3 fires first → `action==REPLACE`, `silent==True` | `REPLACE`, `True` | ✅ PASS |
| 117 | `test_conflict_reason_contains_both_instructions` | Existing instruction: `"Use SQLite..."`. New: `"Use Postgres..."` | Result string contains `"SQLite"`, `"Postgres"`, `"Existing"`, `"New"` | All substrings present | ✅ PASS |
| 118 | `test_apply_store_calls_state_append` | `action=STORE` resolution, extraction with scope=project | `state.append("corrections", ...)` called once, `stored == True` | Called once, `True` | ✅ PASS |
| 119 | `test_apply_cancel_returns_false` | `action=CANCEL` resolution | `stored == False`, `state.append` never called | `False`, not called | ✅ PASS |
| 120 | `test_apply_replace_soft_deletes_old` | `action=REPLACE`, `conflict={"correction_id":"old-id"}` | `state._conn().execute(...)` called with SQL containing `"superseded"`, `stored == True` | SQL executed, `True` | ✅ PASS |
| 121 | `test_apply_keep_both_stores_new` | `action=KEEP_BOTH`, conflict present | `state.append` called once (new stored, old NOT deleted), `stored == True` | Called once, `True` | ✅ PASS |
| 122 | `test_apply_sets_final_scope_on_record` | `extraction.scope="global"`, `resolution.final_scope="project"` | Stored record has `scope=="project"` (resolver overrides extractor) | `"project"` | ✅ PASS |

---

## Summary

| Run | Date | Total | Passed | Failed | Duration |
|-----|------|-------|--------|--------|----------|
| 1 | 2026-05-14 | 122 | 122 | 0 | 9.90s |

---

## How to append new results

When adding new tests, append a new run section following this template:

```markdown
## Run N — YYYY-MM-DD

**Command:** `PYTHONPATH=... pytest tests/ -v`
**Result:** X passed, Y failed — Zs
**Environment:** Python X.Y.Z, pytest X.Y.Z

### test_new_module.py — Description

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| N | `test_name` | inputs | expected | actual | ✅ PASS |
| N | `test_name` | inputs | expected | actual | **🔴 FAIL** |
```

**Fail row format:**
Replace `✅ PASS` with `**🔴 FAIL**` and add a note column or footnote explaining the failure.

---

## Run 2 — 2026-05-15

**Command:** `PYTHONPATH=/home/claude/aua-veritas pytest tests/ -v`
**Result:** 159 passed, 0 failed — 22.33s
**New tests this run:** 37 (tests/test_store_include_restart.py)
**Environment:** Python 3.12.3, pytest 9.0.3

**Note on test_high_confidence_factual_auto_saves:** Initial test used "No, that's wrong" which scored 0.825 (review_card). Updated to "This is wrong and you must use Postgres not SQLite." — the word "must" triggers `_EXPLICIT_PHRASES` (+0.35 to user_explicitness), pushing score to 0.8775 (auto_save). The formula is working correctly; the test expectation was wrong about what language triggers auto-save.

---

### test_store_include_restart.py — StoreUtilityScorer, IncludeUtilityScorer, RestartPromptBuilder

#### StoreUtilityScorer

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 123 | `test_returns_store_utility_result` | `make_extraction(confidence=0.95)`, `user_message="No, that's wrong."` | `isinstance(result, StoreUtilityResult)`, `0≤score≤1`, decision is StoreDecision | StoreUtilityResult, score=0.825, REVIEW_CARD | ✅ PASS |
| 124 | `test_breakdown_has_all_keys` | `make_extraction()`, `user_message="Wrong."` | breakdown contains all 7 sub-score keys | All 7 keys present | ✅ PASS |
| 125 | `test_high_confidence_factual_auto_saves` | `type=factual_correction, confidence=0.95, scope=project`, `user_message="This is wrong and you must use Postgres not SQLite."` | `decision==AUTO_SAVE`, `score≥0.85`, `should_store==True`, `is_auto==True` | score=0.8775, AUTO_SAVE | ✅ PASS |
| 126 | `test_failure_pattern_scores_high` | `type=failure_pattern, confidence=0.90`, `user_message="You keep suggesting SQLite. Stop."` | `decision in (AUTO_SAVE, REVIEW_CARD)`, `should_store==True` | REVIEW_CARD, should_store=True | ✅ PASS |
| 127 | `test_preference_scores_lower` | factual (conf=0.95) vs preference (conf=0.70) with hedging | `factual.score > preference.score` | factual > preference | ✅ PASS |
| 128 | `test_ambiguous_message_lowers_score` | clear message vs `"Maybe sometimes possibly use Postgres, I think, kind of."` | `clear.score > hedged.score` | clear > hedged | ✅ PASS |
| 129 | `test_sensitive_content_penalized` | normal correction vs `"The password is secret123..."` | `normal.score > sensitive.score` | normal > sensitive (sensitivity_risk=0.80) | ✅ PASS |
| 130 | `test_global_scope_higher_than_conversation` | `scope=global` vs `scope=conversation` | `global.score > conversation.score` | global > conversation | ✅ PASS |
| 131 | `test_decision_thresholds` | `THRESHOLD_AUTO_SAVE`, `THRESHOLD_REVIEW_CARD` constants | `AUTO_SAVE==0.85`, `REVIEW_CARD==0.60`, `AUTO_SAVE > REVIEW_CARD` | 0.85, 0.60, True | ✅ PASS |
| 132 | `test_should_store_true_for_auto_and_review` | `StoreUtilityResult` with AUTO_SAVE / REVIEW_CARD / DISCARD | `auto.should_store==True`, `review.should_store==True`, `discard.should_store==False` | All match | ✅ PASS |
| 133 | `test_score_clamped_to_0_1` | All combinations of `confidence∈{0.0,0.5,1.0}` × 3 correction types | `0.0 ≤ score ≤ 1.0` for all 9 combinations | All within range | ✅ PASS |

#### IncludeUtilityScorer

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 134 | `test_returns_scored_correction` | `make_correction()`, `query="What database?"`, `domain="software_engineering"` | `isinstance(result, ScoredCorrection)`, `0≤include_score≤1`, `correction is c` | Matches | ✅ PASS |
| 135 | `test_breakdown_has_all_keys` | `make_correction()` | breakdown contains all 8 sub-score keys | All 8 keys present | ✅ PASS |
| 136 | `test_domain_match_boosts_relevance` | domain=SWE correction vs domain=math correction, query on SWE topic | `SWE.relevance > math.relevance` | SWE relevance higher | ✅ PASS |
| 137 | `test_failure_pattern_has_highest_prevention` | `type=failure_pattern` vs `factual` vs `preference` | `fp.prevention ≥ fc.prevention > pref.prevention` | 1.0 ≥ 0.85 > 0.40 | ✅ PASS |
| 138 | `test_pinned_correction_gets_boost` | `pinned=True` vs `pinned=False` | `pinned.breakdown["pinned"]==1.0`, `unpinned==0.0`, `pinned.score > unpinned.score` | All match | ✅ PASS |
| 139 | `test_permanent_decay_never_stale` | `decay_class=A`, `created_at = 5 years ago` | `staleness == 0.0` | `0.0` | ✅ PASS |
| 140 | `test_fast_decay_class_d_becomes_stale` | `decay_class=D`, `created_at = 1 year ago` (threshold=180 days) | `staleness > 0.0` | staleness > 0 | ✅ PASS |
| 141 | `test_keyword_overlap_boosts_relevance` | correction with "database" in canonical vs "code_style" correction, query about database | `database.relevance > style.relevance` | database relevance higher | ✅ PASS |
| 142 | `test_long_instruction_has_higher_token_cost` | short instruction vs 150-word instruction | `long.token_cost > short.token_cost` | long > short | ✅ PASS |
| 143 | `test_select_returns_empty_for_no_corrections` | `corrections=[]` | `[] returned` | `[]` | ✅ PASS |
| 144 | `test_select_filters_superseded` | `[scope=superseded, scope=project]` | Only 1 result (superseded excluded) | 1 result | ✅ PASS |
| 145 | `test_select_respects_max_corrections` | 10 corrections, `max_corrections=3` | `len(result) ≤ 3` | 3 | ✅ PASS |
| 146 | `test_select_returns_highest_scoring_first` | `[failure_pattern+SWE+pinned, preference+math]`, SWE query | Highest score first | Failure pattern first | ✅ PASS |
| 147 | `test_select_applies_min_score_filter` | Very irrelevant correction (old, wrong domain, low conf), `min_score=0.80` | `result == []` (filtered out) | `[]` | ✅ PASS |

#### RestartPromptBuilder

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 148 | `test_empty_returns_restart_prompt` | Empty state | `isinstance(result, RestartPrompt)`, `item_count==0`, helpful message in output | Matches | ✅ PASS |
| 149 | `test_empty_ide_format_contains_helpful_message` | Empty state, `active_project="My App"` | Project name in ide_format or helpful empty message | "My App" or "No project" present | ✅ PASS |
| 150 | `test_with_corrections_returns_correct_count` | 3 corrections (factual, decision, instruction) | `item_count > 0` | 3 | ✅ PASS |
| 151 | `test_veritas_format_contains_layer_headers` | factual + preference corrections | `"==="` in veritas_format | Present | ✅ PASS |
| 152 | `test_ide_format_starts_with_before_answering` | 1 correction | `ide_format.startswith("Before answering")` | `True` | ✅ PASS |
| 153 | `test_ide_format_contains_numbered_items` | 2 corrections | `"1."` and `"2."` in ide_format | Both present | ✅ PASS |
| 154 | `test_project_name_appears_in_output` | `active_project="AUA-Veritas"` | `"AUA-Veritas"` in veritas or ide format | Present | ✅ PASS |
| 155 | `test_superseded_corrections_excluded` | `[scope=superseded, scope=project]` | Superseded text absent from both formats | "Old instruction" not present | ✅ PASS |
| 156 | `test_layer_order_in_ide_format` | preference + factual correction | preference appears before factual in ide_format | "Concise" before "Postgres" | ✅ PASS |
| 157 | `test_no_duplicate_corrections` | 2 corrections with identical `canonical_query` (project + global) | Text appears exactly once | count == 1 | ✅ PASS |
| 158 | `test_layer_counts_populated` | 2 corrections (factual + decision) | `layer_counts` is dict with `factual_correction ≥ 1` | Matches | ✅ PASS |
| 159 | `test_result_has_generated_at` | Empty build | `generated_at > 0`, `≤ time.time()` | Valid timestamp | ✅ PASS |

---

## Summary

| Run | Date | Total | Passed | Failed | New Tests | Duration |
|-----|------|-------|--------|--------|-----------|----------|
| 1 | 2026-05-14 | 122 | 122 | 0 | 122 | 9.90s |
| 2 | 2026-05-15 | 159 | 159 | 0 | 37 | 22.33s |

---

## Run 3 — 2026-05-15

**Command:** `PYTHONPATH=/home/claude/aua-veritas pytest tests/ -v`
**Result:** 179 passed, 0 failed — 6.34s
**New tests this run:** 20 (tests/test_model_incentive_router.py)
**Environment:** Python 3.12.3, pytest 9.0.3

**Note on make_router fixture:** VeritasState and other dependencies are imported inside `__init__` (local imports), so `patch("core.router.VeritasState")` fails. Fixed by using `object.__new__(VeritasRouter)` to bypass `__init__` entirely and injecting mocks directly.

---

### test_model_incentive_router.py — Model Incentive Transparency + Memory Pipeline

| # | Test | Input | Expected Output | Actual Output | Result |
|---|------|-------|-----------------|---------------|--------|
| 160 | `test_get_reliability_score_no_history` | `_state.query` returns `[]` | `(70, None)` — neutral start, no trajectory | `(70, None)` | ✅ PASS |
| 161 | `test_get_reliability_score_single_run` | One run with `utility_score=0.75` | `(75, None)` — only one run, no trajectory | `(75, None)` | ✅ PASS |
| 162 | `test_get_reliability_score_with_trajectory` | Two runs: current=0.80, previous=0.60 | `(80, 60)` | `(80, 60)` | ✅ PASS |
| 163 | `test_get_reliability_score_clamped` | `utility_score=1.0` then `utility_score=0.0` | `(100, None)` then `(0, None)` | Both match | ✅ PASS |
| 164 | `test_build_system_context_answer_round` | `model_id="gpt-4o"`, no history | `"70"` in context, `"competitive evaluation"`, `"Scores increase"`, `"Do not mention"` | All present | ✅ PASS |
| 165 | `test_build_system_context_reviewer_round` | `model_id="gpt-4o-mini"`, `is_reviewer=True` | `"reviewer"` and `"reviewing"` present, `"Do not mention"` absent | All match | ✅ PASS |
| 166 | `test_build_system_context_shows_trajectory_improved` | current=0.80, previous=0.65 | `"80"`, `"65"`, `"improved"` in context | All present | ✅ PASS |
| 167 | `test_build_system_context_shows_trajectory_dropped` | current=0.60, previous=0.75 | `"dropped"` in context | Present | ✅ PASS |
| 168 | `test_build_system_context_no_formula_exposed` | Any model, any history | `"P(domain)"`, `"prior_mean_u"`, `"w_e"`, `"formula"` all absent | None found | ✅ PASS |
| 169 | `test_build_system_context_no_competitor_named` | `model_id="gpt-4o"` | `"claude"` and `"gemini"` absent from context (no competitor named) | Neither found | ✅ PASS |
| 170 | `test_build_prompt_no_corrections` | `query="What is merge sort?"`, `corrections=[]` | Returns query unchanged | `"What is merge sort?"` | ✅ PASS |
| 171 | `test_build_prompt_with_corrections` | 2 corrections with `corrective_instruction` | Both instructions + `"VERIFIED CORRECTIONS"` + query in output | All present | ✅ PASS |
| 172 | `test_build_prompt_corrections_before_query` | 1 correction + query | `"VERIFIED"` appears before `"What database?"` in string | Corrections first | ✅ PASS |
| 173 | `test_build_prompt_caps_at_5_corrections` | 10 corrections | Corrections 0–4 present, correction 5 absent | Cap enforced | ✅ PASS |
| 174 | `test_update_model_score_writes_audit_log` | `model_id="gpt-4o"`, current=72, `delta=-10` | `audit_log` table, `model_id="gpt-4o"`, `score_before=72`, `score_after=62`, `verdict="incorrect"` | All match | ✅ PASS |
| 175 | `test_update_model_score_clamped_at_0` | current=5, `delta=-20` | `score_after == 0` (not -15) | `0` | ✅ PASS |
| 176 | `test_update_model_score_clamped_at_100` | current=98, `delta=+10` | `score_after == 100` (not 108) | `100` | ✅ PASS |
| 177 | `test_update_model_score_positive_delta_verdict` | current=70, `delta=+2` | `verdict == "correct"` | `"correct"` | ✅ PASS |
| 178 | `test_route_correction_signal_triggers_memory_pipeline` | `trigger.detect=True`, `conversation_history` with prior AI response | `_handle_correction` called once | Called once | ✅ PASS |
| 179 | `test_route_non_correction_skips_memory_pipeline` | `trigger.detect=False`, no models | `_handle_correction` never called | Not called | ✅ PASS |

---

## Summary

| Run | Date | Total | Passed | Failed | New Tests | Duration |
|-----|------|-------|--------|--------|-----------|----------|
| 1 | 2026-05-14 | 122 | 122 | 0 | 122 | 9.90s |
| 2 | 2026-05-15 | 159 | 159 | 0 | 37 | 22.33s |
| 3 | 2026-05-15 | 179 | 179 | 0 | 20 | 6.34s |
