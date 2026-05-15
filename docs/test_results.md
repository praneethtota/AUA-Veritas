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
