"""
benchmark_dataset.py

Comprehensive 200-Question Ground-Truth Benchmark Dataset for CodeNavigator.
Verified directly against the source code of the LLM-DND repository.
"""

BENCHMARK_DATASET = {   'Q01': {   'id': 'Q01',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `load_characters()` in the codebase?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='load_characters', direction='incoming')`",
               'answer': '`load_characters()` (defined in `src/game_workflows/loaders.py:12-16`) is called by **3 '
                         'distinct call sites**:\n'
                         '1. `display_character_list()` in `src/game_workflows/player.py:193`\n'
                         '2. `start_adventure()` in `src/game_workflows/core.py:32`\n'
                         '3. `OllamaApi.start_adventure()` in `src/api_workflows/call_api.py:49`',
               'verification_target': 'Multi-file caller aggregation across 3 modules.'},
    'Q02': {   'id': 'Q02',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What are all the call sites that invoke `save_characters()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='save_characters', direction='incoming')`",
               'answer': '`save_characters()` (defined in `src/game_workflows/loaders.py:19-21`) is called by two '
                         'functions in `src/game_workflows/player.py`:\n'
                         '1. `create_character_form()` at line 179 (when saving a newly created hero to '
                         '`characters.json`)\n'
                         '2. `display_character_list()` at line 203 (when deleting a character from the sidebar)',
               'verification_target': 'Direct edge resolution from `player.py` to `loaders.py`.'},
    'Q03': {   'id': 'Q03',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Where is `save_adventure()` called across the entire repository?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='save_adventure', direction='incoming')`",
               'answer': '`save_adventure()` (defined in `src/game_workflows/loaders.py:47-63`) is called exclusively '
                         'in `src/game_workflows/core.py` at three distinct points:\n'
                         '1. Line 75 in `start_adventure()`: saves the initial adventure session, `.pkl` history, and '
                         '`history_ids.json`.\n'
                         '2. Line 130 in `start_adventure()`: saves state after a player submits a character action in '
                         'the chat form.\n'
                         '3. Line 141 in `start_adventure()`: saves state after the Dungeon Master finishes generating '
                         'the turn progression response.',
               'verification_target': 'Cross-module caller detection (`core.py` -> `loaders.py`).'},
    'Q04': {   'id': 'Q04',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What functions call `load_adventure()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='load_adventure', direction='incoming')`",
               'answer': '`load_adventure()` (defined in `src/game_workflows/loaders.py:24-36`) is called exclusively '
                         'by:\n'
                         '1. `initialize_adventure_state(uuid)` in `src/game_workflows/game.py:63-64` to unpack '
                         '`{uuid}.pkl` and `{uuid}_char.pkl` from disk.',
               'verification_target': 'Pickle loader consumer identification.'},
    'Q05': {   'id': 'Q05',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `delete_history_file()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='delete_history_file', direction='incoming')`",
               'answer': '`delete_history_file()` (defined in `src/game_workflows/loaders.py:72-91`) is called by:\n'
                         '1. `display_adventure_list()` in `src/game_workflows/game.py:57` when the player clicks the '
                         'delete (trash) button next to a saved adventure.',
               'verification_target': 'UI callback edge resolution.'},
    'Q06': {   'id': 'Q06',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Which functions invoke `update_history_ids()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='update_history_ids', direction='incoming')`",
               'answer': '`update_history_ids()` (defined in `src/game_workflows/loaders.py:65-69`) is called by:\n'
                         '1. `delete_history_file(uuid)` in `src/game_workflows/loaders.py:88` after unlinking pickle '
                         'files from disk to rewrite `history_ids.json`.',
               'verification_target': 'Intra-file caller resolution within `loaders.py`.'},
    'Q07': {   'id': 'Q07',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Where in the codebase is `create_character_form()` called?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='create_character_form', direction='incoming')`",
               'answer': '`create_character_form()` (defined in `src/game_workflows/player.py:14-189`) is called by:\n'
                         '1. `play_game()` in `src/game_workflows/game.py:35` when '
                         '`st.session_state.character_creation` is True.',
               'verification_target': 'State-guarded UI caller resolution.'},
    'Q08': {   'id': 'Q08',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What functions call `start_adventure()` in `src/game_workflows/core.py`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='start_adventure', direction='incoming', "
                             "file_path='src/game_workflows/core.py')`",
               'answer': '`start_adventure()` in `src/game_workflows/core.py` is called by two functions in '
                         '`src/game_workflows/game.py`:\n'
                         "1. `play_game()` at line 38 (when `st.session_state['game_state']['state']` is True after "
                         "clicking 'Start Adventure')\n"
                         '2. `display_adventure_list()` at line 54 (when the user clicks the continue adventure '
                         "controller button '🎮')",
               'verification_target': 'Disambiguating `core.py:start_adventure` from `call_api.py:start_adventure`.'},
    'Q09': {   'id': 'Q09',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `play_game()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='play_game', direction='incoming')`",
               'answer': '`play_game()` (defined in `src/game_workflows/game.py:16-39`) is called by:\n'
                         "1. `main()` in `main.py:50` when the user selects 'Play Game' on the sidebar radio "
                         'navigation.',
               'verification_target': 'Root entry-point edge from `main.py`.'},
    'Q10': {   'id': 'Q10',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Which functions invoke `display_adventure_list()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='display_adventure_list', direction='incoming')`",
               'answer': '`display_adventure_list()` (defined in `src/game_workflows/game.py:41-60`) is called by:\n'
                         "1. `main()` in `main.py:53` when the user navigates to the 'Play Game' section.",
               'verification_target': 'Sidebar listing entry point.'},
    'Q11': {   'id': 'Q11',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Where is `display_character_list()` called?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='display_character_list', direction='incoming')`",
               'answer': '`display_character_list()` (defined in `src/game_workflows/player.py:191-205`) is called '
                         'by:\n'
                         "1. `main()` in `main.py:52` in the 'Play Game' page branch to render created characters in "
                         'the sidebar.',
               'verification_target': 'Root UI layout sequence.'},
    'Q12': {   'id': 'Q12',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `initialize_adventure_state()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='initialize_adventure_state', "
                             "direction='incoming')`",
               'answer': '`initialize_adventure_state()` (defined in `src/game_workflows/game.py:62-68`) is called '
                         'by:\n'
                         '1. `display_adventure_list()` in `src/game_workflows/game.py:53` when the user clicks the '
                         "continue button ('🎮') for a saved adventure.",
               'verification_target': 'Button handler invocation path.'},
    'Q13': {   'id': 'Q13',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What functions trigger `reset_old_games()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='reset_old_games', direction='incoming')`",
               'answer': '`reset_old_games()` (defined in `src/game_workflows/game.py:70-77`) is called by:\n'
                         "1. `play_game()` in `src/game_workflows/game.py:30` when the user clicks the '🏞️ Start "
                         "Adventure' button in the sidebar.",
               'verification_target': 'State sanitization trigger identification.'},
    'Q14': {   'id': 'Q14',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `check_ollama_availability()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='check_ollama_availability', "
                             "direction='incoming')`",
               'answer': '`check_ollama_availability()` (defined in `src/utils.py:12-18`) is called by:\n'
                         "1. `display_updated_status_sidebar()` in `main.py:29` (to write 'Running' or 'Not Running' "
                         'to the sidebar placeholder)\n'
                         '2. `test_model_availability()` in `src/utils.py:22` (to verify connectivity before page '
                         'load)',
               'verification_target': 'Utility check reuse across `main.py` and `utils.py`.'},
    'Q15': {   'id': 'Q15',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What are the incoming callers of `test_model_availability()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='test_model_availability', "
                             "direction='incoming')`",
               'answer': '`test_model_availability()` (defined in `src/utils.py:21-28`) is called directly by:\n'
                         '1. `main()` in `main.py:44` during application startup.',
               'verification_target': 'Pre-flight sanity check hook.'},
    'Q16': {   'id': 'Q16',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Where is `manage_models()` invoked?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='manage_models', direction='incoming')`",
               'answer': '`manage_models()` (defined in `src/imports/model.py:33-70`) is invoked in:\n'
                         "1. `main()` in `main.py:56` when the sidebar radio is set to 'Manage Models'.",
               'verification_target': 'Top-level tab dispatch.'},
    'Q17': {   'id': 'Q17',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `set_fantasy_theme()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='set_fantasy_theme', direction='incoming')`",
               'answer': '`set_fantasy_theme()` (defined in `src/ui/theme.py:3-13`) is called by:\n'
                         '1. `main()` in `main.py:38` at the beginning of the main application script.',
               'verification_target': 'CSS injection hook point.'},
    'Q18': {   'id': 'Q18',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'Who calls `initialize_rag()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='initialize_rag', direction='incoming')`",
               'answer': '`initialize_rag()` (defined in `src/imports/model.py:20-23`) is called by:\n'
                         "1. `manage_models()` in `src/imports/model.py:67` when the user clicks 'Save Model "
                         "Selections'.",
               'verification_target': 'Cached resource factory invocation.'},
    'Q19': {   'id': 'Q19',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What functions invoke `initialize_history()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='initialize_history', direction='incoming')`",
               'answer': '`initialize_history()` (defined in `src/imports/model.py:27-30`) is called by:\n'
                         "1. `manage_models()` in `src/imports/model.py:68` when the user clicks 'Save Model "
                         "Selections'.",
               'verification_target': 'ChromaDB history store factory call.'},
    'Q20': {   'id': 'Q20',
               'category': 'Category 1: Upstream Callers & Caller Chains',
               'question': 'What is the full upstream call chain that leads to `load_characters()` starting from '
                           '`main()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='load_characters', direction='incoming', "
                             'max_depth=3)`',
               'answer': 'The complete upstream call chain leading to `load_characters()` starting from `main()` '
                         'follows two distinct routes:\n'
                         '1. Route A (Via Adventure Log):\n'
                         '   `main()` (`main.py:50`) -> `play_game()` (`game.py:38`) -> `start_adventure()` '
                         '(`core.py:32`) -> `load_characters()` (`loaders.py:12`)\n'
                         '2. Route B (Via Character Sidebar):\n'
                         '   `main()` (`main.py:52`) -> `display_character_list()` (`player.py:193`) -> '
                         '`load_characters()` (`loaders.py:12`)',
               'verification_target': 'Multi-hop call path reconstruction.\n\n---'},
    'Q21': {   'id': 'Q21',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What functions does `main()` in `main.py` call directly?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='main', direction='outgoing')`",
               'answer': '`main()` in `main.py` directly calls the following internal functions:\n'
                         '1. `set_fantasy_theme()` (`src/ui/theme.py`)\n'
                         '2. `display_updated_status_sidebar()` (`main.py`)\n'
                         '3. `test_model_availability()` (`src/utils.py`)\n'
                         '4. `play_game()` (`src/game_workflows/game.py`)\n'
                         '5. `display_character_list()` (`src/game_workflows/player.py`)\n'
                         '6. `display_adventure_list()` (`src/game_workflows/game.py`)\n'
                         '7. `manage_models()` (`src/imports/model.py`)',
               'verification_target': 'High-level router outgoing fan-out.'},
    'Q22': {   'id': 'Q22',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What does `play_game()` in `src/game_workflows/game.py` invoke?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='play_game', direction='outgoing')`",
               'answer': '`play_game()` in `src/game_workflows/game.py` invokes:\n'
                         '1. `initialize_session_state()` (`game.py:22`)\n'
                         "2. `reset_old_games()` (`game.py:30`, on 'Start Adventure' button click)\n"
                         '3. `create_character_form()` (`src/game_workflows/player.py:35`, when `character_creation` '
                         'is True)\n'
                         "4. `start_adventure()` (`src/game_workflows/core.py:38`, when `game_state['state']` is True)",
               'verification_target': 'Workflow state branching.'},
    'Q23': {   'id': 'Q23',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What functions does `start_adventure()` in `src/game_workflows/core.py` call?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='start_adventure', direction='outgoing')`",
               'answer': '`start_adventure()` in `src/game_workflows/core.py` directly calls:\n'
                         '1. `initialise_adventure_session_state()` (`core.py:27`)\n'
                         '2. `load_characters()` (`src/game_workflows/player.py:32`)\n'
                         "3. `st.session_state['api'].start_adventure()` (`call_api.py:51`)\n"
                         "4. `st.session_state['api'].name_adventure()` (`call_api.py:57`)\n"
                         "5. `st.session_state['api'].save_doc_to_history_vector()` (`call_api.py:71, 132, 143`)\n"
                         '6. `save_adventure()` (`src/game_workflows/loaders.py:75, 130, 141`)\n'
                         "7. `st.session_state['api'].progress_story()` (`call_api.py:122`)\n"
                         '8. `st.rerun()` (`core.py:77, 146`)',
               'verification_target': 'Orchestration pipeline fan-out.'},
    'Q24': {   'id': 'Q24',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What outgoing calls are made by `create_character_form()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='create_character_form', direction='outgoing')`",
               'answer': '`create_character_form()` in `src/game_workflows/player.py` invokes:\n'
                         '1. `initialize_session_state()` (`player.py:43`, inner function)\n'
                         '2. `calculate_points_spent()` (`player.py:32, 33, 86, 87`, inner function)\n'
                         '3. `update_ability_score()` (`player.py:77`, inner callback passed to Streamlit widget)\n'
                         '4. `save_characters()` (`src/game_workflows/loaders.py:179`)\n'
                         '5. `reset_character_form()` (`player.py:181`, inner function)\n'
                         '6. `st.rerun()` (`player.py:183`)',
               'verification_target': 'Nested lexical closures vs external imports.'},
    'Q25': {   'id': 'Q25',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What downstream functions are executed by `load_adventure()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='load_adventure', direction='outgoing')`",
               'answer': '`load_adventure(uuid)` in `src/game_workflows/loaders.py` calls:\n'
                         '1. `os.path.join()` (`loaders.py:25, 26, 27`)\n'
                         '2. `os.path.exists()` (`loaders.py:29`)\n'
                         '3. `pickle.load()` (`loaders.py:31, 33` to load `{uuid}.pkl` and `{uuid}_char.pkl`)',
               'verification_target': 'Standard library I/O leaf calls.'},
    'Q26': {   'id': 'Q26',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What functions are called inside `delete_history_file()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='delete_history_file', direction='outgoing')`",
               'answer': '`delete_history_file(uuid)` in `src/game_workflows/loaders.py` invokes:\n'
                         '1. `st.session_state.history_store.get(where={"uuid": uuid})` (`loaders.py:77`)\n'
                         '2. `st.session_state.history_store.delete(history_ids)` (`loaders.py:81`)\n'
                         '3. `os.path.join()` (`loaders.py:74, 75`)\n'
                         '4. `os.path.exists()` (`loaders.py:84`)\n'
                         '5. `os.remove()` (`loaders.py:85, 86` for `{uuid}.pkl` and `{uuid}_char.pkl`)\n'
                         '6. `update_history_ids()` (`loaders.py:88`)',
               'verification_target': 'Vector deletion + File unlink coordination.'},
    'Q27': {   'id': 'Q27',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What outgoing calls are initiated by `display_adventure_list()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='display_adventure_list', direction='outgoing')`",
               'answer': '`display_adventure_list()` in `src/game_workflows/game.py` calls:\n'
                         '1. `load_available_adventures()` (`loaders.py:43`)\n'
                         "2. `initialize_adventure_state(uuid)` (`game.py:53`, when continue button '🎮' is clicked)\n"
                         '3. `start_adventure()` (`core.py:54`, after initializing adventure state)\n'
                         "4. `delete_history_file(uuid=uuid)` (`loaders.py:57`, when delete button '🗑️' is clicked)\n"
                         '5. `st.rerun()` (`game.py:59`)',
               'verification_target': 'Adventure card click callbacks.'},
    'Q28': {   'id': 'Q28',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What does `initialize_adventure_state()` invoke?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='initialize_adventure_state', "
                             "direction='outgoing')`",
               'answer': '`initialize_adventure_state(uuid)` in `src/game_workflows/game.py` calls:\n'
                         '1. `load_adventure(uuid=uuid)` (`src/game_workflows/loaders.py:63`)\n'
                         '2. `st.rerun()` (`game.py:67`)',
               'verification_target': 'State restore + rerun loop.'},
    'Q29': {   'id': 'Q29',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What functions does `manage_models()` call?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='manage_models', direction='outgoing')`",
               'answer': '`manage_models()` in `src/imports/model.py` calls:\n'
                         '1. `list_ollama_models()` (`model.py:46`, inner function querying `/api/tags`)\n'
                         '2. `OllamaApi(model=dm_model)` (`src/api_workflows/call_api.py:63`)\n'
                         '3. `HuggingFaceEmbeddings(model_name=embedding_model)` (`langchain_huggingface:65`)\n'
                         '4. `initialize_rag()` (`model.py:67`)\n'
                         '5. `initialize_history()` (`model.py:68`)',
               'verification_target': 'Model setup side effects.'},
    'Q30': {   'id': 'Q30',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What downstream functions does `test_model_availability()` call?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='test_model_availability', "
                             "direction='outgoing')`",
               'answer': '`test_model_availability()` in `src/utils.py` calls:\n'
                         '1. `check_ollama_availability()` (`utils.py:22`)\n'
                         "2. `st.rerun()` (`utils.py:27`, when 'Retry Connection' button is clicked)",
               'verification_target': 'Error boundary branching.'},
    'Q31': {   'id': 'Q31',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What calls are made inside `check_ollama_availability()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='check_ollama_availability', "
                             "direction='outgoing')`",
               'answer': '`check_ollama_availability()` in `src/utils.py` calls:\n'
                         '1. `requests.get()` (`utils.py:14`) targeting '
                         '`http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/version` with a `timeout=5`.',
               'verification_target': 'HTTP request leaf node.'},
    'Q32': {   'id': 'Q32',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What outgoing calls does `OllamaApi.start_adventure()` make?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='start_adventure', direction='outgoing')`",
               'answer': '`OllamaApi.start_adventure()` in `src/api_workflows/call_api.py` calls:\n'
                         '1. `ChatPromptTemplate.from_template(template)` (`call_api.py:45`)\n'
                         '2. `load_characters()` (`src/game_workflows/loaders.py:49`)\n'
                         '3. `chain.stream(...)` (`call_api.py:54`) where `chain = prompt | self.llm`',
               'verification_target': 'LangChain LCEL streaming pipe.'},
    'Q33': {   'id': 'Q33',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What does `OllamaApi.progress_story()` call during its execution?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='progress_story', direction='outgoing')`",
               'answer': '`OllamaApi.progress_story()` in `src/api_workflows/call_api.py` calls:\n'
                         '1. `get_input()` (`call_api.py:156`, inner helper formatting player inputs)\n'
                         '2. `get_history()` (`call_api.py:157`, inner helper performing vector retrieval)\n'
                         '3. `st.session_state.embedding_model.embed_query()` (`call_api.py:82`)\n'
                         '4. `st.session_state.history_store.similarity_search_by_vector_with_relevance_scores()` '
                         '(`call_api.py:81`)\n'
                         '5. `create_history_aware_retriever()` (`call_api.py:128`)\n'
                         '6. `create_stuff_documents_chain()` (`call_api.py:150`)\n'
                         '7. `create_retrieval_chain()` (`call_api.py:153`)\n'
                         '8. `rag_chain.stream()` (`call_api.py:159`)',
               'verification_target': 'Historical RAG retrieval loop.'},
    'Q34': {   'id': 'Q34',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What downstream functions are executed inside `dm_turn()` in `adventure.py`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='dm_turn', direction='outgoing')`",
               'answer': '`dm_turn()` in `src/game_workflows/adventure.py` calls:\n'
                         '1. `vector_store.similarity_search()` (`adventure.py:18`)\n'
                         '2. `api_call()` (`adventure.py:21`, note: `api_call` is an invalid import that does not '
                         'exist in `call_api.py`)',
               'verification_target': 'Standalone module callee resolution.'},
    'Q35': {   'id': 'Q35',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What functions are called by `start_new_adventure()` in `adventure.py`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='start_new_adventure', direction='outgoing')`",
               'answer': '`start_new_adventure()` in `src/game_workflows/adventure.py` calls:\n'
                         '1. `api_call()` (`adventure.py:6`, note: `api_call` does not exist in `call_api.py`)',
               'verification_target': 'Leaf test for orphan module.'},
    'Q36': {   'id': 'Q36',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What outgoing functions does `save_adventure()` call?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='save_adventure', direction='outgoing')`",
               'answer': '`save_adventure()` in `src/game_workflows/loaders.py` calls:\n'
                         '1. `os.path.join()` (`loaders.py:48, 51, 55, 60`)\n'
                         '2. `os.makedirs(req_path, exist_ok=True)` (`loaders.py:49`)\n'
                         '3. `pickle.dump()` (`loaders.py:53, 62`)\n'
                         '4. `json.dump()` (`loaders.py:57`)',
               'verification_target': 'File serialization leaf operations.'},
    'Q37': {   'id': 'Q37',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What calls are made inside `display_updated_status_sidebar()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='display_updated_status_sidebar', "
                             "direction='outgoing')`",
               'answer': '`display_updated_status_sidebar()` in `main.py` calls:\n'
                         '1. `check_ollama_availability()` (`src/utils.py:29`)\n'
                         '2. `system_status.write()` (`main.py:28`)\n'
                         '3. `ollama_placeholder.write()` (`main.py:30`)\n'
                         '4. `model_placeholder.write()` (`main.py:31`)\n'
                         '5. `rag_placeholder.write()` (`main.py:33`)',
               'verification_target': 'Streamlit placeholder update sequence.'},
    'Q38': {   'id': 'Q38',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What does `initialise_adventure_session_state()` call?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='initialise_adventure_session_state', "
                             "direction='outgoing')`",
               'answer': '`initialise_adventure_session_state()` in `src/game_workflows/core.py` does not invoke '
                         'external functions; it reads and sets Streamlit session state keys:\n'
                         '- `st.session_state["has_adventure_started"]` (line 17)\n'
                         '- `st.session_state["chat_history"]` (line 19)\n'
                         "- `st.session_state['adventure_dict']` (line 21)\n"
                         '- `st.session_state["characters_in_adventure"]` (line 23)',
               'verification_target': 'Pure state mutating leaf node.'},
    'Q39': {   'id': 'Q39',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What functions does `reset_old_games()` invoke?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='reset_old_games', direction='outgoing')`",
               'answer': '`reset_old_games()` in `src/game_workflows/game.py` does not call external functions; it '
                         'purges state keys from `st.session_state`:\n'
                         '- `del st.session_state["has_adventure_started"]` (line 72)\n'
                         '- `del st.session_state["chat_history"]` (line 74)\n'
                         '- `del st.session_state["characters_in_adventure"]` (line 76)',
               'verification_target': 'Dictionary key deletion leaf node.'},
    'Q40': {   'id': 'Q40',
               'category': 'Category 2: Downstream Callees & Execution Trees',
               'question': 'What LangChain library functions are called by `OllamaApi.__init__()`?',
               'tool_chain': "`tool_traverse_call_graph(target_symbol='__init__', direction='outgoing')`",
               'answer': '`OllamaApi.__init__()` in `src/api_workflows/call_api.py` instantiates:\n'
                         '1. `OllamaLLM(model=model, temperature=temperature)` (`call_api.py:17`)\n'
                         '2. `RecursiveCharacterTextSplitter(chunk_size=1100, chunk_overlap=100)` (`call_api.py:18`)',
               'verification_target': 'Library constructor call detection.\n\n---'},
    'Q41': {   'id': 'Q41',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What will break if I modify `load_characters()` in `loaders.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='load_characters')`",
               'answer': 'Modifying `load_characters()` in `src/game_workflows/loaders.py` impacts 3 direct call '
                         'sites:\n'
                         '1. `display_character_list()` (`player.py:193`): breaks character listing and deletion in '
                         'the sidebar.\n'
                         '2. `start_adventure()` (`core.py:32`): breaks character selection validation and hero roster '
                         'loading.\n'
                         "3. `OllamaApi.start_adventure()` (`call_api.py:49`): breaks the Dungeon Master's ability to "
                         'inject character sheets into the LLM system prompt.\n'
                         'This ripples up to `play_game()` and `main()` in `main.py`.',
               'verification_target': 'Core data loader transitive blast radius.'},
    'Q42': {   'id': 'Q42',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius of changing `save_characters()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='save_characters')`",
               'answer': 'The blast radius of modifying `save_characters()` in `src/game_workflows/loaders.py` is '
                         'confined to `src/game_workflows/player.py`:\n'
                         '1. `create_character_form()` (line 179): saving newly created characters to '
                         '`characters.json` fails.\n'
                         '2. `display_character_list()` (line 203): updating `characters.json` when deleting a '
                         'character from the sidebar fails.',
               'verification_target': 'Form persistence impact.'},
    'Q43': {   'id': 'Q43',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the ripple effect if I alter `save_adventure()` in `loaders.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='save_adventure')`",
               'answer': 'Altering `save_adventure()` in `src/game_workflows/loaders.py` directly impacts '
                         '`src/game_workflows/core.py` at 3 invocation points:\n'
                         '1. Initial adventure creation (line 75)\n'
                         '2. Player turn submission (line 130)\n'
                         '3. DM narrative response completion (line 141)\n'
                         'Failure ripples downstream: `{uuid}.pkl`, `{uuid}_char.pkl`, and `history_ids.json` become '
                         'corrupted or unwritten, causing `load_adventure()` and `display_adventure_list()` in '
                         '`game.py` to fail when resuming saved campaigns.',
               'verification_target': 'Adventure persistence blast radius.'},
    'Q44': {   'id': 'Q44',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What breaks if I change the signature of `load_adventure()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='load_adventure')`",
               'answer': 'Changing the signature of `load_adventure(uuid)` in `src/game_workflows/loaders.py` breaks '
                         'its sole caller:\n'
                         '`initialize_adventure_state(uuid)` in `src/game_workflows/game.py:63`.\n'
                         "This prevents users from resuming any saved games via the '🎮' button in "
                         '`display_adventure_list()`.',
               'verification_target': 'Campaign resumption pipeline impact.'},
    'Q45': {   'id': 'Q45',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the impact of modifying `create_character_form()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='create_character_form')`",
               'answer': 'Modifying `create_character_form()` in `src/game_workflows/player.py` directly impacts:\n'
                         '1. Its caller `play_game()` in `src/game_workflows/game.py:35` when `character_creation` '
                         'mode is active.\n'
                         '2. The entire hero creation workflow: point-buy calculation (`calculate_points_spent`, '
                         '`update_ability_score`), equipment selection (`weapon_dict`, `armor_dict`), and character '
                         'saving (`save_characters`).',
               'verification_target': 'Sub-screen UI blast radius.'},
    'Q46': {   'id': 'Q46',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What will happen across the system if I modify `start_adventure()` in `core.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='start_adventure')`",
               'answer': 'Modifying `start_adventure()` in `src/game_workflows/core.py` impacts both entry points in '
                         '`src/game_workflows/game.py`:\n'
                         '1. `play_game()` (line 38) when starting a fresh adventure.\n'
                         '2. `display_adventure_list()` (line 54) when resuming an existing adventure.\n'
                         'It disrupts the core gameplay loop: chat turn progression, RAG vector store indexing, '
                         'character display, and session persistence.',
               'verification_target': 'Major game loop impact analysis.'},
    'Q47': {   'id': 'Q47',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius of modifying `OllamaApi.start_adventure()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='start_adventure')`",
               'answer': 'Modifying `OllamaApi.start_adventure()` in `src/api_workflows/call_api.py` directly '
                         'impacts:\n'
                         '`start_adventure()` in `src/game_workflows/core.py:51`.\n'
                         'It breaks the opening scene generation, party members introduction, difficulty prompt '
                         'formatting, and initial story chunk streaming.',
               'verification_target': 'API generator downstream blast radius.'},
    'Q48': {   'id': 'Q48',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius of modifying `OllamaApi.progress_story()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='progress_story')`",
               'answer': 'Modifying `OllamaApi.progress_story()` in `src/api_workflows/call_api.py` directly impacts:\n'
                         '`start_adventure()` in `src/game_workflows/core.py:122`.\n'
                         'It breaks player turn processing, semantic vector search against `history_store`, LangChain '
                         'history-aware retrieval, and turn-by-turn story continuation streaming.',
               'verification_target': 'Turn progression impact.'},
    'Q49': {   'id': 'Q49',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What will break if I modify `check_ollama_availability()` in `utils.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='check_ollama_availability')`",
               'answer': 'Modifying `check_ollama_availability()` in `src/utils.py` directly impacts 2 callers:\n'
                         '1. `display_updated_status_sidebar()` in `main.py:29` (status display in the sidebar).\n'
                         '2. `test_model_availability()` in `src/utils.py:22` (blocks page execution if Ollama is '
                         'offline).\n'
                         'Any malfunction will prevent users from accessing the app or incorrectly report Ollama as '
                         'offline.',
               'verification_target': 'Health check infrastructure impact.'},
    'Q50': {   'id': 'Q50',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the system-wide impact of changing `manage_models()` in `model.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='manage_models')`",
               'answer': 'The system-wide impact of changing `manage_models()` in `src/imports/model.py` affects:\n'
                         "`main()` in `main.py:56` when the user selects 'Manage Models'.\n"
                         'Because `manage_models()` initializes `st.session_state.dm_model`, `st.session_state.api`, '
                         '`st.session_state.embedding_model`, `st.session_state.vector_store`, and '
                         '`st.session_state.history_store`, breaking it halts model configuration and causes '
                         '`play_game()` to block with a configuration warning.',
               'verification_target': 'Configuration view impact.'},
    'Q51': {   'id': 'Q51',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What breaks if I modify `initialize_rag()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='initialize_rag')`",
               'answer': 'Modifying `initialize_rag()` in `src/imports/model.py` breaks:\n'
                         '1. `manage_models()` in `model.py:67` where `st.session_state.vector_store` is assigned.\n'
                         '2. `OllamaApi.progress_story()` in `call_api.py:129` where `st.session_state.vector_store` '
                         'is passed to `create_history_aware_retriever()`.\n'
                         'This breaks D&D rules handbook retrieval during gameplay.',
               'verification_target': 'ChromaDB RAG factory impact.'},
    'Q52': {   'id': 'Q52',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius of changing `initialize_history()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='initialize_history')`",
               'answer': 'The blast radius of changing `initialize_history()` in `src/imports/model.py` impacts:\n'
                         '1. `manage_models()` (`model.py:68`): sets `st.session_state.history_store`.\n'
                         '2. `OllamaApi.progress_story()` (`call_api.py:81`): performs historical similarity '
                         'searches.\n'
                         '3. `OllamaApi.save_doc_to_history_vector()` (`call_api.py:166`): writes turn documents to '
                         'history.\n'
                         '4. `delete_history_file()` (`loaders.py:77, 81`): queries and deletes vector IDs from '
                         'history.',
               'verification_target': 'ChromaDB history store factory impact.'},
    'Q53': {   'id': 'Q53',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What will break if I modify `set_fantasy_theme()` in `theme.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='set_fantasy_theme')`",
               'answer': 'Modifying `set_fantasy_theme()` in `src/ui/theme.py` impacts only:\n'
                         '`main()` in `main.py:38`.\n'
                         'The blast radius is purely cosmetic (Cinzel font, gold text, burgundy buttons, dark sidebar '
                         'background) and has zero impact on application logic or game state.',
               'verification_target': 'Pure cosmetic blast radius.'},
    'Q54': {   'id': 'Q54',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the impact of modifying `delete_history_file()`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='delete_history_file')`",
               'answer': 'Modifying `delete_history_file()` in `src/game_workflows/loaders.py` impacts:\n'
                         '`display_adventure_list()` in `src/game_workflows/game.py:57`.\n'
                         'If broken, users cannot delete past campaigns, causing obsolete pickle files and orphaned '
                         'vector records to remain on disk and in ChromaDB.',
               'verification_target': 'Campaign deletion lifecycle.'},
    'Q55': {   'id': 'Q55',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What breaks if I change `play_game()` in `game.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='play_game')`",
               'answer': 'Changing `play_game()` in `src/game_workflows/game.py` breaks:\n'
                         '`main()` in `main.py:50`.\n'
                         'This disrupts the entire primary gameplay section, including character creation dispatch, '
                         'adventure launching, and game state initialization.',
               'verification_target': 'Screen controller blast radius.'},
    'Q56': {   'id': 'Q56',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the combined blast radius of modifying both `load_characters` and '
                           '`save_characters`?',
               'tool_chain': "`tool_calculate_blast_radius(changed_symbols=['load_characters', 'save_characters'])`",
               'answer': 'The combined blast radius of modifying both `load_characters` and `save_characters` in '
                         '`loaders.py` encompasses:\n'
                         '1. `create_character_form()` in `player.py:179` (saving new heroes)\n'
                         '2. `display_character_list()` in `player.py:193, 203` (displaying and deleting characters)\n'
                         '3. `start_adventure()` in `core.py:32` (selecting characters for campaigns)\n'
                         '4. `OllamaApi.start_adventure()` in `call_api.py:49` (DM prompt character injection)\n'
                         'It completely breaks character lifecycle management and party formation across the entire '
                         'system.',
               'verification_target': 'Multi-symbol composite blast radius.'},
    'Q57': {   'id': 'Q57',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius of modifying the constant dictionary `weapon_dict` in '
                           '`references.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='weapon_dict')`",
               'answer': 'Modifying `weapon_dict` in `src/game_workflows/references.py` is isolated to:\n'
                         '`src/game_workflows/player.py:7, 114-117` inside `create_character_form()`.\n'
                         'It alters weapon categories, weapon dropdown options, and weapon damage descriptions in '
                         'character creation.',
               'verification_target': 'Static reference dictionary impact.'},
    'Q58': {   'id': 'Q58',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius of changing `armor_dict` in `references.py`?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='armor_dict')`",
               'answer': 'Modifying `armor_dict` in `src/game_workflows/references.py` is isolated to:\n'
                         '`src/game_workflows/player.py:7, 130-135` inside `create_character_form()`.\n'
                         'It alters armor categories, armor dropdown options, and armor class (AC) details in '
                         'character creation.',
               'verification_target': 'Static reference dictionary impact.'},
    'Q59': {   'id': 'Q59',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'If I modify `start_new_adventure()` in `adventure.py`, what breaks in the active app?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='start_new_adventure')`",
               'answer': 'Modifying `start_new_adventure()` in `src/game_workflows/adventure.py` causes **0 breaks in '
                         'the active application**.\n'
                         '`adventure.py` is completely dead code and is never imported or invoked anywhere in the '
                         'active application.',
               'verification_target': 'Zero-caller orphan blast radius verification.'},
    'Q60': {   'id': 'Q60',
               'category': 'Category 3: Blast Radius & Impact Analysis',
               'question': 'What is the blast radius if I refactor the `OllamaApi` class constructor?',
               'tool_chain': "`tool_calculate_blast_radius(target_symbol='OllamaApi')`",
               'answer': 'Refactoring the constructor of `OllamaApi` in `src/api_workflows/call_api.py` impacts:\n'
                         '`manage_models()` in `src/imports/model.py:63-64` (`st.session_state.api = '
                         'OllamaApi(model=dm_model)`).\n'
                         'If this fails, `st.session_state.api` will not be instantiated, causing crashes when '
                         '`start_adventure()` in `core.py` attempts to invoke API methods.',
               'verification_target': 'Class instantiation blast radius.\n\n---'},
    'Q61': {   'id': 'Q61',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What is the point cost for an ability score of 15 in `calculate_point_cost`?',
               'tool_chain': "1. `tool_get_symbol_code_snippet(symbol_name='calculate_point_cost')` $\\rightarrow$ 0 "
                             'results\n'
                             '  2. Evaluator triggers **Case B** $\\rightarrow$ Sibling retry: '
                             '`tool_search_codebase_semantic("calculate_point_cost")`\n'
                             '  3. Matches `calculate_points_spent(score)` in `src/game_workflows/player.py:24-26`',
               'answer': 'The symbol `calculate_point_cost` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `calculate_points_spent(score)` in '
                         '`src/game_workflows/player.py:24-26`.\n'
                         'The calculation formula is `return score - 8`.\n'
                         'For an ability score of 15: `15 - 8 = 7` points.',
               'verification_target': 'Case B recovery from typo in function name.'},
    'Q62': {   'id': 'Q62',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Who calls `load_character()` in the codebase?',
               'tool_chain': "1. `tool_traverse_call_graph(target_symbol='load_character')` $\\rightarrow$ 0 callers\n"
                             '  2. Evaluator Case B $\\rightarrow$ Semantic search finds `load_characters`\n'
                             '  3. Resolves callers of `load_characters`',
               'answer': 'The symbol `load_character()` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `load_characters()` in '
                         '`src/game_workflows/loaders.py:12-16`.\n'
                         'Its callers are:\n'
                         '1. `display_character_list()` in `src/game_workflows/player.py:193`\n'
                         '2. `start_adventure()` in `src/game_workflows/core.py:32`\n'
                         '3. `OllamaApi.start_adventure()` in `src/api_workflows/call_api.py:49`',
               'verification_target': 'Singular vs plural symbol typo recovery.'},
    'Q63': {   'id': 'Q63',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Where is `check_ollama_status` defined and what does it check?',
               'tool_chain': '1. Snippet for `check_ollama_status` $\\rightarrow$ 0 results\n'
                             '  2. Case B Fallback finds `check_ollama_availability` in `src/utils.py:12`',
               'answer': 'The symbol `check_ollama_status` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `check_ollama_availability()` in `src/utils.py:12-18`.\n'
                         'It performs an HTTP GET request to `http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/version` with '
                         '`timeout=5` and returns `True` if `status_code == 200`, otherwise `False`.',
               'verification_target': 'Semantic synonym typo recovery (`status` vs `availability`).'},
    'Q64': {   'id': 'Q64',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What does `save_character()` do?',
               'tool_chain': '1. Snippet lookup fails\n'
                             '  2. Case B Fallback resolves `save_characters(characters)` in '
                             '`src/game_workflows/loaders.py:19`',
               'answer': 'The symbol `save_character()` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `save_characters(characters)` in '
                         '`src/game_workflows/loaders.py:19-21`.\n'
                         'It dumps the `characters` dictionary to `CHARACTERS_FILE` (`characters.json`) with '
                         '`indent=4` using `json.dump`.',
               'verification_target': 'Singular vs plural write function recovery.'},
    'Q65': {   'id': 'Q65',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What parameters are required for `load_adventure_file`?',
               'tool_chain': '1. Lookup fails $\\rightarrow$ Case B resolves `load_adventure(uuid)` in `loaders.py:24`',
               'answer': 'The symbol `load_adventure_file` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `load_adventure(uuid)` in '
                         '`src/game_workflows/loaders.py:24-36`.\n'
                         'It requires exactly one parameter: `uuid` (str).',
               'verification_target': 'Suffix mismatch recovery (`_file` suffix).'},
    'Q66': {   'id': 'Q66',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Show me the implementation of `delete_history` in `loaders.py`.',
               'tool_chain': '1. Lookup fails $\\rightarrow$ Case B resolves `delete_history_file(uuid)` in '
                             '`loaders.py:72`',
               'answer': 'The symbol `delete_history` does not exist in `loaders.py`.\n'
                         'The near-miss resolved symbol is `delete_history_file(uuid)` in '
                         '`src/game_workflows/loaders.py:72-91`.\n'
                         "It removes the uuid entry from `st.session_state['adventure_dict']`, deletes matching vector "
                         'records from `st.session_state.history_store`, unlinks `{uuid}.pkl` and `{uuid}_char.pkl` '
                         'from disk, and calls `update_history_ids()`.',
               'verification_target': 'Truncated function name recovery.'},
    'Q67': {   'id': 'Q67',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Where is `reset_game()` called?',
               'tool_chain': '1. Call graph fails $\\rightarrow$ Case B resolves `reset_old_games()` in '
                             '`src/game_workflows/game.py:70`',
               'answer': 'The symbol `reset_game()` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `reset_old_games()` in `src/game_workflows/game.py:70-77`.\n'
                         "It is called in `play_game()` at line 30 when the user clicks '🏞️ Start Adventure'.",
               'verification_target': 'Verb-noun mismatch recovery (`reset_game` vs `reset_old_games`).'},
    'Q68': {   'id': 'Q68',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What does `initialize_theme()` do?',
               'tool_chain': '1. Snippet fails $\\rightarrow$ Case B resolves `set_fantasy_theme()` in '
                             '`src/ui/theme.py:4`',
               'answer': 'The symbol `initialize_theme()` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `set_fantasy_theme()` in `src/ui/theme.py:3-13`.\n'
                         "It injects custom CSS styling and the Google Font 'Cinzel' into Streamlit using "
                         '`st.markdown(..., unsafe_allow_html=True)`.',
               'verification_target': 'Semantic action mismatch (`initialize` vs `set`).'},
    'Q69': {   'id': 'Q69',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Where is `initialise_adventure_state` defined?',
               'tool_chain': '1. Lookup fails $\\rightarrow$ Case B resolves `initialise_adventure_session_state()` in '
                             '`core.py:15` or `initialize_adventure_state(uuid)` in `game.py:62`',
               'answer': 'The symbol `initialise_adventure_state` matches two resolved symbols:\n'
                         '1. `initialise_adventure_session_state()` in `src/game_workflows/core.py:16-24` (initializes '
                         'adventure session keys).\n'
                         '2. `initialize_adventure_state(uuid)` in `src/game_workflows/game.py:62-68` (loads saved '
                         'adventure state from disk and triggers `st.rerun()`).',
               'verification_target': 'Disambiguating regional spelling variations (`initialise` vs `initialize`).'},
    'Q70': {   'id': 'Q70',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What does `fetch_available_adventures` return?',
               'tool_chain': '1. Lookup fails $\\rightarrow$ Case B resolves `load_available_adventures()` in '
                             '`loaders.py:39`',
               'answer': 'The symbol `fetch_available_adventures` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `load_available_adventures()` in '
                         '`src/game_workflows/loaders.py:39-44`.\n'
                         'It returns a dictionary mapping adventure UUIDs to their titles parsed from '
                         '`history_ids.json`, or `{}` if the file does not exist.',
               'verification_target': 'Synonym action recovery (`fetch` vs `load`).'},
    'Q71': {   'id': 'Q71',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What is the timeout value in `verify_ollama`?',
               'tool_chain': '1. Snippet fails $\\rightarrow$ Case B resolves `check_ollama_availability` in '
                             '`utils.py:15`',
               'answer': 'The symbol `verify_ollama` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `check_ollama_availability()` in `src/utils.py:12-18`.\n'
                         'The timeout value is `timeout=5` (5 seconds).',
               'verification_target': 'Conceptual function lookup to extract parameter value.'},
    'Q72': {   'id': 'Q72',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What does `update_history()` in `loaders.py` update?',
               'tool_chain': '1. Lookup fails $\\rightarrow$ Case B resolves `update_history_ids()` in `loaders.py:65`',
               'answer': 'The symbol `update_history()` does not exist in `loaders.py`.\n'
                         'The near-miss resolved symbol is `update_history_ids()` in '
                         '`src/game_workflows/loaders.py:65-69`.\n'
                         "It dumps `st.session_state['adventure_dict']` into the JSON file "
                         '`os.path.join(HISTORY_DB_DIR, "HIST", "history_ids.json")`.',
               'verification_target': 'Near-miss suffix recovery.'},
    'Q73': {   'id': 'Q73',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What is the chunk size in `OllamaApi` text splitter?',
               'tool_chain': '1. Snippet for `OllamaApi.__init__` in `call_api.py:18`',
               'answer': 'In `OllamaApi.__init__()` (`src/api_workflows/call_api.py:18-19`), `self.text_splitter` is '
                         'instantiated as:\n'
                         '`RecursiveCharacterTextSplitter(chunk_size=1100, chunk_overlap=100)`.\n'
                         'The chunk size is `1100` characters (with an overlap of `100` characters).',
               'verification_target': 'Inner attribute value extraction.'},
    'Q74': {   'id': 'Q74',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Where is `CHARACTER_FILE_PATH` defined?',
               'tool_chain': '1. Env var query fails $\\rightarrow$ Case B resolves `CHARACTERS_FILE` in '
                             '`loaders.py:8`',
               'answer': 'The symbol `CHARACTER_FILE_PATH` does not exist in the codebase.\n'
                         'The near-miss resolved constant is `CHARACTERS_FILE` defined in '
                         '`src/game_workflows/loaders.py:8`:\n'
                         '`CHARACTERS_FILE = os.getenv("CHARACTERS_FILE", "characters.json")`.',
               'verification_target': 'Environment variable typo recovery.'},
    'Q75': {   'id': 'Q75',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What is the default value of `TOTAL_POINTS` in character creation?',
               'tool_chain': '1. State query fails $\\rightarrow$ Case B resolves `TOTAL_SKILL_POINTS` in '
                             '`player.py:11`',
               'answer': 'The symbol `TOTAL_POINTS` does not exist in character creation.\n'
                         'The near-miss resolved constant is `TOTAL_SKILL_POINTS` in '
                         '`src/game_workflows/player.py:12`:\n'
                         '`TOTAL_SKILL_POINTS = int(os.getenv("TOTAL_MAX_POINTS_AT_START", 27))`.\n'
                         'The default value is `27`.',
               'verification_target': 'Near-miss global variable resolution.'},
    'Q76': {   'id': 'Q76',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What does `format_adventure_name` do?',
               'tool_chain': '1. Snippet fails $\\rightarrow$ Case B resolves `name_adventure` in `call_api.py:57`',
               'answer': 'The symbol `format_adventure_name` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `OllamaApi.name_adventure(self, adventure: str) -> str` in '
                         '`src/api_workflows/call_api.py:57-72`.\n'
                         'It invokes the LLM with a template asking the DM to name the D&D session based on initial '
                         'text without quotation marks.',
               'verification_target': 'Verb-noun near-miss mapping.'},
    'Q77': {   'id': 'Q77',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What does `save_vector_doc` in `call_api.py` do?',
               'tool_chain': '1. Snippet fails $\\rightarrow$ Case B resolves `save_doc_to_history_vector` in '
                             '`call_api.py`',
               'answer': 'The symbol `save_vector_doc` does not exist in `call_api.py`.\n'
                         'The near-miss resolved symbol is `OllamaApi.save_doc_to_history_vector(self, doc: Document) '
                         '-> None` in `src/api_workflows/call_api.py:163-167`.\n'
                         'It chunks `doc` via `self.text_splitter.split_documents([doc])` and persists them to '
                         '`st.session_state.history_store.add_documents()`.',
               'verification_target': 'Method name truncation recovery.'},
    'Q78': {   'id': 'Q78',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Where is `weapon_dictionary` defined?',
               'tool_chain': '1. Variable query fails $\\rightarrow$ Case B resolves `weapon_dict` in '
                             '`references.py:1`',
               'answer': 'The symbol `weapon_dictionary` does not exist.\n'
                         'The near-miss resolved symbol is `weapon_dict` defined in '
                         '`src/game_workflows/references.py:1-47`.\n'
                         "It maps weapon categories ('Simple Melee', 'Simple Ranged', 'Martial Melee', 'Martial "
                         "Ranged') to weapon names and stats.",
               'verification_target': 'Dictionary name abbreviation recovery.'},
    'Q79': {   'id': 'Q79',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'Where is `armor_list` defined?',
               'tool_chain': '1. Variable query fails $\\rightarrow$ Case B resolves `armor_dict` in '
                             '`references.py:46`',
               'answer': 'The symbol `armor_list` does not exist.\n'
                         'The near-miss resolved symbol is `armor_dict` defined in '
                         '`src/game_workflows/references.py:49-74`.\n'
                         "It maps armor categories ('Light Armor', 'Medium Armor', 'Heavy Armor', 'Shield') to "
                         'specific armor pieces and stats.',
               'verification_target': 'Data structure type typo recovery (`list` vs `dict`).'},
    'Q80': {   'id': 'Q80',
               'category': 'Category 4: Deliberate Typos & Near-Miss Symbols (Case B Fallback)',
               'question': 'What is the return value of `get_points_spent`?',
               'tool_chain': '1. Snippet fails $\\rightarrow$ Case B resolves `calculate_points_spent(score)` in '
                             '`player.py:24`',
               'answer': 'The symbol `get_points_spent` does not exist in the codebase.\n'
                         'The near-miss resolved symbol is `calculate_points_spent(score)` in '
                         '`src/game_workflows/player.py:24-26`.\n'
                         'It returns `score - 8` (representing point-buy cost relative to base score 8).',
               'verification_target': 'Near-miss arithmetic function recovery.\n\n---'},
    'Q81': {   'id': 'Q81',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `st.session_state.ability_scores` read and updated?',
               'tool_chain': '',
               'answer': '`st.session_state.ability_scores` is accessed exclusively in '
                         '`src/game_workflows/player.py`:\n'
                         '- Initialized: `initialize_session_state()` (`player.py:19-20`) to `{ability: 8 for ability '
                         'in [...]}`.\n'
                         '- Read: `update_ability_score()` (`player.py:29`), ability score input render '
                         '(`player.py:73`), character save dictionary (`player.py:169`), and `reset_character_form()` '
                         '(`player.py:39`).\n'
                         '- Updated: `update_ability_score()` (`player.py:35`) and `reset_character_form()` '
                         '(`player.py:39`).',
               'verification_target': 'AST `STATE_READS` / `STATE_WRITES` edges.'},
    'Q82': {   'id': 'Q82',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Which functions mutate `st.session_state.remaining_points`?',
               'tool_chain': '',
               'answer': '`st.session_state.remaining_points` is mutated by 3 functions in '
                         '`src/game_workflows/player.py`:\n'
                         '1. `initialize_session_state()` (line 22): initializes to `TOTAL_SKILL_POINTS` (27).\n'
                         '2. `update_ability_score()` (line 36): updates via `st.session_state.remaining_points += '
                         'old_points - new_points`.\n'
                         '3. `reset_character_form()` (line 41): resets back to `TOTAL_SKILL_POINTS`.',
               'verification_target': 'State delta mutation tracking.'},
    'Q83': {   'id': 'Q83',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where in the codebase is `st.session_state.dm_model` initialized and read?',
               'tool_chain': '',
               'answer': '`st.session_state.dm_model` is:\n'
                         '- Initialized/Written: in `manage_models()` (`src/imports/model.py:62`) when user clicks '
                         "'Save Model Selections'.\n"
                         '- Read: in `play_game()` (`src/game_workflows/game.py:17`) to check if model configuration '
                         'exists, and in `manage_models()` (`model.py:57`) to preserve dropdown selection.',
               'verification_target': 'Cross-file session state propagation.'},
    'Q84': {   'id': 'Q84',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'What functions access `st.session_state.vector_store`?',
               'tool_chain': '',
               'answer': '`st.session_state.vector_store` is accessed by:\n'
                         '1. `manage_models()` (`src/imports/model.py:67`): initialized by calling '
                         '`initialize_rag()`.\n'
                         '2. `play_game()` (`src/game_workflows/game.py:17`): validated at startup.\n'
                         '3. `OllamaApi.progress_story()` (`src/api_workflows/call_api.py:129`): passed to '
                         '`create_history_aware_retriever`.',
               'verification_target': 'Vector store reference mapping.'},
    'Q85': {   'id': 'Q85',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Which functions reference or mutate `st.session_state.history_store`?',
               'tool_chain': '',
               'answer': '`st.session_state.history_store` is accessed by:\n'
                         '1. `manage_models()` (`src/imports/model.py:68`): initialized with `initialize_history()`.\n'
                         '2. `play_game()` (`src/game_workflows/game.py:17`): validated in session check.\n'
                         '3. `OllamaApi.progress_story()` (`src/api_workflows/call_api.py:81`): queried for similar '
                         'documents with relevance scores.\n'
                         '4. `OllamaApi.save_doc_to_history_vector()` (`call_api.py:166`): documents added via '
                         '`add_documents()`.\n'
                         '5. `delete_history_file()` (`src/game_workflows/loaders.py:77, 81`): queried and deleted by '
                         'UUID.',
               'verification_target': 'History vector store audit.'},
    'Q86': {   'id': 'Q86',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `st.session_state.chat_history` modified?',
               'tool_chain': '',
               'answer': '`st.session_state.chat_history` is modified in `src/game_workflows/core.py` and '
                         '`src/game_workflows/game.py`:\n'
                         '- Initialized: `initialise_adventure_session_state()` (`core.py:19`) to `[]`.\n'
                         '- Appended: `start_adventure()` (`core.py:70` with initial DM intro, line 116 with player '
                         'prompts, line 136 with DM story progress).\n'
                         '- Deleted: `reset_old_games()` (`game.py:74`) via `del st.session_state["chat_history"]`.',
               'verification_target': 'Conversation history mutation sites.'},
    'Q87': {   'id': 'Q87',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'What functions read or write `st.session_state.characters_in_adventure`?',
               'tool_chain': '',
               'answer': '`st.session_state.characters_in_adventure` is accessed in:\n'
                         '- Initialized: `initialise_adventure_session_state()` (`core.py:23`) to `[]`.\n'
                         '- Written: `start_adventure()` (`core.py:35` from character selectbox).\n'
                         '- Read: `start_adventure()` (`core.py:51, 87`) and `initialize_adventure_state()` '
                         '(`game.py:65`).\n'
                         '- Deleted: `reset_old_games()` (`game.py:76`).',
               'verification_target': 'Multi-hero session state audit.'},
    'Q88': {   'id': 'Q88',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `st.session_state.adventure_dict` modified?',
               'tool_chain': '',
               'answer': '`st.session_state.adventure_dict` is modified in:\n'
                         '- Initialized: `initialise_adventure_session_state()` (`core.py:21`) to `{}`.\n'
                         '- Updated: `start_adventure()` (`core.py:73` sets '
                         '`st.session_state.adventure_dict[adventure_uuid] = adventure_name`).\n'
                         '- Mutated: `delete_history_file()` (`loaders.py:73` deletes `del '
                         "st.session_state['adventure_dict'][uuid]`).\n"
                         '- Read: `update_history_ids()` (`loaders.py:69`) to dump to `history_ids.json`.',
               'verification_target': 'Persistent adventure index dictionary tracking.'},
    'Q89': {   'id': 'Q89',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Which functions read or write `st.session_state.has_adventure_started`?',
               'tool_chain': '',
               'answer': '`st.session_state.has_adventure_started` is accessed in:\n'
                         '- Initialized: `initialise_adventure_session_state()` (`core.py:17`) to `False`.\n'
                         '- Read: `start_adventure()` (`core.py:44`) to determine whether to display the start form or '
                         'the active gameplay chat.\n'
                         '- Written: `start_adventure()` (`core.py:76`) set to `True`.\n'
                         '- Deleted: `reset_old_games()` (`game.py:72`).',
               'verification_target': 'Adventure lifecycle boolean flag.'},
    'Q90': {   'id': 'Q90',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `st.session_state.current_uuid` set and read?',
               'tool_chain': '',
               'answer': '`st.session_state.current_uuid` is:\n'
                         '- Set: in `start_adventure()` (`core.py:46`) using `str(uuid.uuid4())`, and in '
                         '`initialize_adventure_state()` (`game.py:66`) from saved campaign ID.\n'
                         '- Read: in `start_adventure()` (`core.py:71, 75, 130, 132, 141, 143`) and in '
                         '`OllamaApi.progress_story()` (`call_api.py:86`) as a vector search filter.',
               'verification_target': 'Session UUID lifecycle.'},
    'Q91': {   'id': 'Q91',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'What functions read or mutate `st.session_state.character_creation`?',
               'tool_chain': '',
               'answer': '`st.session_state.character_creation` is mutated and read in `src/game_workflows/game.py`:\n'
                         '- Initialized: `initialize_session_state()` (line 10) to `False`.\n'
                         "- Set to `True`: `play_game()` (line 27) when clicking '🪄 Create a Character'.\n"
                         "- Set to `False`: `play_game()` (line 31) when clicking '🏞️ Start Adventure'.\n"
                         '- Read: `play_game()` (line 34) to render `create_character_form()`.',
               'verification_target': 'View toggle flag audit.'},
    'Q92': {   'id': 'Q92',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `st.session_state.character_created` used?',
               'tool_chain': '',
               'answer': '`st.session_state.character_created` is initialized in '
                         '`src/game_workflows/player.py:16-17`:\n'
                         "`if 'character_created' not in st.session_state: st.session_state.character_created = "
                         'False`\n'
                         'It is **never read or modified anywhere else** in the codebase (it is an orphaned/dead state '
                         'variable).',
               'verification_target': 'Dead state variable detection.'},
    'Q93': {   'id': 'Q93',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'What files and functions reference `st.session_state.game_state`?',
               'tool_chain': '',
               'answer': '`st.session_state.game_state` is referenced exclusively in `src/game_workflows/game.py`:\n'
                         '- Initialized: `initialize_session_state()` (lines 12-13) as `{"state": False}`.\n'
                         '- Mutated: `play_game()` lines 26 (`["state"] = False`) and 32 (`["state"] = True`).\n'
                         "- Read: `play_game()` line 37 (`if st.session_state['game_state']['state']: "
                         'start_adventure()`).',
               'verification_target': 'State dictionary references.'},
    'Q94': {   'id': 'Q94',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `st.session_state.page` set and checked?',
               'tool_chain': '',
               'answer': '`st.session_state.page` is **not used anywhere in the codebase**.\n'
                         'Page routing is managed by the local variable `page = st.sidebar.radio("Go to", ["Play '
                         'Game", "Manage Models"])` in `main.py:48`.',
               'verification_target': 'Main router state flag.'},
    'Q95': {   'id': 'Q95',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'What functions read or write `st.session_state.api`?',
               'tool_chain': '',
               'answer': '`st.session_state.api` is:\n'
                         '- Written: `manage_models()` in `src/imports/model.py:63-64` (`st.session_state.api = '
                         'OllamaApi(model=dm_model)`).\n'
                         '- Read: `start_adventure()` in `src/game_workflows/core.py` at lines 51, 57, 71, 122, 132, '
                         '143.',
               'verification_target': 'Class instance session reference.'},
    'Q96': {   'id': 'Q96',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Which methods read `st.session_state.embedding_model`?',
               'tool_chain': '',
               'answer': '`st.session_state.embedding_model` is read by 3 functions:\n'
                         '1. `initialize_rag()` in `src/imports/model.py:22`\n'
                         '2. `initialize_history()` in `src/imports/model.py:29`\n'
                         '3. `OllamaApi.progress_story()` in `src/api_workflows/call_api.py:82`',
               'verification_target': 'Embedder instance reference audit.'},
    'Q97': {   'id': 'Q97',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `TOTAL_SKILL_POINTS` declared and where is it referenced?',
               'tool_chain': '',
               'answer': '`TOTAL_SKILL_POINTS` is:\n'
                         '- Declared: `src/game_workflows/player.py:12`:\n'
                         '  `TOTAL_SKILL_POINTS = int(os.getenv("TOTAL_MAX_POINTS_AT_START", 27))`\n'
                         '- Referenced: in `player.py:22` (`initialize_session_state`) and `player.py:41` '
                         '(`reset_character_form`).',
               'verification_target': 'Module constant reference tracking.'},
    'Q98': {   'id': 'Q98',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'What files access the global variable `TURN_LIMIT`?',
               'tool_chain': '',
               'answer': '`TURN_LIMIT` is loaded from the environment in 2 files:\n'
                         '1. `main.py:13`: `TURN_LIMIT = int(os.getenv("TURN_LIMIT", 10))`\n'
                         '2. `src/game_workflows/core.py:13`: `TURN_LIMIT = int(os.getenv("TURN_LIMIT", 10))`\n'
                         '(Neither file uses `TURN_LIMIT` in game execution logic).',
               'verification_target': 'Duplicate constant declaration across files.'},
    'Q99': {   'id': 'Q99',
               'category': 'Category 5: State & Variable Reference Audits',
               'question': 'Where is `OLLAMA_API_ENDPOINT` referenced across the codebase?',
               'tool_chain': '',
               'answer': '`OLLAMA_API_ENDPOINT` is referenced in 2 files:\n'
                         '1. `src/utils.py:9, 14`: defined at line 9 and queried in `check_ollama_availability()`.\n'
                         '2. `src/imports/model.py:13, 37`: defined at line 13 and queried in `list_ollama_models()`.',
               'verification_target': 'Constant URL usage audit.'},
    'Q100': {   'id': 'Q100',
                'category': 'Category 5: State & Variable Reference Audits',
                'question': 'Which functions read `CHARACTERS_FILE`?',
                'tool_chain': '',
                'answer': '`CHARACTERS_FILE` is read by 2 functions in `src/game_workflows/loaders.py`:\n'
                          '1. `load_characters()` (lines 13, 14)\n'
                          '2. `save_characters()` (line 20)',
                'verification_target': 'File path constant reference tracking.'},
    'Q101': {   'id': 'Q101',
                'category': 'Category 5: State & Variable Reference Audits',
                'question': 'What default value does `ability_scores` take when a character form is opened?',
                'tool_chain': '',
                'answer': 'When a character form is opened, `ability_scores` defaults to **8 for all six abilities**:\n'
                          '`{"Strength": 8, "Dexterity": 8, "Constitution": 8, "Intelligence": 8, "Wisdom": 8, '
                          '"Charisma": 8}`\n'
                          '(defined in `src/game_workflows/player.py:19-20`).',
                'verification_target': 'AST dictionary comprehension audit.'},
    'Q102': {   'id': 'Q102',
                'category': 'Category 5: State & Variable Reference Audits',
                'question': 'What is the maximum value permitted for an ability score in `create_character_form`?',
                'tool_chain': '',
                'answer': 'The maximum value permitted for an ability score in `create_character_form` is **15** '
                          '(`max_value=15` in `st.number_input()` at `src/game_workflows/player.py:74`).',
                'verification_target': 'AST widget argument extraction.'},
    'Q103': {   'id': 'Q103',
                'category': 'Category 5: State & Variable Reference Audits',
                'question': 'What is the minimum value permitted for an ability score in `create_character_form`?',
                'tool_chain': '',
                'answer': 'The minimum value permitted for an ability score in `create_character_form` is **8** '
                          '(`min_value=8` in `st.number_input()` at `src/game_workflows/player.py:73`).',
                'verification_target': 'AST widget argument extraction.'},
    'Q104': {   'id': 'Q104',
                'category': 'Category 5: State & Variable Reference Audits',
                'question': 'What races can a player select in `create_character_form`?',
                'tool_chain': '',
                'answer': 'A player can select from **7 races** in `create_character_form` '
                          '(`src/game_workflows/player.py:52-53`):\n'
                          '1. Human\n'
                          '2. Elf\n'
                          '3. Dwarf\n'
                          '4. Halfling\n'
                          '5. Gnome\n'
                          '6. Half-Orc\n'
                          '7. Tiefling',
                'verification_target': 'AST list extraction.'},
    'Q105': {   'id': 'Q105',
                'category': 'Category 5: State & Variable Reference Audits',
                'question': 'What character classes are available in `create_character_form`?',
                'tool_chain': '',
                'answer': 'A player can select from **7 classes** in `create_character_form` '
                          '(`src/game_workflows/player.py:55-56`):\n'
                          '1. Fighter\n'
                          '2. Wizard\n'
                          '3. Rogue\n'
                          '4. Cleric\n'
                          '5. Paladin\n'
                          '6. Ranger\n'
                          '7. Barbarian',
                'verification_target': 'AST list extraction.\n\n---'},
    'Q106': {   'id': 'Q106',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Where is `OLLAMA_HOST` read, and what is its default value?',
                'tool_chain': '',
                'answer': '`OLLAMA_HOST` is read in 3 files:\n'
                          '1. `main.py:11`\n'
                          '2. `src/utils.py:7`\n'
                          '3. `src/imports/model.py:11`\n'
                          "Its default fallback value is `'localhost'`.",
                'verification_target': 'Cross-file env var consistency.'},
    'Q107': {   'id': 'Q107',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Which files access the environment variable `OLLAMA_PORT`?',
                'tool_chain': '',
                'answer': '`OLLAMA_PORT` is accessed in 3 files:\n'
                          '1. `main.py:12`\n'
                          '2. `src/utils.py:8`\n'
                          '3. `src/imports/model.py:12`\n'
                          'Its default fallback value is `"11434"`.',
                'verification_target': 'Env var audit.'},
    'Q108': {   'id': 'Q108',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What files and functions read `CHARACTERS_FILE` via `os.getenv`?',
                'tool_chain': '',
                'answer': '`CHARACTERS_FILE` is read via `os.getenv` exclusively in:\n'
                          '`src/game_workflows/loaders.py:8`:\n'
                          '`CHARACTERS_FILE = os.getenv("CHARACTERS_FILE", "characters.json")`.',
                'verification_target': 'Storage configuration audit.'},
    'Q109': {   'id': 'Q109',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Where is `HISTORY_DB_DIR` read in the repository?',
                'tool_chain': '',
                'answer': '`HISTORY_DB_DIR` is read in 2 files:\n'
                          '1. `src/game_workflows/loaders.py:9`: `HISTORY_DB_DIR = os.getenv("HISTORY_DB_DIR", '
                          '"./history")`\n'
                          '2. `src/imports/model.py:16`: `HISTORY_DB_DIR = os.getenv("HISTORY_DB_DIR", "./history")`',
                'verification_target': 'History storage env var audit.'},
    'Q110': {   'id': 'Q110',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Which file reads `CHROMA_DB_DIR` and what is its default fallback directory?',
                'tool_chain': '',
                'answer': '`CHROMA_DB_DIR` is read exclusively in `src/imports/model.py:15`:\n'
                          "`CHROMA_DB_DIR = os.getenv('CHROMA_DB_DIR', './5e_dnd_chroma_langchain_db')`.\n"
                          "Its default fallback directory is `'./5e_dnd_chroma_langchain_db'`.",
                'verification_target': 'Vector DB directory configuration.'},
    'Q111': {   'id': 'Q111',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Where is `TURN_LIMIT` loaded from the environment, and what is its fallback value?',
                'tool_chain': '',
                'answer': '`TURN_LIMIT` is loaded from the environment in 2 places:\n'
                          '1. `main.py:13`: `TURN_LIMIT = int(os.getenv("TURN_LIMIT", 10))`\n'
                          '2. `src/game_workflows/core.py:13`: `TURN_LIMIT = int(os.getenv("TURN_LIMIT", 10))`\n'
                          'Its fallback default value is `10`.',
                'verification_target': 'Integer cast env var audit.'},
    'Q112': {   'id': 'Q112',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Which function reads `TOTAL_MAX_POINTS_AT_START` from the environment?',
                'tool_chain': '',
                'answer': '`TOTAL_MAX_POINTS_AT_START` is read at module level in:\n'
                          '`src/game_workflows/player.py:12`:\n'
                          '`TOTAL_SKILL_POINTS = int(os.getenv("TOTAL_MAX_POINTS_AT_START", 27))`\n'
                          'It is used in `initialize_session_state()` and `reset_character_form()`.',
                'verification_target': 'Point buy limit configuration.'},
    'Q113': {   'id': 'Q113',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Are there any API keys or tokens read from `.env` in this codebase?',
                'tool_chain': '',
                'answer': '**No API keys or tokens are read from `.env` in this codebase.**\n'
                          'The application relies strictly on local Ollama and local HuggingFace sentence transformer '
                          'models.',
                'verification_target': 'Negative security finding.'},
    'Q114': {   'id': 'Q114',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Are there any hardcoded secret strings or tokens in the codebase?',
                'tool_chain': '',
                'answer': '**There are zero hardcoded secret strings, tokens, or credentials in the codebase.**',
                'verification_target': 'Secret scanning audit.'},
    'Q115': {   'id': 'Q115',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What environment variables are loaded in `src/game_workflows/loaders.py`?',
                'tool_chain': '',
                'answer': '`src/game_workflows/loaders.py` loads two environment variables:\n'
                          '1. `CHARACTERS_FILE` (default `"characters.json"`, line 8)\n'
                          '2. `HISTORY_DB_DIR` (default `"./history"`, line 9)',
                'verification_target': 'File-scoped env var list.'},
    'Q116': {   'id': 'Q116',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What environment variables are referenced in `src/game_workflows/player.py`?',
                'tool_chain': '',
                'answer': '`src/game_workflows/player.py` references one environment variable:\n'
                          '`TOTAL_MAX_POINTS_AT_START` (default `27`, line 12).',
                'verification_target': 'File-scoped env var list.'},
    'Q117': {   'id': 'Q117',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What environment variables does `main.py` read?',
                'tool_chain': '',
                'answer': '`main.py` reads 3 environment variables:\n'
                          "1. `OLLAMA_HOST` (default `'localhost'`, line 11)\n"
                          "2. `OLLAMA_PORT` (default `'11434'`, line 12)\n"
                          '3. `TURN_LIMIT` (default `10`, line 13)',
                'verification_target': 'Main module env var list.'},
    'Q118': {   'id': 'Q118',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What environment variables are accessed in `src/imports/model.py`?',
                'tool_chain': '',
                'answer': '`src/imports/model.py` accesses 4 environment variables:\n'
                          "1. `OLLAMA_HOST` (default `'localhost'`, line 11)\n"
                          '2. `OLLAMA_PORT` (default `"11434"`, line 12)\n'
                          "3. `CHROMA_DB_DIR` (default `'./5e_dnd_chroma_langchain_db'`, line 15)\n"
                          '4. `HISTORY_DB_DIR` (default `"./history"`, line 16)',
                'verification_target': 'Model setup module env var list.'},
    'Q119': {   'id': 'Q119',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What environment variables are read in `src/utils.py`?',
                'tool_chain': '',
                'answer': '`src/utils.py` reads 2 environment variables:\n'
                          "1. `OLLAMA_HOST` (default `'localhost'`, line 7)\n"
                          '2. `OLLAMA_PORT` (default `"11434"`, line 8)',
                'verification_target': 'Utility module env var list.'},
    'Q120': {   'id': 'Q120',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'Does `core.py` read any environment variables directly?',
                'tool_chain': '',
                'answer': 'Yes, `src/game_workflows/core.py:13` directly reads:\n'
                          '`TURN_LIMIT = int(os.getenv("TURN_LIMIT", 10))`.',
                'verification_target': 'Verification of direct vs imported variables.'},
    'Q121': {   'id': 'Q121',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What happens if `TOTAL_MAX_POINTS_AT_START` is missing from the environment?',
                'tool_chain': '',
                'answer': 'If `TOTAL_MAX_POINTS_AT_START` is missing from the environment, Python uses the fallback '
                          'value of `27`, initializing `TOTAL_SKILL_POINTS = 27`.',
                'verification_target': 'Fallback verification.'},
    'Q122': {   'id': 'Q122',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What happens if `OLLAMA_PORT` is not configured in the `.env` file?',
                'tool_chain': '',
                'answer': 'If `OLLAMA_PORT` is not configured, it falls back to `"11434"`, constructing API endpoints '
                          'like `http://localhost:11434/api/generate`.',
                'verification_target': 'Fallback verification.'},
    'Q123': {   'id': 'Q123',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What default path is used if `HISTORY_DB_DIR` is not provided?',
                'tool_chain': '',
                'answer': 'The default path used if `HISTORY_DB_DIR` is not provided is `"./history"`.',
                'verification_target': 'Fallback path verification.'},
    'Q124': {   'id': 'Q124',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'What default model path is used if `CHROMA_DB_DIR` is not set?',
                'tool_chain': '',
                'answer': 'The default model path used if `CHROMA_DB_DIR` is not set is '
                          "`'./5e_dnd_chroma_langchain_db'`.",
                'verification_target': 'Fallback path verification.'},
    'Q125': {   'id': 'Q125',
                'category': 'Category 6: Environment Variables & Configuration Audits',
                'question': 'List every distinct environment variable read across the entire project.',
                'tool_chain': '',
                'answer': 'Across the entire repository, exactly **7 distinct environment variables** are read:\n'
                          '1. `OLLAMA_HOST`\n'
                          '2. `OLLAMA_PORT`\n'
                          '3. `TURN_LIMIT`\n'
                          '4. `CHARACTERS_FILE`\n'
                          '5. `HISTORY_DB_DIR`\n'
                          '6. `CHROMA_DB_DIR`\n'
                          '7. `TOTAL_MAX_POINTS_AT_START`',
                'verification_target': 'Project-wide deduplicated configuration audit.\n\n---'},
    'Q126': {   'id': 'Q126',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the exact implementation of `calculate_points_spent`?',
                'tool_chain': '',
                'answer': 'Exact implementation of `calculate_points_spent` (`src/game_workflows/player.py:24-26`):\n'
                          '```python\n'
                          'def calculate_points_spent(score):\n'
                          '    # Point buy system calculation\n'
                          '    return score - 8\n'
                          '```',
                'verification_target': 'Inner closure snippet extraction.'},
    'Q127': {   'id': 'Q127',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the complete code definition of `update_ability_score`.',
                'tool_chain': '',
                'answer': 'Complete code definition of `update_ability_score` (`src/game_workflows/player.py:28-36`):\n'
                          '```python\n'
                          'def update_ability_score(ability):\n'
                          '    old_score = st.session_state.ability_scores[ability]\n'
                          '    new_score = st.session_state[f"ability_{ability}"]\n'
                          '\n'
                          '    old_points = calculate_points_spent(old_score)\n'
                          '    new_points = calculate_points_spent(new_score)\n'
                          '\n'
                          '    st.session_state.ability_scores[ability] = new_score\n'
                          '    st.session_state.remaining_points += old_points - new_points\n'
                          '```',
                'verification_target': 'Callback closure extraction.'},
    'Q128': {   'id': 'Q128',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the code implementation of `reset_character_form` in `player.py`?',
                'tool_chain': '',
                'answer': 'Code implementation of `reset_character_form` (`src/game_workflows/player.py:38-41`):\n'
                          '```python\n'
                          'def reset_character_form():\n'
                          '    st.session_state.ability_scores = {ability: 8 for ability in [\n'
                          '        "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]}\n'
                          '    st.session_state.remaining_points = TOTAL_SKILL_POINTS\n'
                          '```',
                'verification_target': 'Form reset closure extraction.'},
    'Q129': {   'id': 'Q129',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the code of `initialize_session_state` in `src/game_workflows/player.py`.',
                'tool_chain': '',
                'answer': 'Code of `initialize_session_state` in `src/game_workflows/player.py:15-22`:\n'
                          '```python\n'
                          'def initialize_session_state():\n'
                          "    if 'character_created' not in st.session_state:\n"
                          '        st.session_state.character_created = False\n'
                          "    if 'ability_scores' not in st.session_state:\n"
                          '        st.session_state.ability_scores = {ability: 8 for ability in [\n'
                          '            "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", '
                          '"Charisma"]}\n'
                          "    if 'remaining_points' not in st.session_state:\n"
                          '        st.session_state.remaining_points = TOTAL_SKILL_POINTS\n'
                          '```',
                'verification_target': 'Disambiguating same-name function in `player.py` vs `game.py`.'},
    'Q130': {   'id': 'Q130',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the code of `initialize_session_state` in `src/game_workflows/game.py`.',
                'tool_chain': '',
                'answer': 'Code of `initialize_session_state` in `src/game_workflows/game.py:8-13`:\n'
                          '```python\n'
                          'def initialize_session_state():\n'
                          '    if "character_creation" not in st.session_state:\n'
                          '        st.session_state.character_creation = False\n'
                          '\n'
                          '    if "game_state" not in st.session_state:\n'
                          '        st.session_state.game_state = {"state": False}\n'
                          '```',
                'verification_target': 'Disambiguating same-name function in `game.py` vs `player.py`.'},
    'Q131': {   'id': 'Q131',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the exact code definition of `load_characters()` in `loaders.py`?',
                'tool_chain': '',
                'answer': 'Exact code definition of `load_characters()` in `src/game_workflows/loaders.py:12-16`:\n'
                          '```python\n'
                          'def load_characters():\n'
                          '    if os.path.exists(CHARACTERS_FILE):\n'
                          '        with open(CHARACTERS_FILE, "r") as f:\n'
                          '            return json.load(f)\n'
                          '    return {}\n'
                          '```',
                'verification_target': 'Base loader snippet extraction.'},
    'Q132': {   'id': 'Q132',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the code definition of `save_characters()` in `loaders.py`.',
                'tool_chain': '',
                'answer': 'Code definition of `save_characters()` in `src/game_workflows/loaders.py:19-21`:\n'
                          '```python\n'
                          'def save_characters(characters):\n'
                          '    with open(CHARACTERS_FILE, "w") as f:\n'
                          '        json.dump(characters, f, indent=4)\n'
                          '```',
                'verification_target': 'Base persistence snippet extraction.'},
    'Q133': {   'id': 'Q133',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the implementation of `load_adventure()` in `loaders.py`?',
                'tool_chain': '',
                'answer': 'Implementation of `load_adventure()` in `src/game_workflows/loaders.py:24-36`:\n'
                          '```python\n'
                          'def load_adventure(uuid):\n'
                          '    req_path = os.path.join(HISTORY_DB_DIR, "HIST")\n'
                          '    hist_path = os.path.join(req_path, f"{uuid}.pkl")\n'
                          '    char_path = os.path.join(req_path, f"{uuid}_char.pkl")\n'
                          '\n'
                          '    if os.path.exists(hist_path) and os.path.exists(char_path):\n'
                          '        with open(hist_path, "rb") as f:  # Open in binary mode for reading\n'
                          '            history = pickle.load(f)\n'
                          '        with open(char_path, "rb") as cf:\n'
                          '            characters = pickle.load(cf)\n'
                          '    else:\n'
                          '        raise NameError(f"History file {uuid} doesn\'t exist")\n'
                          '    return history, characters\n'
                          '```',
                'verification_target': 'Binary deserialization snippet extraction.'},
    'Q134': {   'id': 'Q134',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What does `load_available_adventures()` do in `loaders.py`?',
                'tool_chain': '',
                'answer': 'Implementation of `load_available_adventures()` in `src/game_workflows/loaders.py:39-44`:\n'
                          '```python\n'
                          'def load_available_adventures():\n'
                          '    req_path = os.path.join(HISTORY_DB_DIR, "HIST", "history_ids.json")\n'
                          '    if os.path.exists(req_path):\n'
                          '        with open(req_path, "r") as f:\n'
                          '            return json.load(f)\n'
                          '    return {}\n'
                          '```',
                'verification_target': 'Index loader snippet extraction.'},
    'Q135': {   'id': 'Q135',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the complete implementation of `save_adventure()` in `loaders.py`.',
                'tool_chain': '',
                'answer': 'Complete implementation of `save_adventure()` in `src/game_workflows/loaders.py:47-63`:\n'
                          '```python\n'
                          'def save_adventure(uuid: str, history: list, history_names: dict, characters: list = None) '
                          '-> None:\n'
                          '    req_path = os.path.join(HISTORY_DB_DIR, "HIST")\n'
                          '    os.makedirs(req_path, exist_ok=True)\n'
                          '\n'
                          '    path = os.path.join(req_path, f"{uuid}.pkl")\n'
                          '    with open(path, "wb") as f:\n'
                          '        pickle.dump(history, f)\n'
                          '\n'
                          '    name_path = os.path.join(req_path, "history_ids.json")\n'
                          '    with open(name_path, "w") as f:\n'
                          '        json.dump(history_names, f)\n'
                          '\n'
                          '    if characters:\n'
                          '        char_path = os.path.join(req_path, f"{uuid}_char.pkl")\n'
                          '        with open(char_path, "wb") as f:\n'
                          '            pickle.dump(characters, f)\n'
                          '```',
                'verification_target': 'Multi-file persistence snippet.'},
    'Q136': {   'id': 'Q136',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the code of `update_history_ids()` in `loaders.py`?',
                'tool_chain': '',
                'answer': 'Code of `update_history_ids()` in `src/game_workflows/loaders.py:65-69`:\n'
                          '```python\n'
                          'def update_history_ids():\n'
                          '    req_path = os.path.join(HISTORY_DB_DIR, "HIST")\n'
                          '    name_path = os.path.join(req_path, "history_ids.json")\n'
                          '    with open(name_path, "w") as f:\n'
                          "        json.dump(st.session_state['adventure_dict'], f)\n"
                          '```',
                'verification_target': 'Short helper snippet extraction.'},
    'Q137': {   'id': 'Q137',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the code implementation of `delete_history_file()`?',
                'tool_chain': '',
                'answer': 'Code implementation of `delete_history_file()` in `src/game_workflows/loaders.py:72-91`:\n'
                          '```python\n'
                          'def delete_history_file(uuid):\n'
                          "    del st.session_state['adventure_dict'][uuid]\n"
                          '    path = os.path.join(HISTORY_DB_DIR, "HIST", f"{uuid}.pkl")\n'
                          '    char_path = os.path.join(HISTORY_DB_DIR, "HIST", f"{uuid}_char.pkl")\n'
                          '\n'
                          '    history_ids = st.session_state.history_store.get(\n'
                          '        where={"uuid": uuid}\n'
                          "    )['ids']\n"
                          '\n'
                          '    st.session_state.history_store.delete(history_ids)\n'
                          '\n'
                          '    # Check if file exists, then delete it\n'
                          '    if os.path.exists(path):\n'
                          '        os.remove(path)\n'
                          '        os.remove(char_path)\n'
                          '        print(f"File {path} deleted successfully.")\n'
                          '        update_history_ids()\n'
                          '    else:\n'
                          '        print(f"File {path} not found.")\n'
                          '```',
                'verification_target': 'Composite deletion snippet extraction.'},
    'Q138': {   'id': 'Q138',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the code of `check_ollama_availability()` in `utils.py`.',
                'tool_chain': '',
                'answer': 'Code of `check_ollama_availability()` in `src/utils.py:12-18`:\n'
                          '```python\n'
                          'def check_ollama_availability():\n'
                          '    try:\n'
                          '        response = requests.get(OLLAMA_API_ENDPOINT.replace(\n'
                          "            '/api/generate', '/api/version'), timeout=5)\n"
                          '        return response.status_code == 200\n'
                          '    except requests.RequestException:\n'
                          '        return False\n'
                          '```',
                'verification_target': 'HTTP check snippet extraction.'},
    'Q139': {   'id': 'Q139',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the implementation of `test_model_availability()` in `utils.py`?',
                'tool_chain': '',
                'answer': 'Implementation of `test_model_availability()` in `src/utils.py:21-28`:\n'
                          '```python\n'
                          'def test_model_availability():\n'
                          '    if not check_ollama_availability():\n'
                          '        st.error(\n'
                          '            "Ollama is not available. Please make sure it\'s running and configured '
                          'correctly.")\n'
                          '        st.info("To start Ollama, open a terminal and run the \'ollama serve\' command.")\n'
                          '        if st.button("Retry Connection"):\n'
                          '            st.rerun()\n'
                          '    return\n'
                          '```',
                'verification_target': 'UI error handler snippet.'},
    'Q140': {   'id': 'Q140',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the implementation of `initialize_rag()` in `src/imports/model.py`.',
                'tool_chain': '',
                'answer': 'Implementation of `initialize_rag()` in `src/imports/model.py:19-23`:\n'
                          '```python\n'
                          '@st.cache_resource\n'
                          'def initialize_rag():\n'
                          '    handbook_store = Chroma(\n'
                          '        embedding_function=st.session_state.embedding_model, '
                          'persist_directory=CHROMA_DB_DIR)\n'
                          '    return handbook_store.as_retriever()\n'
                          '```',
                'verification_target': 'Cached Chroma retriever factory.'},
    'Q141': {   'id': 'Q141',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'What is the code for `initialize_history()` in `src/imports/model.py`?',
                'tool_chain': '',
                'answer': 'Code of `initialize_history()` in `src/imports/model.py:26-30`:\n'
                          '```python\n'
                          '@st.cache_resource\n'
                          'def initialize_history():\n'
                          '    history_store = Chroma(\n'
                          '        embedding_function=st.session_state.embedding_model, '
                          'persist_directory=HISTORY_DB_DIR)\n'
                          '    return history_store\n'
                          '```',
                'verification_target': 'Cached Chroma history factory.'},
    'Q142': {   'id': 'Q142',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the code of `set_fantasy_theme()` in `theme.py`.',
                'tool_chain': '',
                'answer': 'Code of `set_fantasy_theme()` in `src/ui/theme.py:3-13`:\n'
                          '```python\n'
                          'def set_fantasy_theme():\n'
                          '    st.markdown("""\n'
                          '    <style>\n'
                          "        body { color: #e0e0e0; background-color: #1a1a2e; font-family: 'Cinzel', serif; }\n"
                          '        .stButton>button { color: #ffd700; background-color: #4a0e0e; border: 2px solid '
                          '#ffd700; }\n'
                          '        .stTextInput>div>div>input, .stTextArea>div>div>textarea { color: #e0e0e0; '
                          'background-color: #2a2a4e; }\n'
                          '        .stHeader { color: #ffd700; text-shadow: 2px 2px 4px #000000; }\n'
                          '        .sidebar .sidebar-content { background-color: #16213e; }\n'
                          '    </style>\n'
                          '    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&display=swap" '
                          'rel="stylesheet">\n'
                          '    """, unsafe_allow_html=True)\n'
                          '```',
                'verification_target': 'CSS injection snippet.'},
    'Q143': {   'id': 'Q143',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the implementation of `reset_old_games()` in `game.py`.',
                'tool_chain': '',
                'answer': 'Implementation of `reset_old_games()` in `src/game_workflows/game.py:70-77`:\n'
                          '```python\n'
                          'def reset_old_games():\n'
                          '    if "has_adventure_started" in st.session_state:\n'
                          '        del st.session_state["has_adventure_started"]\n'
                          '    if "chat_history" in st.session_state:\n'
                          '        del st.session_state["chat_history"]\n'
                          '    if "characters_in_adventure" in st.session_state:\n'
                          '        del st.session_state["characters_in_adventure"]\n'
                          '```',
                'verification_target': 'Session cleanup snippet.'},
    'Q144': {   'id': 'Q144',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the code of `dm_turn()` in `adventure.py`.',
                'tool_chain': '',
                'answer': 'Code of `dm_turn()` in `src/game_workflows/adventure.py:17-21`:\n'
                          '```python\n'
                          'def dm_turn(model: str, game_state: Dict, vector_store) -> str:\n'
                          '    context = vector_store.similarity_search(\n'
                          '        " ".join(game_state[\'story_progression\'][-5:]), k=3)\n'
                          '    dm_prompt = f"As the Dungeon Master, consider the recent events:\\n{\' '
                          "'.join(game_state['story_progression'][-5:])}\\nRelevant lore: {' '.join([doc.page_content "
                          'for doc in context])}\\nSummarize the actions, introduce the next challenge or plot '
                          'development, and describe the scene. Be creative and engaging."\n'
                          '    return api_call(model, dm_prompt, 300)\n'
                          '```',
                'verification_target': 'Standalone turn runner snippet.'},
    'Q145': {   'id': 'Q145',
                'category': 'Category 7: Exact AST Definitions & Inner Closures',
                'question': 'Show the implementation of `start_new_adventure()` in `adventure.py`.',
                'tool_chain': '',
                'answer': 'Implementation of `start_new_adventure()` in `src/game_workflows/adventure.py:5-14`:\n'
                          '```python\n'
                          'def start_new_adventure(model: str, party_members: Dict[str, str]) -> Tuple[Dict, str]:\n'
                          '    dm_intro = api_call(model,\n'
                          '                        f"You are the Dungeon Master. Start an exciting and unique D&D '
                          "adventure. Introduce the characters: {', '.join(party_members.keys())}. Set the scene and "
                          'present an initial challenge or mystery.",\n'
                          '                        300)\n'
                          '    return {\n'
                          '        "turn": 1,\n'
                          '        "story_progression": [dm_intro],\n'
                          '        "turn_participation": {name: False for name in party_members},\n'
                          '        "party_members": party_members\n'
                          '    }, dm_intro\n'
                          '```',
                'verification_target': 'Standalone intro runner snippet.\n\n---'},
    'Q146': {   'id': 'Q146',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'What classes are defined in `src/api_workflows/call_api.py`?',
                'tool_chain': '',
                'answer': '`src/api_workflows/call_api.py` defines exactly one class:\n`class OllamaApi:` (line 14).',
                'verification_target': 'Class inventory query.'},
    'Q147': {   'id': 'Q147',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'What are the direct methods of the `OllamaApi` class?',
                'tool_chain': '',
                'answer': 'The direct methods of `OllamaApi` in `src/api_workflows/call_api.py` are:\n'
                          '1. `__init__(self, model: str, temperature: int = 0.7) -> None` (line 15)\n'
                          '2. `start_adventure(self, characters: List[str], difficulty: str, user_prompt: str = None) '
                          '-> Generator` (line 24)\n'
                          '3. `name_adventure(self, adventure: str) -> str` (line 57)\n'
                          '4. `progress_story(self, chat_msg: dict[str, str], history: list) -> Generator` (line 74)\n'
                          '5. `save_doc_to_history_vector(self, doc: Document) -> None` (line 163)',
                'verification_target': 'Method extraction for class.'},
    'Q148': {   'id': 'Q148',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Does `OllamaApi` inherit from any superclasses or base classes?',
                'tool_chain': '',
                'answer': 'No. `OllamaApi` does not inherit from any custom superclasses or base classes (it inherits '
                          "directly from Python's implicit `object`).",
                'verification_target': 'Inheritance root verification.'},
    'Q149': {   'id': 'Q149',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'What is the constructor signature and initialization logic of `OllamaApi`?',
                'tool_chain': '',
                'answer': 'Constructor signature and initialization logic of `OllamaApi` (`call_api.py:15-23`):\n'
                          'Signature: `def __init__(self, model: str, temperature: int = 0.7) -> None:`\n'
                          'Logic:\n'
                          '1. Instantiates `self.llm = OllamaLLM(model=model, temperature=temperature)`.\n'
                          '2. Instantiates `self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1100, '
                          'chunk_overlap=100)`.\n'
                          '3. Catches `requests.RequestException` to report errors via `st.error`.',
                'verification_target': 'Constructor AST audit.'},
    'Q150': {   'id': 'Q150',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Does `src/imports/model.py` define any custom classes?',
                'tool_chain': '',
                'answer': 'No. `src/imports/model.py` defines no classes; it contains only functions '
                          '(`initialize_rag`, `initialize_history`, `manage_models`, and nested `list_ollama_models`).',
                'verification_target': 'Negative class query.'},
    'Q151': {   'id': 'Q151',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Does `src/game_workflows/player.py` define any classes?',
                'tool_chain': '',
                'answer': 'No. `src/game_workflows/player.py` defines no classes; it consists entirely of procedural '
                          'functions (`create_character_form`, `display_character_list`, and inner closures).',
                'verification_target': 'Functional vs OOP architecture check.'},
    'Q152': {   'id': 'Q152',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'What external LangChain classes are instantiated across the codebase?',
                'tool_chain': '',
                'answer': 'External LangChain classes instantiated across the repository:\n'
                          '1. `OllamaLLM` (`langchain_ollama.llms`) in `call_api.py:17`\n'
                          '2. `RecursiveCharacterTextSplitter` (`langchain_text_splitters`) in `call_api.py:18`\n'
                          '3. `Chroma` (`langchain_chroma`) in `model.py:21, 28`\n'
                          '4. `HuggingFaceEmbeddings` (`langchain_huggingface`) in `model.py:65`\n'
                          '5. `Document` (`langchain_core.documents`) in `core.py:68, 128, 139`\n'
                          '6. `AIMessage` and `HumanMessage` (`langchain_core.messages`) in `call_api.py:94, 96`',
                'verification_target': 'External dependency instantiation audit.'},
    'Q153': {   'id': 'Q153',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Where is `Chroma` instantiated and how is it configured?',
                'tool_chain': '',
                'answer': '`Chroma` is instantiated in `src/imports/model.py` at two locations:\n'
                          '1. `initialize_rag()` (lines 21-22):\n'
                          '   `Chroma(embedding_function=st.session_state.embedding_model, '
                          'persist_directory=CHROMA_DB_DIR)`\n'
                          '2. `initialize_history()` (lines 28-29):\n'
                          '   `Chroma(embedding_function=st.session_state.embedding_model, '
                          'persist_directory=HISTORY_DB_DIR)`',
                'verification_target': 'Vector DB client instantiation points.'},
    'Q154': {   'id': 'Q154',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Where is `HuggingFaceEmbeddings` instantiated and what models does it support in the UI?',
                'tool_chain': '',
                'answer': '`HuggingFaceEmbeddings` is instantiated in `src/imports/model.py:65-66`:\n'
                          '`st.session_state.embedding_model = HuggingFaceEmbeddings(model_name=embedding_model)`\n'
                          'The UI selectbox (`model.py:58-59`) supports two embedding models:\n'
                          '1. `"sentence-transformers/all-MiniLM-L6-v2"`\n'
                          '2. `"sentence-transformers/all-mpnet-base-v2"`',
                'verification_target': 'Embedding model option audit.'},
    'Q155': {   'id': 'Q155',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Where is `RecursiveCharacterTextSplitter` instantiated and what are its chunk size and '
                            'overlap?',
                'tool_chain': '',
                'answer': '`RecursiveCharacterTextSplitter` is instantiated in `src/api_workflows/call_api.py:18-19`:\n'
                          '`RecursiveCharacterTextSplitter(chunk_size=1100, chunk_overlap=100)`\n'
                          'Its chunk size is `1100` and its chunk overlap is `100`.',
                'verification_target': 'Text splitter parameter audit.'},
    'Q156': {   'id': 'Q156',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Where is `OllamaLLM` instantiated in the codebase?',
                'tool_chain': '',
                'answer': '`OllamaLLM` is instantiated in `src/api_workflows/call_api.py:17` inside '
                          '`OllamaApi.__init__`:\n'
                          '`self.llm = OllamaLLM(model=model, temperature=temperature)`.',
                'verification_target': 'LLM client instantiation point.'},
    'Q157': {   'id': 'Q157',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': "How is LangChain's `Document` class used in `core.py`?",
                'tool_chain': '',
                'answer': "LangChain's `Document` class is used in `src/game_workflows/core.py` to wrap narrative "
                          'segments with metadata before saving to vector memory:\n'
                          '1. Line 68: wraps initial DM intro with `metadata={"source": "AI", "uuid": '
                          'adventure_uuid}`.\n'
                          '2. Line 128: wraps player input actions with `metadata={"source": "Human", "uuid": '
                          'adventure_uuid}`.\n'
                          '3. Line 139: wraps DM response turns with `metadata={"source": "AI", "uuid": '
                          'adventure_uuid}`.',
                'verification_target': 'Data transfer object audit.'},
    'Q158': {   'id': 'Q158',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Are there any abstract base classes (ABCs) implemented in this repository?',
                'tool_chain': '',
                'answer': 'No. There are no Abstract Base Classes (ABCs) defined or implemented in the `dnd` '
                          'repository.',
                'verification_target': 'Negative pattern verification.'},
    'Q159': {   'id': 'Q159',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'What third-party message classes are used in `core.py`?',
                'tool_chain': '',
                'answer': 'In `core.py`, chat history is stored as plain Python tuples: `(role, message)` where `role` '
                          'is `"user"` or `"assistant"`. Third-party LangChain message classes (`AIMessage`, '
                          '`HumanMessage`) are used in `src/api_workflows/call_api.py:94, 96`.',
                'verification_target': 'Message schema inventory.'},
    'Q160': {   'id': 'Q160',
                'category': 'Category 8: Type Hierarchy, OOP & Class Introspection',
                'question': 'Are there any Pydantic models defined in the `dnd` repo?',
                'tool_chain': '',
                'answer': 'No. There are **zero Pydantic models** (`BaseModel`) defined in the `dnd` repository.',
                'verification_target': 'Repository boundary verification.\n\n---'},
    'Q161': {   'id': 'Q161',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is `start_new_adventure()` in `src/game_workflows/adventure.py` called anywhere in the '
                            'active application?',
                'tool_chain': '',
                'answer': 'No. `start_new_adventure()` in `src/game_workflows/adventure.py:5` is completely uncalled '
                          'and unreachable. The live application uses `start_adventure()` in '
                          '`src/game_workflows/core.py`.',
                'verification_target': 'Uncalled function detection.'},
    'Q162': {   'id': 'Q162',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is `dm_turn()` in `src/game_workflows/adventure.py` used by `main.py` or `game.py`?',
                'tool_chain': '',
                'answer': 'No. `dm_turn()` in `src/game_workflows/adventure.py:17` is neither imported nor called by '
                          '`main.py`, `game.py`, or any active module.',
                'verification_target': 'Dead function reachability analysis.'},
    'Q163': {   'id': 'Q163',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any dead or uncalled functions in `src/game_workflows/adventure.py`?',
                'tool_chain': '',
                'answer': 'Yes. Both functions in `src/game_workflows/adventure.py` (`start_new_adventure` and '
                          '`dm_turn`) are dead, uncalled code.',
                'verification_target': 'File-level dead code audit.'},
    'Q164': {   'id': 'Q164',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is the entire file `src/game_workflows/adventure.py` an orphan module?',
                'tool_chain': '',
                'answer': 'Yes. The entire file `src/game_workflows/adventure.py` is an orphan module; no other file '
                          'in the repository imports or executes it.',
                'verification_target': 'Dead file reachability.'},
    'Q165': {   'id': 'Q165',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is `api_call` imported in `adventure.py` actually defined in `call_api.py`?',
                'tool_chain': '',
                'answer': 'No. `adventure.py:2` attempts `from src.api_workflows.call_api import api_call`, but '
                          '`api_call` does not exist in `call_api.py` (which defines only `class OllamaApi`). Any '
                          'attempt to run `adventure.py` raises an `ImportError`.',
                'verification_target': 'Broken import / dead edge detection.'},
    'Q166': {   'id': 'Q166',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any unused imports in `src/game_workflows/player.py`?',
                'tool_chain': '',
                'answer': 'Yes. `src/game_workflows/player.py:3` has an unused import:\n'
                          '`from requests import session`.',
                'verification_target': 'AST unused import detection.'},
    'Q167': {   'id': 'Q167',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is `from requests import session` in `player.py` ever used?',
                'tool_chain': '',
                'answer': 'No. `from requests import session` in `player.py:3` is completely unused dead code.',
                'verification_target': 'Specific unused import check.'},
    'Q168': {   'id': 'Q168',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any unused variables declared in `src/game_workflows/references.py`?',
                'tool_chain': '',
                'answer': 'No. `src/game_workflows/references.py` defines exactly two variables: `weapon_dict` and '
                          '`armor_dict`. Both are imported and actively used in `src/game_workflows/player.py:7, 114, '
                          '130`.',
                'verification_target': 'Variable reachability check.'},
    'Q169': {   'id': 'Q169',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is `reset_character_form()` in `player.py` called anywhere, or is it dead code?',
                'tool_chain': '',
                'answer': '`reset_character_form()` is **not dead code**. It is actively called in '
                          '`src/game_workflows/player.py:181` inside `create_character_form()` right after a character '
                          'is successfully saved.',
                'verification_target': 'Inner closure orphan detection.'},
    'Q170': {   'id': 'Q170',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any unreferenced functions in `src/game_workflows/loaders.py`?',
                'tool_chain': '',
                'answer': 'No. All 7 functions in `src/game_workflows/loaders.py` are referenced and called across the '
                          'codebase:\n'
                          '- `load_characters` (called in `player.py`, `core.py`, `call_api.py`)\n'
                          '- `save_characters` (called in `player.py`)\n'
                          '- `load_adventure` (called in `game.py`)\n'
                          '- `load_available_adventures` (called in `game.py`)\n'
                          '- `save_adventure` (called in `core.py`)\n'
                          '- `update_history_ids` (called in `loaders.py`)\n'
                          '- `delete_history_file` (called in `game.py`)',
                'verification_target': 'Full reachability verification of utility module.'},
    'Q171': {   'id': 'Q171',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any dead or uncalled functions in `src/utils.py`?',
                'tool_chain': '',
                'answer': 'No. Both functions in `src/utils.py` are actively called:\n'
                          '- `check_ollama_availability()`: called in `main.py:29` and `utils.py:22`\n'
                          '- `test_model_availability()`: called in `main.py:44`',
                'verification_target': 'Utility module reachability verification.'},
    'Q172': {   'id': 'Q172',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Is `character_created` in `st.session_state` ever checked after initialization?',
                'tool_chain': '',
                'answer': 'No. `character_created` is initialized in `src/game_workflows/player.py:17` '
                          '(`st.session_state.character_created = False`), but is **never checked or modified again** '
                          'anywhere in the project.',
                'verification_target': 'Dead session state flag detection.'},
    'Q173': {   'id': 'Q173',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any orphan functions in `src/imports/model.py`?',
                'tool_chain': '',
                'answer': 'No. All functions in `src/imports/model.py` (`initialize_rag`, `initialize_history`, '
                          '`manage_models`, and nested `list_ollama_models`) are actively called.',
                'verification_target': 'Import module reachability check.'},
    'Q174': {   'id': 'Q174',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Are there any unused environment variables loaded in `.env` or in the Python files?',
                'tool_chain': '',
                'answer': 'Yes. `TURN_LIMIT` is loaded via `os.getenv("TURN_LIMIT", 10)` in `main.py:13` and '
                          '`src/game_workflows/core.py:13`, but is never referenced anywhere in game turn logic or '
                          'loop conditions.',
                'verification_target': 'Configuration reachability check.'},
    'Q175': {   'id': 'Q175',
                'category': 'Category 9: Dead Code, Orphans & Reachability',
                'question': 'Run a full dead-code audit: What are all unreachable functions detected across the '
                            'repository?',
                'tool_chain': '',
                'answer': 'Comprehensive dead-code audit across the repository:\n'
                          '1. Dead functions:\n'
                          '   - `start_new_adventure()` in `src/game_workflows/adventure.py:5`\n'
                          '   - `dm_turn()` in `src/game_workflows/adventure.py:17`\n'
                          '2. Dead module:\n'
                          '   - Entire `src/game_workflows/adventure.py` file is orphaned.\n'
                          '3. Dead imports:\n'
                          '   - `from requests import session` in `src/game_workflows/player.py:3`\n'
                          '   - `from src.api_workflows.call_api import api_call` in `adventure.py:2` (broken import)\n'
                          '4. Dead state variables:\n'
                          '   - `st.session_state.character_created` in `player.py:17` (set once, never read)\n'
                          '5. Dead environment variable:\n'
                          '   - `TURN_LIMIT` in `main.py:13` and `core.py:13` (loaded, never used)',
                'verification_target': 'Project-wide reachability audit.\n\n---'},
    'Q176': {   'id': 'Q176',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'Are there any circular imports between `game_workflows` and `api_workflows`?',
                'tool_chain': '',
                'answer': 'No circular imports exist between `game_workflows` and `api_workflows`.\n'
                          '`call_api.py` imports `load_characters` from `loaders.py`.\n'
                          '`core.py` imports `OllamaApi` from `call_api.py`.\n'
                          'There is no reverse import from `api_workflows` back into `core.py` or `game.py`.',
                'verification_target': 'Circular dependency cycle check.'},
    'Q177': {   'id': 'Q177',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'Does `src/game_workflows/player.py` import anything from `src/game_workflows/core.py`?',
                'tool_chain': '',
                'answer': 'No. `src/game_workflows/player.py` does not import anything from '
                          '`src/game_workflows/core.py`.',
                'verification_target': 'Dependency boundary check.'},
    'Q178': {   'id': 'Q178',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'Does `src/game_workflows/core.py` import anything from `src/game_workflows/player.py`?',
                'tool_chain': '',
                'answer': 'No. `src/game_workflows/core.py` does not import anything from '
                          '`src/game_workflows/player.py`.',
                'verification_target': 'Cross-module import check.'},
    'Q179': {   'id': 'Q179',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'Is there an import cycle between `player.py` and `core.py`?',
                'tool_chain': '',
                'answer': 'No. There is no import cycle between `player.py` and `core.py`. Neither file imports the '
                          'other; both are independent modules orchestrated by `game.py` and `main.py`.',
                'verification_target': 'Acyclic dependency verification.'},
    'Q180': {   'id': 'Q180',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'What modules depend directly on `src/game_workflows/loaders.py`?',
                'tool_chain': '',
                'answer': 'Four modules directly import `src/game_workflows/loaders.py`:\n'
                          '1. `src/game_workflows/player.py` (imports `load_characters`, `save_characters`)\n'
                          '2. `src/game_workflows/game.py` (imports `load_adventure`, `load_available_adventures`, '
                          '`delete_history_file`)\n'
                          '3. `src/game_workflows/core.py` (imports `load_characters`, `save_adventure`)\n'
                          '4. `src/api_workflows/call_api.py` (imports `load_characters`)',
                'verification_target': 'Fan-in module dependency audit.'},
    'Q181': {   'id': 'Q181',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'What are all the internal dependencies imported by `main.py`?',
                'tool_chain': '',
                'answer': 'Internal dependencies imported by `main.py`:\n'
                          '1. `src.ui.theme` (`set_fantasy_theme`)\n'
                          '2. `src.utils` (`test_model_availability`, `check_ollama_availability`)\n'
                          '3. `src.imports.model` (`manage_models`)\n'
                          '4. `src.game_workflows.game` (`play_game`, `display_adventure_list`)\n'
                          '5. `src.game_workflows.player` (`display_character_list`)',
                'verification_target': 'Main orchestrator import map.'},
    'Q182': {   'id': 'Q182',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'What modules import from `src/utils.py`?',
                'tool_chain': '',
                'answer': 'Only `main.py:4` imports from `src/utils.py` (`from src.utils import '
                          'test_model_availability, check_ollama_availability`).',
                'verification_target': 'Utility dependency fan-in.'},
    'Q183': {   'id': 'Q183',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'What modules import from `src/imports/model.py`?',
                'tool_chain': '',
                'answer': 'Only `main.py:5` imports from `src/imports/model.py` (`from src.imports.model import '
                          'manage_models`).',
                'verification_target': 'Model manager dependency fan-in.'},
    'Q184': {   'id': 'Q184',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'What files import `src/game_workflows/references.py`?',
                'tool_chain': '',
                'answer': 'Only `src/game_workflows/player.py:7` imports `src/game_workflows/references.py` (`from '
                          'src.game_workflows.references import weapon_dict, armor_dict`).',
                'verification_target': 'Reference table dependency fan-in.'},
    'Q185': {   'id': 'Q185',
                'category': 'Category 10: Architecture Coupling & Modularity Boundaries',
                'question': 'Does `src/ui/theme.py` have any dependencies on the game logic or API?',
                'tool_chain': '',
                'answer': 'No. `src/ui/theme.py` imports only `streamlit as st` and has zero dependencies on game '
                          'logic, loaders, models, or APIs.',
                'verification_target': 'UI presentation decoupling verification.\n\n---'},
    'Q186': {   'id': 'Q186',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace the lineage of the `difficulty` parameter in `start_adventure` through to '
                            '`OllamaApi`.',
                'tool_chain': '',
                'answer': 'Lineage of `difficulty` parameter:\n'
                          '1. User selects difficulty in `src/game_workflows/core.py:40` via '
                          '`st.selectbox("Difficulty", ["easy", "medium", "hard"])`.\n'
                          '2. Passed as argument `difficulty=difficulty` to '
                          "`st.session_state['api'].start_adventure()` in `core.py:52`.\n"
                          '3. Received in `OllamaApi.start_adventure(characters, difficulty, user_prompt)` in '
                          '`src/api_workflows/call_api.py:24`.\n'
                          '4. Injected into `chain.stream({"characters_details": ..., "difficulty": difficulty, '
                          '"user_prompt": ...})` at `call_api.py:54`, populating `{difficulty}` in the LLM prompt '
                          'template.',
                'verification_target': 'Cross-module parameter flow.'},
    'Q187': {   'id': 'Q187',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace the lineage of the `characters` parameter from `core.py` to '
                            '`OllamaApi.start_adventure`.',
                'tool_chain': '',
                'answer': 'Lineage of `characters` parameter:\n'
                          '1. In `src/game_workflows/core.py:35`, user selections from `st.multiselect("Select '
                          'Characters", list(characters.keys()))` are assigned to '
                          '`st.session_state["characters_in_adventure"]`.\n'
                          '2. Passed as `characters=st.session_state["characters_in_adventure"]` to '
                          "`st.session_state['api'].start_adventure()` in `core.py:51`.\n"
                          '3. In `OllamaApi.start_adventure()` (`call_api.py:49-53`), `characters_dict = '
                          "load_characters()` is called, and each character's stats are concatenated into "
                          '`characters_str`.\n'
                          '4. Injected into `chain.stream({"characters_details": characters_str, ...})` at '
                          '`call_api.py:54`.',
                'verification_target': 'Parameter transformation and prompt interpolation.'},
    'Q188': {   'id': 'Q188',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace how `score` flows into `calculate_points_spent` in `player.py`.',
                'tool_chain': '',
                'answer': 'Lineage of `score` into `calculate_points_spent`:\n'
                          '1. Player changes score in `st.number_input()` (`src/game_workflows/player.py:72-78`), '
                          'triggering callback `on_change=update_ability_score, args=(ability,)`.\n'
                          '2. In `update_ability_score(ability)` (`player.py:28-33`), `old_score = '
                          'st.session_state.ability_scores[ability]` and `new_score = '
                          'st.session_state[f"ability_{ability}"]` are retrieved.\n'
                          '3. Both are passed to `calculate_points_spent(old_score)` and '
                          '`calculate_points_spent(new_score)` at lines 32 and 33.\n'
                          '4. Inside `calculate_points_spent(score)` (`player.py:24-26`), it returns `score - 8`.',
                'verification_target': 'Widget value to closure argument propagation.'},
    'Q189': {   'id': 'Q189',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace how `uuid` propagates from `initialize_adventure_state` to `load_adventure`.',
                'tool_chain': '',
                'answer': 'Lineage of `uuid` from `initialize_adventure_state` to `load_adventure`:\n'
                          "1. In `src/game_workflows/game.py:53`, when player clicks '🎮', "
                          "`initialize_adventure_state(uuid)` is called with the campaign's UUID string.\n"
                          '2. In `initialize_adventure_state(uuid)` (`game.py:63`), it calls `history, characters = '
                          'load_adventure(uuid=uuid)`.\n'
                          '3. In `load_adventure(uuid)` (`loaders.py:24-36`), `uuid` formats `{uuid}.pkl` and '
                          '`{uuid}_char.pkl` to locate and load files from `./history/HIST`.',
                'verification_target': 'UUID string propagation into file paths.'},
    'Q190': {   'id': 'Q190',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace how `user_prompt` in `core.py` reaches the LangChain prompt template in '
                            '`call_api.py`.',
                'tool_chain': '',
                'answer': 'Lineage of `user_prompt` from `core.py` to `call_api.py`:\n'
                          '1. User enters text in `st.text_area("Give me some prompt", ...)` in '
                          '`src/game_workflows/core.py:42` stored as `prompt`.\n'
                          "2. Passed as `user_prompt=prompt` to `st.session_state['api'].start_adventure()` in "
                          '`core.py:52`.\n'
                          '3. In `OllamaApi.start_adventure()` (`call_api.py:25-26`), if empty it defaults to `"make '
                          'it as instreasting as possible."`.\n'
                          '4. Injected into `chain.stream({"user_prompt": user_prompt, ...})` at `call_api.py:54`, '
                          'populating `{user_prompt}` in the prompt template.',
                'verification_target': 'Default argument assignment and prompt injection flow.'},
    'Q191': {   'id': 'Q191',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace how `adventure_start` text flows from `api.start_adventure` into `save_adventure`.',
                'tool_chain': '',
                'answer': 'Lineage of `adventure_start` text into `save_adventure`:\n'
                          '1. In `src/game_workflows/core.py:54-56`, tokens streamed from '
                          "`st.session_state['api'].start_adventure(...)` are captured in `adventure_start`.\n"
                          '2. Line 68: wraps `adventure_start` in `Document(page_content=adventure_start, '
                          'metadata={"source": "AI", "uuid": adventure_uuid})` and saves it to history vector store.\n'
                          '3. Line 70: appends `("assistant", adventure_start)` to '
                          '`st.session_state["chat_history"]`.\n'
                          '4. Line 75: passes `history=st.session_state["chat_history"]` to `save_adventure(uuid=..., '
                          'history=..., history_names=..., characters=...)`.',
                'verification_target': 'Streamed text accumulation and persistence flow.'},
    'Q192': {   'id': 'Q192',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace the lineage of the `model` parameter from `manage_models` into '
                            '`OllamaApi.__init__`.',
                'tool_chain': '',
                'answer': 'Lineage of `model` parameter into `OllamaApi.__init__`:\n'
                          '1. User chooses model in `manage_models()` (`src/imports/model.py:56-57`) via `dm_model = '
                          'st.selectbox("Dungeon Master Model", models, ...)`.\n'
                          "2. Clicking 'Save Model Selections' (line 61) calls `st.session_state.api = "
                          'OllamaApi(model=dm_model)` at line 63-64.\n'
                          '3. Received in `OllamaApi.__init__(self, model: str, temperature: int = 0.7)` '
                          '(`call_api.py:15`), which assigns `self.llm = OllamaLLM(model=model, '
                          'temperature=temperature)` at line 17.',
                'verification_target': 'Constructor parameter binding.'},
    'Q193': {   'id': 'Q193',
                'category': 'Category 11: Parameter Lineage & Value Propagation',
                'question': 'Trace how `chat_msg` flows through `OllamaApi.progress_story`.',
                'tool_chain': '',
                'answer': 'Lineage of `chat_msg` through `OllamaApi.progress_story`:\n'
                          '1. In `src/game_workflows/core.py:112`, submitted character actions are collected into '
                          '`current_chat[character] = message`.\n'
                          "2. Line 122: passed to `st.session_state['api'].progress_story(chat_msg=current_chat, "
                          'history=st.session_state["chat_history"])`.\n'
                          '3. In `OllamaApi.progress_story()` (`call_api.py:74-159`):\n'
                          '   - `get_input()` (lines 106-111) formats `{character} said: {message}\\n\\n` into '
                          '`input_text`.\n'
                          '   - `get_history()` (lines 75-90) iterates over `chat.values()`, embeds each with '
                          '`embedding_model.embed_query(msg)`, and searches `history_store`.\n'
                          '4. Both formatted inputs are passed to `rag_chain.stream({"input": input_text, '
                          '"chat_history": history_as_message})`.',
                'verification_target': 'Dictionary values iteration and embedding query flow.\n\n---'},
    'Q194': {   'id': 'Q194',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'How does the character creation point-buy system calculate remaining skill points?',
                'tool_chain': 'Method 1 (`tool_search_codebase_semantic` $\\rightarrow$ '
                              '`tool_get_symbol_code_snippet`)',
                'answer': 'Character creation point-buy system calculation:\n'
                          '1. Total budget: Initialized to `TOTAL_SKILL_POINTS = '
                          'int(os.getenv("TOTAL_MAX_POINTS_AT_START", 27))` (`player.py:12, 22`).\n'
                          '2. Baseline scores: All 6 abilities begin at base score 8 (`player.py:19-20`).\n'
                          '3. Cost formula: `calculate_points_spent(score) = score - 8` (`player.py:24-26`).\n'
                          '4. Allocation update: When a player adjusts a score, `update_ability_score()` '
                          '(`player.py:28-36`) calculates `old_points = calculate_points_spent(old_score)` and '
                          '`new_points = calculate_points_spent(new_score)`, adjusting remaining points by:\n'
                          '   `st.session_state.remaining_points += old_points - new_points`.',
                'verification_target': 'Pure natural language conceptual query to AST arithmetic resolution.'},
    'Q195': {   'id': 'Q195',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'What happens when a player allocates points to an ability score higher than 15?',
                'tool_chain': '',
                'answer': 'When a player attempts to allocate an ability score higher than 15:\n'
                          'The Streamlit widget `st.number_input()` in `src/game_workflows/player.py:74` strictly '
                          'enforces `max_value=15` (and `min_value=8`).\n'
                          'The UI prevents the player from entering or incrementing any score above 15.',
                'verification_target': 'Form boundary constraint resolution.'},
    'Q196': {   'id': 'Q196',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'How does the application check if the local Ollama server is alive before letting users '
                            'play?',
                'tool_chain': '',
                'answer': 'Checking Ollama availability before playing:\n'
                          '1. Application startup: `main()` (`main.py:44`) calls `test_model_availability()` '
                          '(`src/utils.py:21-28`).\n'
                          '2. Verification call: `test_model_availability()` calls `check_ollama_availability()` '
                          '(`src/utils.py:12-18`).\n'
                          '3. HTTP probe: Sends `requests.get("http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/version", '
                          'timeout=5)`.\n'
                          '4. Guard block: If status is not 200 or an exception is raised, `test_model_availability()` '
                          "displays an error banner with a 'Retry Connection' button, blocking users from playing "
                          'until Ollama is running.',
                'verification_target': 'System health check conceptual query.'},
    'Q197': {   'id': 'Q197',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'Where and how is the 5e Dungeons & Dragons rules handbook indexed into ChromaDB?',
                'tool_chain': '',
                'answer': 'Indexing the 5e D&D rules handbook into ChromaDB:\n'
                          '1. Pre-built index: The handbook is stored in a pre-indexed Chroma vector database '
                          'directory at `./5e_dnd_chroma_langchain_db` (configured via `CHROMA_DB_DIR` in '
                          '`src/imports/model.py:15`).\n'
                          '2. Resource loading: In `initialize_rag()` (`model.py:20-23`), decorated with '
                          '`@st.cache_resource`, it is instantiated using:\n'
                          '   `Chroma(embedding_function=st.session_state.embedding_model, '
                          'persist_directory=CHROMA_DB_DIR)`\n'
                          '3. Retriever conversion: Exposed to the application as a retriever via '
                          '`handbook_store.as_retriever()`.',
                'verification_target': 'RAG vector store architecture resolution.'},
    'Q198': {   'id': 'Q198',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'How does the application persist conversation history so players can resume past '
                            'campaigns?',
                'tool_chain': '',
                'answer': 'Dual-storage strategy for persisting campaign history:\n'
                          '1. Pickle serialization (`save_adventure` in `loaders.py:47-63`):\n'
                          '   Dumps `st.session_state["chat_history"]` to `{uuid}.pkl` and characters to '
                          '`{uuid}_char.pkl` in `./history/HIST/`.\n'
                          '2. JSON registry (`loaders.py:55-57`):\n'
                          '   Records `{uuid: adventure_name}` in `./history/HIST/history_ids.json`.\n'
                          '3. Vector database persistence (`call_api.py:163-167`):\n'
                          '   Splits dialogue turns with `RecursiveCharacterTextSplitter` and embeds chunks into '
                          'ChromaDB at `./history` with `metadata={"uuid": uuid, "source": "AI"|"Human"}`.\n'
                          'To resume, `load_adventure()` unpickles the files and `initialize_adventure_state()` '
                          'restores the session state.',
                'verification_target': 'Dual-tier persistence concept mapping.'},
    'Q199': {   'id': 'Q199',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'How does the Dungeon Master prompt change its behavior between Easy, Medium, and Hard '
                            'difficulty?',
                'tool_chain': '',
                'answer': 'Dungeon Master difficulty prompt conditioning:\n'
                          'In `src/api_workflows/call_api.py:33-37`, the prompt template explicitly conditions the '
                          "DM's dice roll logic:\n"
                          '- **Easy**: "You\'ll let their dice roll high mostly unless the demand is unreasonable"\n'
                          '- **Medium**: "You\'ll try and fail the roll where it makes sense and make the story '
                          'intresting"\n'
                          '- **Hard**: "You can randomly choose the roll"\n'
                          'The selected difficulty string is injected into `{difficulty}` in `chain.stream()`.',
                'verification_target': 'System prompt template rule extraction.'},
    'Q200': {   'id': 'Q200',
                'category': 'Category 12: Multi-File Conceptual / Method 1 Queries',
                'question': 'How does the system retrieve relevant campaign lore from the vector store when generating '
                            'the next turn in a story?',
                'tool_chain': '',
                'answer': 'Retrieving campaign lore when generating the next turn:\n'
                          'In `OllamaApi.progress_story()` (`src/api_workflows/call_api.py:75-162`):\n'
                          '1. Historical context: `get_history()` embeds each character message with '
                          '`embedding_model.embed_query(msg)` and queries `st.session_state.history_store` with `k=2` '
                          'filtered by `{"uuid": current_uuid}`.\n'
                          '2. Rules context: `create_history_aware_retriever` takes the chat history and queries '
                          '`st.session_state.vector_store` (the 5e rules handbook retriever).\n'
                          '3. Retrieval chain: `create_retrieval_chain` combines both retrieved rule context and '
                          'conversation history, streaming the generated turn via `rag_chain.stream()`.',
                'verification_target': 'Full multi-step RAG context retrieval pipeline.'}}


def get_benchmark_item(qid: str):
    """Retrieve a single benchmark question entry by ID (e.g. 'Q01')."""
    return BENCHMARK_DATASET.get(qid)


def get_questions_by_category(category_substring: str):
    """Filter benchmark items where category matches category_substring (case-insensitive)."""
    sub = category_substring.lower()
    return [
        item for item in BENCHMARK_DATASET.values()
        if sub in item.get("category", "").lower()
    ]
