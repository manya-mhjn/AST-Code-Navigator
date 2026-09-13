# LLM-DND Code Intelligence Agent: 200-Question Evaluation & Ground-Truth Benchmark

This document serves as the master evaluation harness for the **CodeNavigator Next-Gen Agent Architecture** (`agentic_nextgen.py`) against the **`LLM-DND`** repository (`dnd`).

Every question includes:
1. **The Question Query**
2. **Expected Agent Plan & Tool Chain**
3. **Ground Truth Solution** (with exact file paths, line numbers, formulas, and AST relationships)
4. **Architectural Verification Target** (what edge case or graph edge is being validated)

---

## Table of Contents
- [Category 1: Upstream Callers & Caller Chains (Q1–Q20)](#category-1-upstream-callers--caller-chains)
- [Category 2: Downstream Callees & Execution Trees (Q21–Q40)](#category-2-downstream-callees--execution-trees)
- [Category 3: Blast Radius & Impact Analysis (Q41–Q60)](#category-3-blast-radius--impact-analysis)
- [Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback) (Q61–Q80)](#category-4-deliberate-typos--near-miss-symbols)
- [Category 5: State & Variable Reference Audits (Q81–Q105)](#category-5-state--variable-reference-audits)
- [Category 6: Environment Variables & Configuration Audits (Q106–Q125)](#category-6-environment-variables--configuration-audits)
- [Category 7: Exact AST Definitions & Inner Closures (Q126–Q145)](#category-7-exact-ast-definitions--inner-closures)
- [Category 8: Type Hierarchy, OOP & Class Introspection (Q146–Q160)](#category-8-type-hierarchy-oop--class-introspection)
- [Category 9: Dead Code, Orphans & Reachability (Q161–Q175)](#category-9-dead-code-orphans--reachability)
- [Category 10: Architecture Coupling & Modularity Boundaries (Q176–Q185)](#category-10-architecture-coupling--modularity-boundaries)
- [Category 11: Parameter Lineage & Value Propagation (Q186–Q193)](#category-11-parameter-lineage--value-propagation)
- [Category 12: Multi-File Conceptual / Method 1 Queries (Q194–Q200)](#category-12-multi-file-conceptual--method-1-queries)

---

## Category 1: Upstream Callers & Caller Chains

### Q01: Who calls `load_characters()` in the codebase?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='load_characters', direction='incoming')`
* **Ground Truth Solution:**
  `load_characters()` (defined in `src/game_workflows/loaders.py:12-16`) is called by **3 distinct call sites**:
  1. `display_character_list()` in `src/game_workflows/player.py` (via import)
  2. `start_adventure()` in `src/game_workflows/core.py:32`
  3. `OllamaApi.start_adventure()` in `src/api_workflows/call_api.py:49`
* **Verification Target:** Multi-file caller aggregation across 3 modules.

### Q02: What are all the call sites that invoke `save_characters()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='save_characters', direction='incoming')`
* **Ground Truth Solution:**
  `save_characters()` (defined in `src/game_workflows/loaders.py:19-21`) is called by:
  1. `create_character_form()` in `src/game_workflows/player.py` when saving a newly minted hero to `characters.json`.
* **Verification Target:** Direct edge resolution from `player.py` to `loaders.py`.

### Q03: Where is `save_adventure()` called across the entire repository?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='save_adventure', direction='incoming')`
* **Ground Truth Solution:**
  `save_adventure()` (defined in `src/game_workflows/loaders.py:47-63`) is called exclusively by:
  1. `start_adventure()` in `src/game_workflows/core.py:75` (after generating the initial adventure opening narrative and naming it).
* **Verification Target:** Cross-module caller detection (`core.py` -> `loaders.py`).

### Q04: What functions call `load_adventure()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='load_adventure', direction='incoming')`
* **Ground Truth Solution:**
  `load_adventure()` (`loaders.py:24-36`) is called by:
  1. `initialize_adventure_state(uuid)` in `src/game_workflows/game.py:63-64` to load pickled chat history and character lists.
* **Verification Target:** Pickle loader consumer identification.

### Q05: Who calls `delete_history_file()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='delete_history_file', direction='incoming')`
* **Ground Truth Solution:**
  `delete_history_file()` (`loaders.py:72-91`) is called by:
  1. `display_adventure_list()` in `src/game_workflows/game.py:57` when the player clicks the trash icon.
* **Verification Target:** UI callback edge resolution.

### Q06: Which functions invoke `update_history_ids()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='update_history_ids', direction='incoming')`
* **Ground Truth Solution:**
  `update_history_ids()` (`loaders.py:65-69`) is called by:
  1. `delete_history_file(uuid)` in `src/game_workflows/loaders.py:88` after unlinking files from disk.
* **Verification Target:** Intra-file caller resolution within `loaders.py`.

### Q07: Where in the codebase is `create_character_form()` called?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='create_character_form', direction='incoming')`
* **Ground Truth Solution:**
  `create_character_form()` (`player.py:14`) is called by:
  1. `play_game()` in `src/game_workflows/game.py:35` when `st.session_state.character_creation` is True.
* **Verification Target:** State-guarded UI caller resolution.

### Q08: What functions call `start_adventure()` in `src/game_workflows/core.py`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='start_adventure', direction='incoming', file_path='src/game_workflows/core.py')`
* **Ground Truth Solution:**
  Called by `play_game()` in `src/game_workflows/game.py:38` and `initialize_adventure_state()` / continue adventure button (`game.py:54`).
* **Verification Target:** Disambiguating `core.py:start_adventure` from `call_api.py:start_adventure`.

### Q09: Who calls `play_game()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='play_game', direction='incoming')`
* **Ground Truth Solution:**
  `play_game()` (`game.py:16`) is called by:
  1. `main()` in `main.py:50` when the radio button selection is `"Play Game"`.
* **Verification Target:** Root entry-point edge from `main.py`.

### Q10: Which functions invoke `display_adventure_list()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='display_adventure_list', direction='incoming')`
* **Ground Truth Solution:**
  `display_adventure_list()` (`game.py:41`) is called by:
  1. `main()` in `main.py:53`.
* **Verification Target:** Sidebar listing entry point.

### Q11: Where is `display_character_list()` called?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='display_character_list', direction='incoming')`
* **Ground Truth Solution:**
  `display_character_list()` (`player.py`) is called by:
  1. `main()` in `main.py:52`.
* **Verification Target:** Root UI layout sequence.

### Q12: Who calls `initialize_adventure_state()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='initialize_adventure_state', direction='incoming')`
* **Ground Truth Solution:**
  Called by `display_adventure_list()` in `src/game_workflows/game.py:53` when the user clicks `"continue adventure"`.
* **Verification Target:** Button handler invocation path.

### Q13: What functions trigger `reset_old_games()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='reset_old_games', direction='incoming')`
* **Ground Truth Solution:**
  Called by `play_game()` in `src/game_workflows/game.py:30` when the player clicks `"Start Adventure"`.
* **Verification Target:** State sanitization trigger identification.

### Q14: Who calls `check_ollama_availability()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='check_ollama_availability', direction='incoming')`
* **Ground Truth Solution:**
  `check_ollama_availability()` (`src/utils.py:12`) is called by:
  1. `display_updated_status_sidebar()` in `main.py:29`
  2. `test_model_availability()` in `src/utils.py:22`
* **Verification Target:** Utility check reuse across `main.py` and `utils.py`.

### Q15: What are the incoming callers of `test_model_availability()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='test_model_availability', direction='incoming')`
* **Ground Truth Solution:**
  Called by `main()` in `main.py:44` on every page refresh before navigation logic.
* **Verification Target:** Pre-flight sanity check hook.

### Q16: Where is `manage_models()` invoked?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='manage_models', direction='incoming')`
* **Ground Truth Solution:**
  Called by `main()` in `main.py:56` when navigation tab is set to `"Manage Models"`.
* **Verification Target:** Top-level tab dispatch.

### Q17: Who calls `set_fantasy_theme()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='set_fantasy_theme', direction='incoming')`
* **Ground Truth Solution:**
  Called by `main()` in `main.py:38` at the very start of page rendering.
* **Verification Target:** CSS injection hook point.

### Q18: Who calls `initialize_rag()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='initialize_rag', direction='incoming')`
* **Ground Truth Solution:**
  Called by `manage_models()` in `src/imports/model.py:67` when clicking `"Save Model Selections"`.
* **Verification Target:** Cached resource factory invocation.

### Q19: What functions invoke `initialize_history()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='initialize_history', direction='incoming')`
* **Ground Truth Solution:**
  Called by `manage_models()` in `src/imports/model.py:68` when clicking `"Save Model Selections"`.
* **Verification Target:** ChromaDB history store factory call.

### Q20: What is the full upstream call chain that leads to `load_characters()` starting from `main()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='load_characters', direction='incoming', max_depth=3)`
* **Ground Truth Solution:**
  Two primary chains from `main()`:
  1. `main.py:main()` $\rightarrow$ `main.py:display_character_list()` $\rightarrow$ `player.py:load_characters()`
  2. `main.py:main()` $\rightarrow$ `game.py:play_game()` $\rightarrow$ `core.py:start_adventure()` $\rightarrow$ `loaders.py:load_characters()`
* **Verification Target:** Multi-hop call path reconstruction.

---

## Category 2: Downstream Callees & Execution Trees

### Q21: What functions does `main()` in `main.py` call directly?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='main', direction='outgoing')`
* **Ground Truth Solution:**
  `set_fantasy_theme()`, `display_updated_status_sidebar()`, `test_model_availability()`, `play_game()`, `display_character_list()`, `display_adventure_list()`, `manage_models()`.
* **Verification Target:** High-level router outgoing fan-out.

### Q22: What does `play_game()` in `src/game_workflows/game.py` invoke?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='play_game', direction='outgoing')`
* **Ground Truth Solution:**
  `initialize_session_state()` (in `game.py`), `reset_old_games()`, `create_character_form()`, `start_adventure()`.
* **Verification Target:** Workflow state branching.

### Q23: What functions does `start_adventure()` in `src/game_workflows/core.py` call?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='start_adventure', direction='outgoing')`
* **Ground Truth Solution:**
  `initialise_adventure_session_state()`, `load_characters()`, `api.start_adventure()`, `api.name_adventure()`, `api.save_doc_to_history_vector()`, `save_adventure()`.
* **Verification Target:** Orchestration pipeline fan-out.

### Q24: What outgoing calls are made by `create_character_form()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='create_character_form', direction='outgoing')`
* **Ground Truth Solution:**
  Inner functions: `initialize_session_state()`, `calculate_points_spent()`, `update_ability_score()`, `reset_character_form()`; external: `save_characters()`.
* **Verification Target:** Nested lexical closures vs external imports.

### Q25: What downstream functions are executed by `load_adventure()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='load_adventure', direction='outgoing')`
* **Ground Truth Solution:**
  `os.path.join()`, `os.path.exists()`, `open()`, `pickle.load()`.
* **Verification Target:** Standard library I/O leaf calls.

### Q26: What functions are called inside `delete_history_file()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='delete_history_file', direction='outgoing')`
* **Ground Truth Solution:**
  `st.session_state.history_store.get()`, `st.session_state.history_store.delete()`, `os.path.exists()`, `os.remove()`, `update_history_ids()`.
* **Verification Target:** Vector deletion + File unlink coordination.

### Q27: What outgoing calls are initiated by `display_adventure_list()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='display_adventure_list', direction='outgoing')`
* **Ground Truth Solution:**
  `load_available_adventures()`, `initialize_adventure_state()`, `start_adventure()`, `delete_history_file()`.
* **Verification Target:** Adventure card click callbacks.

### Q28: What does `initialize_adventure_state()` invoke?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='initialize_adventure_state', direction='outgoing')`
* **Ground Truth Solution:**
  `load_adventure(uuid)` and `st.rerun()`.
* **Verification Target:** State restore + rerun loop.

### Q29: What functions does `manage_models()` call?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='manage_models', direction='outgoing')`
* **Ground Truth Solution:**
  `list_ollama_models()`, `OllamaApi()`, `HuggingFaceEmbeddings()`, `initialize_rag()`, `initialize_history()`.
* **Verification Target:** Model setup side effects.

### Q30: What downstream functions does `test_model_availability()` call?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='test_model_availability', direction='outgoing')`
* **Ground Truth Solution:**
  `check_ollama_availability()`, `st.error()`, `st.info()`, `st.button()`, `st.rerun()`.
* **Verification Target:** Error boundary branching.

### Q31: What calls are made inside `check_ollama_availability()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='check_ollama_availability', direction='outgoing')`
* **Ground Truth Solution:**
  `requests.get()` to `/api/version`.
* **Verification Target:** HTTP request leaf node.

### Q32: What outgoing calls does `OllamaApi.start_adventure()` make?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='start_adventure', direction='outgoing')`
* **Ground Truth Solution:**
  `ChatPromptTemplate.from_template()`, `load_characters()`, `chain.stream()`.
* **Verification Target:** LangChain LCEL streaming pipe.

### Q33: What does `OllamaApi.progress_story()` call during its execution?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='progress_story', direction='outgoing')`
* **Ground Truth Solution:**
  `get_history()`, `embedding_model.embed_query()`, `history_store.similarity_search_by_vector_with_relevance_scores()`, `ChatPromptTemplate.from_messages()`, `chain.stream()`.
* **Verification Target:** Historical RAG retrieval loop.

### Q34: What downstream functions are executed inside `dm_turn()` in `adventure.py`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='dm_turn', direction='outgoing')`
* **Ground Truth Solution:**
  `vector_store.similarity_search()`, `api_call()`.
* **Verification Target:** Standalone module callee resolution.

### Q35: What functions are called by `start_new_adventure()` in `adventure.py`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='start_new_adventure', direction='outgoing')`
* **Ground Truth Solution:**
  `api_call()`.
* **Verification Target:** Leaf test for orphan module.

### Q36: What outgoing functions does `save_adventure()` call?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='save_adventure', direction='outgoing')`
* **Ground Truth Solution:**
  `os.makedirs()`, `os.path.join()`, `open()`, `pickle.dump()`, `json.dump()`.
* **Verification Target:** File serialization leaf operations.

### Q37: What calls are made inside `display_updated_status_sidebar()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='display_updated_status_sidebar', direction='outgoing')`
* **Ground Truth Solution:**
  `check_ollama_availability()`, `system_status.write()`, `ollama_placeholder.write()`, `model_placeholder.write()`, `rag_placeholder.write()`.
* **Verification Target:** Streamlit placeholder update sequence.

### Q38: What does `initialise_adventure_session_state()` call?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='initialise_adventure_session_state', direction='outgoing')`
* **Ground Truth Solution:**
  No external function calls; only reads and initializes keys on `st.session_state`.
* **Verification Target:** Pure state mutating leaf node.

### Q39: What functions does `reset_old_games()` invoke?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='reset_old_games', direction='outgoing')`
* **Ground Truth Solution:**
  No function calls; executes `del` statements on `st.session_state` keys.
* **Verification Target:** Dictionary key deletion leaf node.

### Q40: What LangChain library functions are called by `OllamaApi.__init__()`?
* **Tool Chain:** `tool_traverse_call_graph(target_symbol='__init__', direction='outgoing')`
* **Ground Truth Solution:**
  `OllamaLLM(model=model, temperature=temperature)` and `RecursiveCharacterTextSplitter(chunk_size=1100, chunk_overlap=100)`.
* **Verification Target:** Library constructor call detection.

---

## Category 3: Blast Radius & Impact Analysis

### Q41: What will break if I modify `load_characters()` in `loaders.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='load_characters')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/player.py`, `src/game_workflows/core.py`, `src/api_workflows/call_api.py`, `main.py`.
  - **Downstream Impact:** Hero selection sidebar (`display_character_list`), hero picking in `start_adventure`, and DM prompt formatting in `OllamaApi.start_adventure`.
* **Verification Target:** Core data loader transitive blast radius.

### Q42: What is the blast radius of changing `save_characters()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='save_characters')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/player.py`, `src/game_workflows/game.py`.
  - **Downstream Impact:** Character persistence upon form submission in `create_character_form()`.
* **Verification Target:** Form persistence impact.

### Q43: What is the ripple effect if I alter `save_adventure()` in `loaders.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='save_adventure')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/core.py`, `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** Campaign saving in `core.py:start_adventure()`.
* **Verification Target:** Adventure persistence blast radius.

### Q44: What breaks if I change the signature of `load_adventure()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='load_adventure')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** `initialize_adventure_state(uuid)` and the `"continue adventure"` button callback.
* **Verification Target:** Campaign resumption pipeline impact.

### Q45: What is the impact of modifying `create_character_form()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='create_character_form')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** `play_game()` character creation view.
* **Verification Target:** Sub-screen UI blast radius.

### Q46: What will happen across the system if I modify `start_adventure()` in `core.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='start_adventure')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** Game screen navigation when clicking `"Start Adventure"` or resuming a campaign.
* **Verification Target:** Major game loop impact analysis.

### Q47: What is the blast radius of modifying `OllamaApi.start_adventure()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='start_adventure')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/core.py`, `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** Initial AI narrative generation and streaming world intro.
* **Verification Target:** API generator downstream blast radius.

### Q48: What is the blast radius of modifying `OllamaApi.progress_story()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='progress_story')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/core.py`.
  - **Downstream Impact:** Chat form submission handler in `core.py:start_adventure()`.
* **Verification Target:** Turn progression impact.

### Q49: What will break if I modify `check_ollama_availability()` in `utils.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='check_ollama_availability')`
* **Ground Truth Solution:**
  - **Affected Files:** `main.py`, `src/utils.py`.
  - **Downstream Impact:** Sidebar status reporting and pre-flight check in `test_model_availability()`.
* **Verification Target:** Health check infrastructure impact.

### Q50: What is the system-wide impact of changing `manage_models()` in `model.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='manage_models')`
* **Ground Truth Solution:**
  - **Affected Files:** `main.py`.
  - **Downstream Impact:** Model selection tab in Streamlit.
* **Verification Target:** Configuration view impact.

### Q51: What breaks if I modify `initialize_rag()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='initialize_rag')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/imports/model.py`, `main.py`.
  - **Downstream Impact:** Setting `st.session_state.vector_store` (5e handbook retrieval).
* **Verification Target:** ChromaDB RAG factory impact.

### Q52: What is the blast radius of changing `initialize_history()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='initialize_history')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/imports/model.py`, `main.py`.
  - **Downstream Impact:** Setting `st.session_state.history_store`.
* **Verification Target:** ChromaDB history store factory impact.

### Q53: What will break if I modify `set_fantasy_theme()` in `theme.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='set_fantasy_theme')`
* **Ground Truth Solution:**
  - **Affected Files:** `main.py`.
  - **Downstream Impact:** Only the global CSS styling; no functional game mechanics break.
* **Verification Target:** Pure cosmetic blast radius.

### Q54: What is the impact of modifying `delete_history_file()`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='delete_history_file')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** Adventure deletion button in sidebar.
* **Verification Target:** Campaign deletion lifecycle.

### Q55: What breaks if I change `play_game()` in `game.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='play_game')`
* **Ground Truth Solution:**
  - **Affected Files:** `main.py`.
  - **Downstream Impact:** The primary game screen tab.
* **Verification Target:** Screen controller blast radius.

### Q56: What is the combined blast radius of modifying both `load_characters` and `save_characters`?
* **Tool Chain:** `tool_calculate_blast_radius(changed_symbols=['load_characters', 'save_characters'])`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/loaders.py`, `src/game_workflows/player.py`, `src/game_workflows/core.py`, `src/api_workflows/call_api.py`, `src/game_workflows/game.py`, `main.py`.
  - **Downstream Impact:** Complete character lifecycle from creation to adventure execution.
* **Verification Target:** Multi-symbol composite blast radius.

### Q57: What is the blast radius of modifying the constant dictionary `weapon_dict` in `references.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='weapon_dict')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/player.py`.
  - **Downstream Impact:** Weapon multiselect box in `create_character_form()`.
* **Verification Target:** Static reference dictionary impact.

### Q58: What is the blast radius of changing `armor_dict` in `references.py`?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='armor_dict')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/game_workflows/player.py`.
  - **Downstream Impact:** Armor selectbox in `create_character_form()`.
* **Verification Target:** Static reference dictionary impact.

### Q59: If I modify `start_new_adventure()` in `adventure.py`, what breaks in the active app?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='start_new_adventure')`
* **Ground Truth Solution:**
  - **Affected Symbols:** 1 (`start_new_adventure` itself).
  - **Incoming Callers:** 0.
  - **Impact:** Nothing breaks in the active app because `adventure.py` is an unreferenced orphan module.
* **Verification Target:** Zero-caller orphan blast radius verification.

### Q60: What is the blast radius if I refactor the `OllamaApi` class constructor?
* **Tool Chain:** `tool_calculate_blast_radius(target_symbol='OllamaApi')`
* **Ground Truth Solution:**
  - **Affected Files:** `src/imports/model.py`, `main.py`.
  - **Downstream Impact:** `manage_models()` where `st.session_state.api = OllamaApi(model=dm_model)` is created.
* **Verification Target:** Class instantiation blast radius.

---

## Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)

### Q61: What is the point cost for an ability score of 15 in `calculate_point_cost`?
* **Tool Chain:**
  1. `tool_get_symbol_code_snippet(symbol_name='calculate_point_cost')` $\rightarrow$ 0 results
  2. Evaluator triggers **Case B** $\rightarrow$ Sibling retry: `tool_search_codebase_semantic("calculate_point_cost")`
  3. Matches `calculate_points_spent(score)` in `src/game_workflows/player.py:24-26`
* **Ground Truth Solution:**
  Function is actually named `calculate_points_spent(score)`. Formula is `return score - 8`. For 15: $15 - 8 = \mathbf{7\text{ points}}$.
* **Verification Target:** Case B recovery from typo in function name.

### Q62: Who calls `load_character()` in the codebase?
* **Tool Chain:**
  1. `tool_traverse_call_graph(target_symbol='load_character')` $\rightarrow$ 0 callers
  2. Evaluator Case B $\rightarrow$ Semantic search finds `load_characters`
  3. Resolves callers of `load_characters`
* **Ground Truth Solution:**
  Function name is plural: `load_characters()`. Callers: `player.py:display_character_list`, `core.py:start_adventure`, and `call_api.py:OllamaApi.start_adventure`.
* **Verification Target:** Singular vs plural symbol typo recovery.

### Q63: Where is `check_ollama_status` defined and what does it check?
* **Tool Chain:**
  1. Snippet for `check_ollama_status` $\rightarrow$ 0 results
  2. Case B Fallback finds `check_ollama_availability` in `src/utils.py:12`
* **Ground Truth Solution:**
  Real function is `check_ollama_availability()`. It checks if Ollama is running by querying `http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/version` with a 5s timeout.
* **Verification Target:** Semantic synonym typo recovery (`status` vs `availability`).

### Q64: What does `save_character()` do?
* **Tool Chain:**
  1. Snippet lookup fails
  2. Case B Fallback resolves `save_characters(characters)` in `src/game_workflows/loaders.py:19`
* **Ground Truth Solution:**
  Real function is `save_characters(characters)`. It dumps the characters dictionary to `characters.json` with `indent=4`.
* **Verification Target:** Singular vs plural write function recovery.

### Q65: What parameters are required for `load_adventure_file`?
* **Tool Chain:**
  1. Lookup fails $\rightarrow$ Case B resolves `load_adventure(uuid)` in `loaders.py:24`
* **Ground Truth Solution:**
  Real function is `load_adventure(uuid)`. Requires a single parameter `uuid: str`.
* **Verification Target:** Suffix mismatch recovery (`_file` suffix).

### Q66: Show me the implementation of `delete_history` in `loaders.py`.
* **Tool Chain:**
  1. Lookup fails $\rightarrow$ Case B resolves `delete_history_file(uuid)` in `loaders.py:72`
* **Ground Truth Solution:**
  Real function is `delete_history_file(uuid)`. Deletes adventure from `st.session_state['adventure_dict']`, removes embeddings from `history_store`, and deletes `{uuid}.pkl` and `{uuid}_char.pkl`.
* **Verification Target:** Truncated function name recovery.

### Q67: Where is `reset_game()` called?
* **Tool Chain:**
  1. Call graph fails $\rightarrow$ Case B resolves `reset_old_games()` in `src/game_workflows/game.py:70`
* **Ground Truth Solution:**
  Real function is `reset_old_games()`. Called by `play_game()` in `src/game_workflows/game.py:30`.
* **Verification Target:** Verb-noun mismatch recovery (`reset_game` vs `reset_old_games`).

### Q68: What does `initialize_theme()` do?
* **Tool Chain:**
  1. Snippet fails $\rightarrow$ Case B resolves `set_fantasy_theme()` in `src/ui/theme.py:4`
* **Ground Truth Solution:**
  Real function is `set_fantasy_theme()`. Injects custom Google Fonts ('Cinzel') and parchment CSS styling into Streamlit via `st.markdown(..., unsafe_allow_html=True)`.
* **Verification Target:** Semantic action mismatch (`initialize` vs `set`).

### Q69: Where is `initialise_adventure_state` defined?
* **Tool Chain:**
  1. Lookup fails $\rightarrow$ Case B resolves `initialise_adventure_session_state()` in `core.py:15` or `initialize_adventure_state(uuid)` in `game.py:62`
* **Ground Truth Solution:**
  Two near matches: `initialise_adventure_session_state()` in `core.py` (British spelling) and `initialize_adventure_state(uuid)` in `game.py` (American spelling).
* **Verification Target:** Disambiguating regional spelling variations (`initialise` vs `initialize`).

### Q70: What does `fetch_available_adventures` return?
* **Tool Chain:**
  1. Lookup fails $\rightarrow$ Case B resolves `load_available_adventures()` in `loaders.py:39`
* **Ground Truth Solution:**
  Real function is `load_available_adventures()`. Reads and returns `history_ids.json` as a dictionary, or `{}` if missing.
* **Verification Target:** Synonym action recovery (`fetch` vs `load`).

### Q71: What is the timeout value in `verify_ollama`?
* **Tool Chain:**
  1. Snippet fails $\rightarrow$ Case B resolves `check_ollama_availability` in `utils.py:15`
* **Ground Truth Solution:**
  Real function is `check_ollama_availability()`. Timeout is `timeout=5` seconds.
* **Verification Target:** Conceptual function lookup to extract parameter value.

### Q72: What does `update_history()` in `loaders.py` update?
* **Tool Chain:**
  1. Lookup fails $\rightarrow$ Case B resolves `update_history_ids()` in `loaders.py:65`
* **Ground Truth Solution:**
  Real function is `update_history_ids()`. Dumps `st.session_state['adventure_dict']` into `history_ids.json`.
* **Verification Target:** Near-miss suffix recovery.

### Q73: What is the chunk size in `OllamaApi` text splitter?
* **Tool Chain:**
  1. Snippet for `OllamaApi.__init__` in `call_api.py:18`
* **Ground Truth Solution:**
  `chunk_size=1100`, `chunk_overlap=100` in `RecursiveCharacterTextSplitter`.
* **Verification Target:** Inner attribute value extraction.

### Q74: Where is `CHARACTER_FILE_PATH` defined?
* **Tool Chain:**
  1. Env var query fails $\rightarrow$ Case B resolves `CHARACTERS_FILE` in `loaders.py:8`
* **Ground Truth Solution:**
  Real variable is `CHARACTERS_FILE = os.getenv("CHARACTERS_FILE", "characters.json")`.
* **Verification Target:** Environment variable typo recovery.

### Q75: What is the default value of `TOTAL_POINTS` in character creation?
* **Tool Chain:**
  1. State query fails $\rightarrow$ Case B resolves `TOTAL_SKILL_POINTS` in `player.py:11`
* **Ground Truth Solution:**
  Real variable is `TOTAL_SKILL_POINTS = int(os.getenv('TOTAL_MAX_POINTS_AT_START', 27))`. Default is **27**.
* **Verification Target:** Near-miss global variable resolution.

### Q76: What does `format_adventure_name` do?
* **Tool Chain:**
  1. Snippet fails $\rightarrow$ Case B resolves `name_adventure` in `call_api.py:57`
* **Ground Truth Solution:**
  Real function is `name_adventure(adventure: str)`. Prompts Ollama to generate a creative title without quotes.
* **Verification Target:** Verb-noun near-miss mapping.

### Q77: What does `save_vector_doc` in `call_api.py` do?
* **Tool Chain:**
  1. Snippet fails $\rightarrow$ Case B resolves `save_doc_to_history_vector` in `call_api.py`
* **Ground Truth Solution:**
  Real method is `save_doc_to_history_vector(document: Document)`; adds document to `st.session_state.history_store`.
* **Verification Target:** Method name truncation recovery.

### Q78: Where is `weapon_dictionary` defined?
* **Tool Chain:**
  1. Variable query fails $\rightarrow$ Case B resolves `weapon_dict` in `references.py:1`
* **Ground Truth Solution:**
  Real variable is `weapon_dict = {...}` in `src/game_workflows/references.py`.
* **Verification Target:** Dictionary name abbreviation recovery.

### Q79: Where is `armor_list` defined?
* **Tool Chain:**
  1. Variable query fails $\rightarrow$ Case B resolves `armor_dict` in `references.py:46`
* **Ground Truth Solution:**
  Real variable is `armor_dict = {...}` in `src/game_workflows/references.py`.
* **Verification Target:** Data structure type typo recovery (`list` vs `dict`).

### Q80: What is the return value of `get_points_spent`?
* **Tool Chain:**
  1. Snippet fails $\rightarrow$ Case B resolves `calculate_points_spent(score)` in `player.py:24`
* **Ground Truth Solution:**
  Real function is `calculate_points_spent(score)`. Returns `score - 8`.
* **Verification Target:** Near-miss arithmetic function recovery.

---

## Category 5: State & Variable Reference Audits

### Q81: Where is `st.session_state.ability_scores` read and updated?
* **Ground Truth Solution:**
  In `src/game_workflows/player.py`: initialized to 8 for all 6 stats in `initialize_session_state()`, read in `create_character_form()` to populate `st.number_input`, and mutated in `update_ability_score()`.
* **Verification Target:** AST `STATE_READS` / `STATE_WRITES` edges.

### Q82: Which functions mutate `st.session_state.remaining_points`?
* **Ground Truth Solution:**
  In `src/game_workflows/player.py`: initialized in `initialize_session_state()` (`= TOTAL_SKILL_POINTS`), reset in `reset_character_form()`, and mutated in `update_ability_score()` via `remaining_points += old_points - new_points`.
* **Verification Target:** State delta mutation tracking.

### Q83: Where in the codebase is `st.session_state.dm_model` initialized and read?
* **Ground Truth Solution:**
  Initialized in `src/imports/model.py:62` (`manage_models`); read in `src/game_workflows/game.py:17` (`play_game`) and `main.py:32` (`display_updated_status_sidebar`).
* **Verification Target:** Cross-file session state propagation.

### Q84: What functions access `st.session_state.vector_store`?
* **Ground Truth Solution:**
  Initialized in `model.py:67` (`manage_models`); read in `game.py:17` (`play_game`), `main.py:34`, and `adventure.py:17` (`dm_turn`).
* **Verification Target:** Vector store reference mapping.

### Q85: Which functions reference or mutate `st.session_state.history_store`?
* **Ground Truth Solution:**
  Initialized in `model.py:68`; read in `game.py:17`, `loaders.py:77` (`delete_history_file`), and `call_api.py:81` (`progress_story`).
* **Verification Target:** History vector store audit.

### Q86: Where is `st.session_state.chat_history` modified?
* **Ground Truth Solution:**
  Initialized in `core.py:19`; appended to in `core.py:65` (narrator system message) and `core.py:130` (user/AI turns); deleted in `game.py:74` (`reset_old_games`).
* **Verification Target:** Conversation history mutation sites.

### Q87: What functions read or write `st.session_state.characters_in_adventure`?
* **Ground Truth Solution:**
  Initialized in `core.py:23`; assigned from `st.multiselect` in `core.py:36`; passed to `save_adventure()` in `core.py:76`; deleted in `game.py:76`.
* **Verification Target:** Multi-hero session state audit.

### Q88: Where is `st.session_state.adventure_dict` modified?
* **Ground Truth Solution:**
  Initialized in `core.py:21`; populated in `game.py:43` via `load_available_adventures()`; updated in `core.py:63` on new adventure; unlinked in `loaders.py:73` on delete.
* **Verification Target:** Persistent adventure index dictionary tracking.

### Q89: Which functions read or write `st.session_state.has_adventure_started`?
* **Ground Truth Solution:**
  Initialized in `core.py:17` (`False`); set to `True` in `core.py:54` and `game.py:65`; deleted in `game.py:72` (`reset_old_games`).
* **Verification Target:** Adventure lifecycle boolean flag.

### Q90: Where is `st.session_state.current_uuid` set and read?
* **Ground Truth Solution:**
  Set to `str(uuid4())` in `core.py:61` and loaded from saved adventure in `game.py:66`; read in `core.py:69` and `call_api.py:86` as metadata filter for ChromaDB.
* **Verification Target:** Session UUID lifecycle.

### Q91: What functions read or mutate `st.session_state.character_creation`?
* **Ground Truth Solution:**
  Initialized in `game.py:10`; set to `True` when clicking `"Create a Character"` (`game.py:27`); set to `False` on `"Start Adventure"` (`game.py:31`).
* **Verification Target:** View toggle flag audit.

### Q92: Where is `st.session_state.character_created` used?
* **Ground Truth Solution:**
  Initialized in `player.py:17` (`False`). Not referenced elsewhere (orphan flag).
* **Verification Target:** Dead state variable detection.

### Q93: What files and functions reference `st.session_state.game_state`?
* **Ground Truth Solution:**
  Initialized in `game.py:13` (`{"state": False}`); set to `False` on character creation (`game.py:26`); set to `True` on start adventure (`game.py:32`); checked in `game.py:37`.
* **Verification Target:** State dictionary references.

### Q94: Where is `st.session_state.page` set and checked?
* **Ground Truth Solution:**
  Set by `st.sidebar.radio("Navigation", ...)` in `main.py:46`; checked in `main.py:49` (`"Play Game"`) and `main.py:55` (`"Manage Models"`).
* **Verification Target:** Main router state flag.

### Q95: What functions read or write `st.session_state.api`?
* **Ground Truth Solution:**
  Instantiated in `model.py:63` (`st.session_state.api = OllamaApi(model=dm_model)`); invoked in `core.py:51` (`api.start_adventure`), `core.py:57`, `core.py:71`, and `core.py:121` (`api.progress_story`).
* **Verification Target:** Class instance session reference.

### Q96: Which methods read `st.session_state.embedding_model`?
* **Ground Truth Solution:**
  Instantiated in `model.py:65` (`HuggingFaceEmbeddings`); passed to `Chroma` in `model.py:22` (`initialize_rag`) and `model.py:29` (`initialize_history`); used in `call_api.py:82` (`embed_query`).
* **Verification Target:** Embedder instance reference audit.

### Q97: Where is `TOTAL_SKILL_POINTS` declared and where is it referenced?
* **Ground Truth Solution:**
  Declared in `src/game_workflows/player.py:11`; referenced in `player.py:22` (`remaining_points = TOTAL_SKILL_POINTS`) and `player.py:41` (`reset_character_form`).
* **Verification Target:** Module constant reference tracking.

### Q98: What files access the global variable `TURN_LIMIT`?
* **Ground Truth Solution:**
  Declared in `main.py:24` (`int(os.getenv('TURN_LIMIT', 10))`) and in `src/game_workflows/core.py:12` (`int(os.getenv('TURN_LIMIT', 10))`).
* **Verification Target:** Duplicate constant declaration across files.

### Q99: Where is `OLLAMA_API_ENDPOINT` referenced across the codebase?
* **Ground Truth Solution:**
  Declared in `main.py:22`, `src/utils.py:9`, and `src/imports/model.py:13`. Used in `utils.py:14` (`/api/version`) and `model.py:37` (`/api/tags`).
* **Verification Target:** Constant URL usage audit.

### Q100: Which functions read `CHARACTERS_FILE`?
* **Ground Truth Solution:**
  Declared in `src/game_workflows/loaders.py:8`; read in `loaders.py:13` (`load_characters`) and `loaders.py:20` (`save_characters`).
* **Verification Target:** File path constant reference tracking.

### Q101: What default value does `ability_scores` take when a character form is opened?
* **Ground Truth Solution:**
  `8` for all 6 abilities: Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma (`player.py:19`).
* **Verification Target:** AST dictionary comprehension audit.

### Q102: What is the maximum value permitted for an ability score in `create_character_form`?
* **Ground Truth Solution:**
  `max_value=15` in `st.number_input` (`player.py:74`).
* **Verification Target:** AST widget argument extraction.

### Q103: What is the minimum value permitted for an ability score in `create_character_form`?
* **Ground Truth Solution:**
  `min_value=8` in `st.number_input` (`player.py:73`).
* **Verification Target:** AST widget argument extraction.

### Q104: What races can a player select in `create_character_form`?
* **Ground Truth Solution:**
  `["Human", "Elf", "Dwarf", "Halfling", "Gnome", "Half-Orc", "Tiefling"]` (`player.py:53`).
* **Verification Target:** AST list extraction.

### Q105: What character classes are available in `create_character_form`?
* **Ground Truth Solution:**
  `["Fighter", "Wizard", "Rogue", "Cleric", "Paladin", "Ranger", "Barbarian"]` (`player.py:56`).
* **Verification Target:** AST list extraction.

---

## Category 6: Environment Variables & Configuration Audits

### Q106: Where is `OLLAMA_HOST` read, and what is its default value?
* **Ground Truth Solution:**
  Read via `os.getenv('OLLAMA_HOST', 'localhost')` in `main.py:20`, `src/utils.py:7`, and `src/imports/model.py:11`. Default is `'localhost'`.
* **Verification Target:** Cross-file env var consistency.

### Q107: Which files access the environment variable `OLLAMA_PORT`?
* **Ground Truth Solution:**
  `main.py:21`, `src/utils.py:8`, and `src/imports/model.py:12`. Default is `'11434'`.
* **Verification Target:** Env var audit.

### Q108: What files and functions read `CHARACTERS_FILE` via `os.getenv`?
* **Ground Truth Solution:**
  `src/game_workflows/loaders.py:8` (`os.getenv("CHARACTERS_FILE", "characters.json")`).
* **Verification Target:** Storage configuration audit.

### Q109: Where is `HISTORY_DB_DIR` read in the repository?
* **Ground Truth Solution:**
  Read in `src/game_workflows/loaders.py:9` and `src/imports/model.py:16`. Default is `'./history'`.
* **Verification Target:** History storage env var audit.

### Q110: Which file reads `CHROMA_DB_DIR` and what is its default fallback directory?
* **Ground Truth Solution:**
  `src/imports/model.py:15` (`os.getenv('CHROMA_DB_DIR', './5e_dnd_chroma_langchain_db')`). Default is `'./5e_dnd_chroma_langchain_db'`.
* **Verification Target:** Vector DB directory configuration.

### Q111: Where is `TURN_LIMIT` loaded from the environment, and what is its fallback value?
* **Ground Truth Solution:**
  `main.py:24` and `src/game_workflows/core.py:12`. Fallback is `10`.
* **Verification Target:** Integer cast env var audit.

### Q112: Which function reads `TOTAL_MAX_POINTS_AT_START` from the environment?
* **Ground Truth Solution:**
  `src/game_workflows/player.py:11` (`int(os.getenv('TOTAL_MAX_POINTS_AT_START', 27))`). Default is `27`.
* **Verification Target:** Point buy limit configuration.

### Q113: Are there any API keys or tokens read from `.env` in this codebase?
* **Ground Truth Solution:**
  No. The application relies on local Ollama and local HuggingFace embeddings; no external cloud API keys (OpenAI, Gemini, Anthropic) are read in `dnd`.
* **Verification Target:** Negative security finding.

### Q114: Are there any hardcoded secret strings or tokens in the codebase?
* **Ground Truth Solution:**
  No hardcoded secrets or passwords found.
* **Verification Target:** Secret scanning audit.

### Q115: What environment variables are loaded in `src/game_workflows/loaders.py`?
* **Ground Truth Solution:**
  `CHARACTERS_FILE` (default `"characters.json"`) and `HISTORY_DB_DIR` (default `"./history"`).
* **Verification Target:** File-scoped env var list.

### Q116: What environment variables are referenced in `src/game_workflows/player.py`?
* **Ground Truth Solution:**
  `TOTAL_MAX_POINTS_AT_START` (default `27`).
* **Verification Target:** File-scoped env var list.

### Q117: What environment variables does `main.py` read?
* **Ground Truth Solution:**
  `OLLAMA_HOST` (`localhost`), `OLLAMA_PORT` (`11434`), and `TURN_LIMIT` (`10`).
* **Verification Target:** Main module env var list.

### Q118: What environment variables are accessed in `src/imports/model.py`?
* **Ground Truth Solution:**
  `OLLAMA_HOST`, `OLLAMA_PORT`, `CHROMA_DB_DIR`, and `HISTORY_DB_DIR`.
* **Verification Target:** Model setup module env var list.

### Q119: What environment variables are read in `src/utils.py`?
* **Ground Truth Solution:**
  `OLLAMA_HOST` and `OLLAMA_PORT`.
* **Verification Target:** Utility module env var list.

### Q120: Does `core.py` read any environment variables directly?
* **Ground Truth Solution:**
  Yes, `TURN_LIMIT = int(os.getenv('TURN_LIMIT', 10))` in line 12.
* **Verification Target:** Verification of direct vs imported variables.

### Q121: What happens if `TOTAL_MAX_POINTS_AT_START` is missing from the environment?
* **Ground Truth Solution:**
  It falls back to integer `27` without throwing an error.
* **Verification Target:** Fallback verification.

### Q122: What happens if `OLLAMA_PORT` is not configured in the `.env` file?
* **Ground Truth Solution:**
  It falls back to string `"11434"`.
* **Verification Target:** Fallback verification.

### Q123: What default path is used if `HISTORY_DB_DIR` is not provided?
* **Ground Truth Solution:**
  `"./history"`.
* **Verification Target:** Fallback path verification.

### Q124: What default model path is used if `CHROMA_DB_DIR` is not set?
* **Ground Truth Solution:**
  `"./5e_dnd_chroma_langchain_db"`.
* **Verification Target:** Fallback path verification.

### Q125: List every distinct environment variable read across the entire project.
* **Ground Truth Solution:**
  Total 6 distinct variables: `OLLAMA_HOST`, `OLLAMA_PORT`, `CHARACTERS_FILE`, `HISTORY_DB_DIR`, `CHROMA_DB_DIR`, `TOTAL_MAX_POINTS_AT_START`, `TURN_LIMIT`.
* **Verification Target:** Project-wide deduplicated configuration audit.

---

## Category 7: Exact AST Definitions & Inner Closures

### Q126: What is the exact implementation of `calculate_points_spent`?
* **Ground Truth Solution:**
  ```python
  def calculate_points_spent(score):
      # Point buy system calculation
      return score - 8
  ```
  Defined in `src/game_workflows/player.py:24-26`.
* **Verification Target:** Inner closure snippet extraction.

### Q127: Show the complete code definition of `update_ability_score`.
* **Ground Truth Solution:**
  ```python
  def update_ability_score(ability):
      old_score = st.session_state.ability_scores[ability]
      new_score = st.session_state[f"ability_{ability}"]

      old_points = calculate_points_spent(old_score)
      new_points = calculate_points_spent(new_score)

      st.session_state.ability_scores[ability] = new_score
      st.session_state.remaining_points += old_points - new_points
  ```
  Defined in `src/game_workflows/player.py:28-36`.
* **Verification Target:** Callback closure extraction.

### Q128: What is the code implementation of `reset_character_form` in `player.py`?
* **Ground Truth Solution:**
  ```python
  def reset_character_form():
      st.session_state.ability_scores = {ability: 8 for ability in [
          "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]}
      st.session_state.remaining_points = TOTAL_SKILL_POINTS
  ```
  Defined in `src/game_workflows/player.py:38-41`.
* **Verification Target:** Form reset closure extraction.

### Q129: Show the code of `initialize_session_state` in `src/game_workflows/player.py`.
* **Ground Truth Solution:**
  Initializes `character_created = False`, `ability_scores = {ability: 8...}`, and `remaining_points = TOTAL_SKILL_POINTS` (`player.py:15-22`).
* **Verification Target:** Disambiguating same-name function in `player.py` vs `game.py`.

### Q130: Show the code of `initialize_session_state` in `src/game_workflows/game.py`.
* **Ground Truth Solution:**
  Initializes `character_creation = False` and `game_state = {"state": False}` (`game.py:8-14`).
* **Verification Target:** Disambiguating same-name function in `game.py` vs `player.py`.

### Q131: What is the exact code definition of `load_characters()` in `loaders.py`?
* **Ground Truth Solution:**
  ```python
  def load_characters():
      if os.path.exists(CHARACTERS_FILE):
          with open(CHARACTERS_FILE, "r") as f:
              return json.load(f)
      return {}
  ```
  Lines 12–16 in `src/game_workflows/loaders.py`.
* **Verification Target:** Base loader snippet extraction.

### Q132: Show the code definition of `save_characters()` in `loaders.py`.
* **Ground Truth Solution:**
  ```python
  def save_characters(characters):
      with open(CHARACTERS_FILE, "w") as f:
          json.dump(characters, f, indent=4)
  ```
  Lines 19–21 in `src/game_workflows/loaders.py`.
* **Verification Target:** Base persistence snippet extraction.

### Q133: What is the implementation of `load_adventure()` in `loaders.py`?
* **Ground Truth Solution:**
  Reads `{uuid}.pkl` and `{uuid}_char.pkl` from `HISTORY_DB_DIR/HIST` in binary mode (`"rb"`), returns `(history, characters)`, or raises `NameError` (`loaders.py:24-36`).
* **Verification Target:** Binary deserialization snippet extraction.

### Q134: What does `load_available_adventures()` do in `loaders.py`?
* **Ground Truth Solution:**
  Reads `history_ids.json` from `HISTORY_DB_DIR/HIST`; returns json dict or `{}` (`loaders.py:39-44`).
* **Verification Target:** Index loader snippet extraction.

### Q135: Show the complete implementation of `save_adventure()` in `loaders.py`.
* **Ground Truth Solution:**
  `pickle.dump(history, f)` to `{uuid}.pkl`, `json.dump(history_names, f)` to `history_ids.json`, and if characters given, `pickle.dump(characters, f)` to `{uuid}_char.pkl` (`loaders.py:47-63`).
* **Verification Target:** Multi-file persistence snippet.

### Q136: What is the code of `update_history_ids()` in `loaders.py`?
* **Ground Truth Solution:**
  Opens `history_ids.json` and writes `st.session_state['adventure_dict']` (`loaders.py:65-69`).
* **Verification Target:** Short helper snippet extraction.

### Q137: What is the code implementation of `delete_history_file()`?
* **Ground Truth Solution:**
  Removes uuid from `st.session_state['adventure_dict']`, deletes embeddings from `history_store`, removes `{uuid}.pkl` and `{uuid}_char.pkl`, and calls `update_history_ids()` (`loaders.py:72-91`).
* **Verification Target:** Composite deletion snippet extraction.

### Q138: Show the code of `check_ollama_availability()` in `utils.py`.
* **Ground Truth Solution:**
  Makes `requests.get` to `http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/version` with `timeout=5`; returns `status_code == 200` (`utils.py:12-18`).
* **Verification Target:** HTTP check snippet extraction.

### Q139: What is the implementation of `test_model_availability()` in `utils.py`?
* **Ground Truth Solution:**
  Checks `check_ollama_availability()`; if false, shows `st.error` and `"Retry Connection"` button calling `st.rerun()` (`utils.py:21-28`).
* **Verification Target:** UI error handler snippet.

### Q140: Show the implementation of `initialize_rag()` in `src/imports/model.py`.
* **Ground Truth Solution:**
  ```python
  @st.cache_resource
  def initialize_rag():
      handbook_store = Chroma(
          embedding_function=st.session_state.embedding_model, persist_directory=CHROMA_DB_DIR)
      return handbook_store.as_retriever()
  ```
  Lines 19–23 in `src/imports/model.py`.
* **Verification Target:** Cached Chroma retriever factory.

### Q141: What is the code for `initialize_history()` in `src/imports/model.py`?
* **Ground Truth Solution:**
  ```python
  @st.cache_resource
  def initialize_history():
      history_store = Chroma(
          embedding_function=st.session_state.embedding_model, persist_directory=HISTORY_DB_DIR)
      return history_store
  ```
  Lines 26–30 in `src/imports/model.py`.
* **Verification Target:** Cached Chroma history factory.

### Q142: Show the code of `set_fantasy_theme()` in `theme.py`.
* **Ground Truth Solution:**
  Injects `<style>` tag with `@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&display=swap')` and background styling (`theme.py:4-29`).
* **Verification Target:** CSS injection snippet.

### Q143: Show the implementation of `reset_old_games()` in `game.py`.
* **Ground Truth Solution:**
  Deletes `has_adventure_started`, `chat_history`, and `characters_in_adventure` from `st.session_state` if present (`game.py:70-76`).
* **Verification Target:** Session cleanup snippet.

### Q144: Show the code of `dm_turn()` in `adventure.py`.
* **Ground Truth Solution:**
  Queries `vector_store.similarity_search` on last 5 story turns with `k=3`, builds prompt with relevant lore, calls `api_call(model, dm_prompt, 300)` (`adventure.py:17-21`).
* **Verification Target:** Standalone turn runner snippet.

### Q145: Show the implementation of `start_new_adventure()` in `adventure.py`.
* **Ground Truth Solution:**
  Calls `api_call` with DM intro prompt, returns initial game state dictionary and intro text (`adventure.py:5-14`).
* **Verification Target:** Standalone intro runner snippet.

---

## Category 8: Type Hierarchy, OOP & Class Introspection

### Q146: What classes are defined in `src/api_workflows/call_api.py`?
* **Ground Truth Solution:**
  A single class: `class OllamaApi`.
* **Verification Target:** Class inventory query.

### Q147: What are the direct methods of the `OllamaApi` class?
* **Ground Truth Solution:**
  `__init__(self, model, temperature=0.7)`, `start_adventure(self, characters, difficulty, user_prompt)`, `name_adventure(self, adventure)`, and `progress_story(self, chat_msg, history)`.
* **Verification Target:** Method extraction for class.

### Q148: Does `OllamaApi` inherit from any superclasses or base classes?
* **Ground Truth Solution:**
  No, it is a root class inheriting directly from `object`.
* **Verification Target:** Inheritance root verification.

### Q149: What is the constructor signature and initialization logic of `OllamaApi`?
* **Ground Truth Solution:**
  `def __init__(self, model: str, temperature: int = 0.7) -> None`. Initializes `self.llm = OllamaLLM(model=model, temperature=temperature)` and `self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1100, chunk_overlap=100)`.
* **Verification Target:** Constructor AST audit.

### Q150: Does `src/imports/model.py` define any custom classes?
* **Ground Truth Solution:**
  No classes; it contains only procedural functions (`initialize_rag`, `initialize_history`, `manage_models`).
* **Verification Target:** Negative class query.

### Q151: Does `src/game_workflows/player.py` define any classes?
* **Ground Truth Solution:**
  No classes; purely procedural functions and closures.
* **Verification Target:** Functional vs OOP architecture check.

### Q152: What external LangChain classes are instantiated across the codebase?
* **Ground Truth Solution:**
  `OllamaLLM`, `RecursiveCharacterTextSplitter`, `ChatPromptTemplate`, `Chroma`, `HuggingFaceEmbeddings`, `Document`, `AIMessage`, `HumanMessage`, `SystemMessage`.
* **Verification Target:** External dependency instantiation audit.

### Q153: Where is `Chroma` instantiated and how is it configured?
* **Ground Truth Solution:**
  In `src/imports/model.py:21` with `persist_directory=CHROMA_DB_DIR` and `model.py:28` with `persist_directory=HISTORY_DB_DIR`.
* **Verification Target:** Vector DB client instantiation points.

### Q154: Where is `HuggingFaceEmbeddings` instantiated and what models does it support in the UI?
* **Ground Truth Solution:**
  In `src/imports/model.py:65`. The UI dropdown offers: `"sentence-transformers/all-MiniLM-L6-v2"` and `"sentence-transformers/all-mpnet-base-v2"`.
* **Verification Target:** Embedding model option audit.

### Q155: Where is `RecursiveCharacterTextSplitter` instantiated and what are its chunk size and overlap?
* **Ground Truth Solution:**
  In `src/api_workflows/call_api.py:18` with `chunk_size=1100, chunk_overlap=100`.
* **Verification Target:** Text splitter parameter audit.

### Q156: Where is `OllamaLLM` instantiated in the codebase?
* **Ground Truth Solution:**
  In `src/api_workflows/call_api.py:17` inside `OllamaApi.__init__`.
* **Verification Target:** LLM client instantiation point.

### Q157: How is LangChain's `Document` class used in `core.py`?
* **Ground Truth Solution:**
  Instantiated as `history_document = Document(page_content=adventure_start, metadata={'source': "AI", "uuid": current_uuid})` (`core.py:68`) and passed to `save_doc_to_history_vector()`.
* **Verification Target:** Data transfer object audit.

### Q158: Are there any abstract base classes (ABCs) implemented in this repository?
* **Ground Truth Solution:**
  No ABCs or `abc.abstractmethod` usages exist in the repo.
* **Verification Target:** Negative pattern verification.

### Q159: What third-party message classes are used in `core.py`?
* **Ground Truth Solution:**
  `AIMessage`, `HumanMessage`, `SystemMessage` from `langchain_core.messages`.
* **Verification Target:** Message schema inventory.

### Q160: Are there any Pydantic models defined in the `dnd` repo?
* **Ground Truth Solution:**
  No Pydantic `BaseModel` classes are defined in `dnd` (they are used in the CodeNavigator pipeline, but not in the game repo itself).
* **Verification Target:** Repository boundary verification.

---

## Category 9: Dead Code, Orphans & Reachability

### Q161: Is `start_new_adventure()` in `src/game_workflows/adventure.py` called anywhere in the active application?
* **Ground Truth Solution:**
  No. It has 0 incoming callers. The active Streamlit game calls `core.py:start_adventure()`.
* **Verification Target:** Uncalled function detection.

### Q162: Is `dm_turn()` in `src/game_workflows/adventure.py` used by `main.py` or `game.py`?
* **Ground Truth Solution:**
  No. It has 0 incoming callers. The active application calls `OllamaApi.progress_story()` in `call_api.py`.
* **Verification Target:** Dead function reachability analysis.

### Q163: Are there any dead or uncalled functions in `src/game_workflows/adventure.py`?
* **Ground Truth Solution:**
  Both functions in `adventure.py` (`start_new_adventure` and `dm_turn`) are uncalled orphans.
* **Verification Target:** File-level dead code audit.

### Q164: Is the entire file `src/game_workflows/adventure.py` an orphan module?
* **Ground Truth Solution:**
  Yes. No file in the repository imports `adventure.py`.
* **Verification Target:** Dead file reachability.

### Q165: Is `api_call` imported in `adventure.py` actually defined in `call_api.py`?
* **Ground Truth Solution:**
  No! `from src.api_workflows.call_api import api_call` in `adventure.py:2` is a broken import because `call_api.py` does not define `api_call` (it defines `class OllamaApi`).
* **Verification Target:** Broken import / dead edge detection.

### Q166: Are there any unused imports in `src/game_workflows/player.py`?
* **Ground Truth Solution:**
  `from requests import session` on line 3 is completely unused.
* **Verification Target:** AST unused import detection.

### Q167: Is `from requests import session` in `player.py` ever used?
* **Ground Truth Solution:**
  No, it is an unused import.
* **Verification Target:** Specific unused import check.

### Q168: Are there any unused variables declared in `src/game_workflows/references.py`?
* **Ground Truth Solution:**
  Both `weapon_dict` and `armor_dict` are imported and used in `player.py`. No unused variables exist in `references.py`.
* **Verification Target:** Variable reachability check.

### Q169: Is `reset_character_form()` in `player.py` called anywhere, or is it dead code?
* **Ground Truth Solution:**
  It is defined as an inner function inside `create_character_form()` at line 38, but is never invoked by any button callback or statement inside the form. It is dead code.
* **Verification Target:** Inner closure orphan detection.

### Q170: Are there any unreferenced functions in `src/game_workflows/loaders.py`?
* **Ground Truth Solution:**
  All functions in `loaders.py` are referenced:
  - `load_characters` $\rightarrow$ called in `player.py`, `core.py`, `call_api.py`
  - `save_characters` $\rightarrow$ called in `player.py`
  - `load_adventure` $\rightarrow$ called in `game.py`
  - `load_available_adventures` $\rightarrow$ called in `game.py`
  - `save_adventure` $\rightarrow$ called in `core.py`
  - `update_history_ids` $\rightarrow$ called in `loaders.py`
  - `delete_history_file` $\rightarrow$ called in `game.py`
* **Verification Target:** Full reachability verification of utility module.

### Q171: Are there any dead or uncalled functions in `src/utils.py`?
* **Ground Truth Solution:**
  No. Both `check_ollama_availability` and `test_model_availability` are invoked from `main.py`.
* **Verification Target:** Utility module reachability verification.

### Q172: Is `character_created` in `st.session_state` ever checked after initialization?
* **Ground Truth Solution:**
  Initialized in `player.py:17`, but never read or checked elsewhere. It is dead state.
* **Verification Target:** Dead session state flag detection.

### Q173: Are there any orphan functions in `src/imports/model.py`?
* **Ground Truth Solution:**
  No. `initialize_rag` and `initialize_history` are called by `manage_models()`, which is called by `main.py`.
* **Verification Target:** Import module reachability check.

### Q174: Are there any unused environment variables loaded in `.env` or in the Python files?
* **Ground Truth Solution:**
  All 6 environment variables loaded via `os.getenv` are read and utilized.
* **Verification Target:** Configuration reachability check.

### Q175: Run a full dead-code audit: What are all unreachable functions detected across the repository?
* **Ground Truth Solution:**
  1. `src/game_workflows/adventure.py::start_new_adventure`
  2. `src/game_workflows/adventure.py::dm_turn`
  3. `src/game_workflows/player.py::create_character_form::reset_character_form`
* **Verification Target:** Project-wide reachability audit.

---

## Category 10: Architecture Coupling & Modularity Boundaries

### Q176: Are there any circular imports between `game_workflows` and `api_workflows`?
* **Ground Truth Solution:**
  No circular imports exist. `core.py` and `call_api.py` both import `loaders.py`, but there is no cycle (`call_api.py` does not import `core.py`).
* **Verification Target:** Circular dependency cycle check.

### Q177: Does `src/game_workflows/player.py` import anything from `src/game_workflows/core.py`?
* **Ground Truth Solution:**
  No. `player.py` only imports from `loaders.py` and `references.py`.
* **Verification Target:** Dependency boundary check.

### Q178: Does `src/game_workflows/core.py` import anything from `src/game_workflows/player.py`?
* **Ground Truth Solution:**
  Yes: `from src.game_workflows.player import load_characters` in line 7.
* **Verification Target:** Cross-module import check.

### Q179: Is there an import cycle between `player.py` and `core.py`?
* **Ground Truth Solution:**
  No cycle. `core.py` imports from `player.py`, but `player.py` does not import from `core.py`.
* **Verification Target:** Acyclic dependency verification.

### Q180: What modules depend directly on `src/game_workflows/loaders.py`?
* **Ground Truth Solution:**
  `player.py`, `core.py`, `game.py`, and `call_api.py`.
* **Verification Target:** Fan-in module dependency audit.

### Q181: What are all the internal dependencies imported by `main.py`?
* **Ground Truth Solution:**
  `src.ui.theme`, `src.utils`, `src.imports.model`, `src.game_workflows.game`, `src.game_workflows.player`.
* **Verification Target:** Main orchestrator import map.

### Q182: What modules import from `src/utils.py`?
* **Ground Truth Solution:**
  Only `main.py`.
* **Verification Target:** Utility dependency fan-in.

### Q183: What modules import from `src/imports/model.py`?
* **Ground Truth Solution:**
  Only `main.py`.
* **Verification Target:** Model manager dependency fan-in.

### Q184: What files import `src/game_workflows/references.py`?
* **Ground Truth Solution:**
  Only `src/game_workflows/player.py`.
* **Verification Target:** Reference table dependency fan-in.

### Q185: Does `src/ui/theme.py` have any dependencies on the game logic or API?
* **Ground Truth Solution:**
  No. `theme.py` has zero internal imports; it only imports `streamlit as st`.
* **Verification Target:** UI presentation decoupling verification.

---

## Category 11: Parameter Lineage & Value Propagation

### Q186: Trace the lineage of the `difficulty` parameter in `start_adventure` through to `OllamaApi`.
* **Ground Truth Solution:**
  Selected in `core.py:40` via `st.radio("Select Difficulty", ["Easy", "Medium", "Hard"])` $\rightarrow$ passed to `api.start_adventure(..., adventure_difficulty, ...)` $\rightarrow$ bound to parameter `difficulty: str` in `OllamaApi.start_adventure` (`call_api.py:24`) $\rightarrow$ injected into `chain.stream({"difficulty": difficulty, ...})` in prompt template.
* **Verification Target:** Cross-module parameter flow.

### Q187: Trace the lineage of the `characters` parameter from `core.py` to `OllamaApi.start_adventure`.
* **Ground Truth Solution:**
  Selected via `st.multiselect` in `core.py:36` $\rightarrow$ stored in `st.session_state["characters_in_adventure"]` $\rightarrow$ passed to `api.start_adventure(st.session_state["characters_in_adventure"], ...)` $\rightarrow$ bound to `characters: List[str]` in `call_api.py:24` $\rightarrow$ mapped to `characters_dict[character]` string $\rightarrow$ injected into prompt as `{characters_details}`.
* **Verification Target:** Parameter transformation and prompt interpolation.

### Q188: Trace how `score` flows into `calculate_points_spent` in `player.py`.
* **Ground Truth Solution:**
  `st.number_input` value $\rightarrow$ `new_score` in `update_ability_score(ability)` $\rightarrow$ passed as argument `score` to `calculate_points_spent(new_score)` $\rightarrow$ evaluated as `score - 8`.
* **Verification Target:** Widget value to closure argument propagation.

### Q189: Trace how `uuid` propagates from `initialize_adventure_state` to `load_adventure`.
* **Ground Truth Solution:**
  Passed into `initialize_adventure_state(uuid)` from `game.py:53` $\rightarrow$ forwarded as argument to `load_adventure(uuid=uuid)` in `game.py:63` $\rightarrow$ concatenated to form `{uuid}.pkl` and `{uuid}_char.pkl` paths in `loaders.py:26-27`.
* **Verification Target:** UUID string propagation into file paths.

### Q190: Trace how `user_prompt` in `core.py` reaches the LangChain prompt template in `call_api.py`.
* **Ground Truth Solution:**
  Entered via `st.text_area("Adventure Prompt")` $\rightarrow$ stored in `adventure_user_prompt` $\rightarrow$ passed to `api.start_adventure(..., adventure_user_prompt)` $\rightarrow$ defaulted to `"make it as instreasting as possible."` if None $\rightarrow$ injected into `{user_prompt}` in `ChatPromptTemplate`.
* **Verification Target:** Default argument assignment and prompt injection flow.

### Q191: Trace how `adventure_start` text flows from `api.start_adventure` into `save_adventure`.
* **Ground Truth Solution:**
  Returned via `st.write_stream(api.start_adventure(...))` $\rightarrow$ stored in `adventure_start` string $\rightarrow$ wrapped into `history_document = Document(page_content=adventure_start)` $\rightarrow$ added to `st.session_state["chat_history"]` $\rightarrow$ passed to `save_adventure(..., history=st.session_state["chat_history"])`.
* **Verification Target:** Streamed text accumulation and persistence flow.

### Q192: Trace the lineage of the `model` parameter from `manage_models` into `OllamaApi.__init__`.
* **Ground Truth Solution:**
  Selected in `st.selectbox("Dungeon Master Model", models)` in `model.py:56` $\rightarrow$ stored in `dm_model` $\rightarrow$ passed to `OllamaApi(model=dm_model)` $\rightarrow$ passed to `OllamaLLM(model=model, ...)`.
* **Verification Target:** Constructor parameter binding.

### Q193: Trace how `chat_msg` flows through `OllamaApi.progress_story`.
* **Ground Truth Solution:**
  Passed as `chat_msg: dict[str, str]` $\rightarrow$ iterated over via `for msg in chat.values():` $\rightarrow$ embedded via `embed_query(msg)` $\rightarrow$ queried in vector search $\rightarrow$ formatted into prompt.
* **Verification Target:** Dictionary values iteration and embedding query flow.

---

## Category 12: Multi-File Conceptual / Method 1 Queries

### Q194: How does the character creation point-buy system calculate remaining skill points?
* **Tool Chain:** Method 1 (`tool_search_codebase_semantic` $\rightarrow$ `tool_get_symbol_code_snippet`)
* **Ground Truth Solution:**
  Starts with `TOTAL_SKILL_POINTS = 27`. Every ability score starts at 8 (cost 0). Raising a score costs `score - 8` points via `calculate_points_spent(score)`. In `update_ability_score()`, the delta `old_points - new_points` is added to `remaining_points`. If `remaining_points < 0`, a Streamlit warning is displayed.
* **Verification Target:** Pure natural language conceptual query to AST arithmetic resolution.

### Q195: What happens when a player allocates points to an ability score higher than 15?
* **Ground Truth Solution:**
  The Streamlit `st.number_input` in `player.py:74` enforces `max_value=15`. The UI restricts input from going above 15.
* **Verification Target:** Form boundary constraint resolution.

### Q196: How does the application check if the local Ollama server is alive before letting users play?
* **Ground Truth Solution:**
  `test_model_availability()` in `src/utils.py` calls `check_ollama_availability()`, which makes a `requests.get` to `http://localhost:11434/api/version` with a 5-second timeout. If unreachable, it renders an error message with instructions to run `ollama serve` and a `"Retry Connection"` button.
* **Verification Target:** System health check conceptual query.

### Q197: Where and how is the 5e Dungeons & Dragons rules handbook indexed into ChromaDB?
* **Ground Truth Solution:**
  `initialize_rag()` in `src/imports/model.py:19-24` connects to a pre-built ChromaDB located at `./5e_dnd_chroma_langchain_db` (or `CHROMA_DB_DIR`), binds `st.session_state.embedding_model`, and returns it as a LangChain retriever (`handbook_store.as_retriever()`).
* **Verification Target:** RAG vector store architecture resolution.

### Q198: How does the application persist conversation history so players can resume past campaigns?
* **Ground Truth Solution:**
  Dual persistence:
  1. Serializes chat messages list to `./history/HIST/{uuid}.pkl` and characters to `{uuid}_char.pkl` via `pickle.dump()`.
  2. Embeds each message into ChromaDB (`st.session_state.history_store`) tagged with `metadata={"uuid": uuid}`.
  3. Maps UUIDs to friendly names in `history_ids.json`.
* **Verification Target:** Dual-tier persistence concept mapping.

### Q199: How does the Dungeon Master prompt change its behavior between Easy, Medium, and Hard difficulty?
* **Ground Truth Solution:**
  In `OllamaApi.start_adventure()` (`call_api.py:35-37`):
  - **Easy:** *"You'll let their dice roll high mostly unless the demand is unreasonable"*
  - **Medium:** *"You'll try and fail the roll where it makes sense and make the story intresting"*
  - **Hard:** *"You can randomly choose the roll"*
* **Verification Target:** System prompt template rule extraction.

### Q200: How does the system retrieve relevant campaign lore from the vector store when generating the next turn in a story?
* **Ground Truth Solution:**
  In `OllamaApi.progress_story()` (`call_api.py:74-100`):
  1. Iterates over player messages in `chat.values()`.
  2. Embeds each message using `st.session_state.embedding_model.embed_query(msg)`.
  3. Executes `history_store.similarity_search_by_vector_with_relevance_scores` with `k=2` filtered by `{"uuid": st.session_state["current_uuid"]}`.
  4. Prepends retrieved documents as `AIMessage` or `HumanMessage` to the conversation context before streaming the LLM response.
* **Verification Target:** Full multi-step RAG context retrieval pipeline.
