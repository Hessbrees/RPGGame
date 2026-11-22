# WERYFIKACJA IMPLEMENTACJI - 2 Graczy AI + GM + ilustracje

## ✅ Data weryfikacji: 2026-11-20 (poprzednia: 2026-04-30)

**Podsumowanie:** rdzeń gry (gracze AI, GM, szyna komunikatów, tryby rozmowy, RAG-i) działa i został rozszerzony o generowanie ilustracji (Stable Diffusion 1.5 + LoRA) z ewaluacją ilościową. Wcześniejsza weryfikacja z 2026-11-20 wykazała kilka błędów obniżających wiarygodność rozgrywki; siedem z nich (imię gracza w prompcie GM, stan gry liczony w kodzie, duplikaty w ChromaDB, dziennik sesji, powrót do rozmowy swobodnej, osobne modele, brak testów) zostało naprawionych i sprawdzonych testami jednostkowymi oraz przebiegami gry z Ollamą. Mechanika gry (walka k20, NPC, wybór scenariusza) nadal nie istnieje, a jakość narracji zależy od modelu (patrz „Nie zaimplementowane” i „Otwarte problemy”).

Legenda: ✅ działa i było sprawdzone w tej weryfikacji · 🟡 działa częściowo lub nie było sprawdzone · ❌ brak · 🔧 wymaga poprawki

## 🔄 AKTUALIZACJA: Język polski
- **Data**: 2026-04-30
- **Zmiana**: Wymuszenie odpowiedzi w języku polskim dla wszystkich agentów
- **Zmodyfikowane pliki**:
  - `src/agents/player_agent.py` - dodano "ZAWSZE ODPOWIADAJ WYŁĄCZNIE PO POLSKU"
  - `src/agents/game_master_agent.py` - dodano "ZAWSZE ODPOWIADAJ WYŁĄCZNIE PO POLSKU"
- **Status**: ✅ Zaimplementowane, w trakcie testowania

## 📋 ZAIMPLEMENTOWANE MODUŁY

### MODUŁ 1: Gracze AI ✅
- [x] 2 graczy AI zaimplementowani (Arin + Theron)
- [x] Osobowości zdefiniowane:
  - **Arin**: złodziej, przebiegły, skryty, nie ufa obcym
  - **Theron**: wojownik, odważny, honorowy, lojalny
- [x] PlayerAgent.decide_action() działa - gracze podejmują autonomiczne decyzje
- [x] Gracze zapisani w GameState.players z HP=100 i ekwipunkiem
- [x] Inicjalizacja przez _initialize_players() w orchestratorze

### MODUŁ 2: Message Bus ✅
- [x] message_history: list[dict] zaimplementowana
- [x] broadcast_message() dodaje wiadomości do szyny
- [x] get_visible_history() zwraca historię dla konkretnego gracza
- [x] Wszystkie komunikaty (GM, gracze, akcje) są broadcastowane

### MODUŁ 3: Tryby konwersacji ✅
- [x] ConversationMode.FREE - rozmowa swobodna
- [x] ConversationMode.TURN_BASED - tryb turowy
- [x] run_free_conversation() - gracze rozmawiają między sobą
- [x] run_turn_based_round() - każdy gracz po kolei
- [x] GM.should_end_free_conversation() - automatyczne przełączanie trybu
- [x] Przełączanie z FREE na TURN_BASED działa poprawnie
- [x] Powrót TURN_BASED → FREE po 3 rundach turowych (`TURN_ROUNDS_BEFORE_FREE`); koniec rozmowy swobodnej oceniany tylko z wiadomości bieżącej rozmowy
- [x] Numer tury rośnie w obu trybach (wcześniej w trybie swobodnym stał na 0)

### MODUŁ 4: Game Flow ✅
- [x] start_adventure() - GM rozpoczyna przygodę
- [x] display_game_state() - wyświetla HP, ekwipunek, turę
- [x] is_game_over() - sprawdza czy wszyscy gracze są nieprzytomni
- [x] get_ending() - zwraca zakończenie gry
- [x] Główna pętla w main.py: for turn in range(max_turns)

### MODUŁ 5: Zmodyfikowany main.py ✅
- [x] Usunięto input() - brak interakcji człowieka
- [x] GameOrchestrator inicjalizowany z num_players=2
- [x] Autonomiczna pętla 10 tur
- [x] Wyświetlanie stanu gry co turę
- [x] Argumenty CLI: `--illustrate`, `--lora`, `--turns`, `--open-gallery`, `--gm-model`, `--player-model`, `--keep-journal`
- [x] Wymuszone UTF-8 na wyjściu (emoji nie przerywają gry przy przekierowaniu do potoku w PowerShell)

### MODUŁ 7: Stan gry w kodzie, osobne modele, dziennik sesji, RAG bez duplikatów (nowy) ✅

- [x] **GM zna gracza:** prompt zawiera imię i klasę postaci wykonującej akcję, zasady z `JudgeRAG` oraz aktualny stan z `GameState.describe_state()` (wcześniej GM dostawał surowy słownik i mylił Arina z Theronem)
- [x] **Stan liczony w kodzie** (`src/game_state/state_updater.py`): po każdej akcji arbiter (drugie wywołanie LLM) zwraca JSON dla wszystkich aktywnych graczy (`hp_change`, `incapacitated`, `items_gained`, `items_lost`); kod waliduje (limit −50/+30 HP na zdarzenie, HP 0-100, maks. 3 przedmioty), stosuje zmiany i ustawia `active=False` przy 0 HP; zmiany są drukowane jako `[Stan] ...` i zapisywane w dzienniku
- [x] **Filtr narracji:** linie, w których GM sam wypisał słownik stanu (np. `{'hp': ...}`), są usuwane przed zapisem i ilustracją
- [x] **Gracze znają swój stan** (HP i ekwipunek dopisywane na końcu sytuacji w trybie turowym)
- [x] **ChromaDB bez duplikatów** (`BaseRAG`): odcisk zawartości plików i modelu embeddings w `chroma_db/rag_fingerprints.json`; indeks budowany od zera tylko przy zmianie danych; sprawdzone na prawdziwej bazie: każda kolekcja ma teraz 1 wpis i 1 unikalny tekst (wcześniej `lore`/`npcs`/`judge` 9/1, `chronicle` 79/42)
- [x] **Dziennik sesji:** na starcie poprzedni `journal.json` trafia do `data/chronicle/archive/`; powyżej 40 wpisów Kronikarz go kompresuje; opcja `--keep-journal` zachowuje stary
- [x] **Osobne modele:** `--gm-model` i `--player-model` (jeden dla wszystkich albo po jednym na gracza); modele Ollama spoza domyślnego są wyładowywane przed renderowaniem ilustracji
- [x] **Testy jednostkowe** (`pytest tests`, 37 testów, bez Ollamy dzięki atrapie LLM): indeksowanie RAG, parser i stosowanie zmian stanu, orkiestrator (imię gracza, HP, koniec gry, przełączanie trybów, dziennik, osobne modele), `image_gen` (parser sceny, prompt, statystyki)

### MODUŁ 6: Ilustracje z przebiegu gry (nowy) ✅

**Działa (sprawdzone):**
- [x] Pipeline `SceneDirector → PromptBuilder → ImageGenerator → Gallery` w trybie `deferred`: przebieg gry (4 tury, `--lora outputs/lora/style_r16/best`) wygenerował 3 obrazy, `index.jsonl` i `gallery.html`
- [x] Filtr ważności sceny (próg 4, pierwsza scena zawsze), limit obrazów, ilustrowana tylko narracja GM
- [x] Współdzielenie 6 GB VRAM: Ollama jest wyładowywana przed renderowaniem
- [x] Trening LoRA stylu (`scripts/train_lora.py`): 1000 kroków, ok. 1,2-2 s/krok, `val_loss` 0,1282 → 0,1247, CLIP Score walidacyjny 32,1 → ok. 33; wagi `best/` i `final/`
- [x] Przygotowanie zbioru (`scripts/prepare_dataset.py`): 82 train / 11 val, podział bez wycieku między wycinkami jednego obrazu
- [x] Eksperyment porównawczy (`scripts/run_experiments.py`): 14 warunków × 12 scen × 3 seedy = 504 obrazy; fazy specs/render/eval wznawialne; CLIP Score, wierność stylu, spójność (DINOv2-I, CLIP-I), bootstrap sparowany po scenach
- [x] Wnioski z eksperymentu: opis sceny od LLM daje ok. +5,6-6,2 pkt CLIP Score względem surowego tekstu (istotne); LoRA poprawia wierność stylu (+0,016, istotne), ale nie CLIP Score; kontekst (lore + karty postaci) zwiększa spójność postaci (DINOv2-I +0,21)
- [x] README zaktualizowane (architektura, konfiguracja IMAGE_*, trening, eksperyment)

**Nie sprawdzone / tylko częściowo:**
- 🟡 Tryb `inline` (obraz zaraz po zdarzeniu) - nigdy nie uruchamiany na żywo
- 🟡 Flaga `--open-gallery` - dodana, ale nie uruchamiana (sprawdzono tylko brak błędów składni)
- 🟡 Praca bez GPU (fallback CPU) i model Turbo (`IMAGE_MODEL_ID=...sd-turbo`) - obsłużone w konfiguracji, nietestowane
- 🟡 Kilka adapterów LoRA naraz (`IMAGE_LORA_PATHS` z średnikami) - kod jest, brak testu

**Nie ma:**
- ❌ LoRA dla poszczególnych postaci (pole `trigger_token` w `CharacterSheet` jest puste); spójność postaci opiera się tylko na tekstowych kartach postaci
- 🟡 Testy `image_gen` obejmują parser sceny, `PromptBuilder` i statystyki (`tests/test_image_gen.py`); brak testów `ImageGenerator` i pipeline'u (wymagają GPU)
- ❌ Ocena z udziałem ludzi; metryki mierzą zgodność z opisem i podobieństwo do stylu, nie estetykę
- ❌ Kontrola liczby i pozycji postaci na obrazie (np. scena z goblinami pokazała 4 wojowników bez goblinów)

## 🎮 OBSERWACJE Z TESTÓW

### Test 1: Autonomiczna rozgrywka
**Scenariusz**: Las Szeptów, 2 graczy AI, 10 tur max

**Zachowanie graczy AI**:
- ✅ Arin (złodziej) jest ostrożny, analizuje sytuację, szuka słabości
- ✅ Theron (wojownik) jest bezpośredni, honorowy, próbuje komunikacji
- ✅ Obaj gracze rozmawiają między sobą i reagują na siebie nawzajem
- ✅ Gracze używają różnych stylów (Arin: skryty, Theron: bezpośredni)

**Zachowanie GM**:
- ✅ Generuje szczegółową narrację wprowadzającą (Las Szeptów)
- ✅ Tworzy przeciwnika (skeletal creature z drzewem)
- ✅ Reaguje na akcje graczy
- ✅ Eskaluje napięcie i prowadzi do walki
- ✅ Automatycznie kończy rozmowę swobodną gdy gracze wspominają akcję

**Przełączanie trybów**:
- ✅ START: ConversationMode.FREE
- ✅ Gracze rozmawiają 2 rundy (6 wymian)
- ✅ GM wykrywa słowa kluczowe ("atak", "walka")
- ✅ Przełączenie na ConversationMode.TURN_BASED
- ✅ Rozpoczyna się tryb turowy z pojedynczymi akcjami

**Message Bus**:
- ✅ Wszystkie wiadomości są logowane do message_history
- ✅ Format: {"turn": X, "speaker": "...", "type": "...", "content": "...", "visible_to": ["all"]}
- ✅ Gracze widzą historię przed podjęciem decyzji (get_visible_history)

### Test 2: Przebieg po naprawach (2026-11-20, 6 tur, Ollama + llama3, bez ilustracji)

Źródła: log konsoli z pierwszego przebiegu po naprawach, `data/chronicle/journal.json` z kolejnego przebiegu oraz zapytanie do ChromaDB.

- ✅ Tury 0-2 w trybie swobodnym, 3-5 w turowym; po 3 rundach turowych GM wraca do rozmowy swobodnej (potwierdzone w logu komunikatem „GM kończy scenę”)
- ✅ GM zwraca się do właściwej postaci po imieniu i korzysta z zasad Sędziego (rzut k20 + modyfikator oraz AC pojawiają się w narracji)
- ✅ Stan liczony w kodzie: w dzienniku wpisy `Stan Arin: HP 100 -> 80`, `Stan Theron: HP 100 -> 90`, `Stan Arin: HP 80 -> 60`; w dzienniku brak słowników stanu gry i `'hp'`
- ✅ Wykryty i naprawiony błąd arbitra: w pierwszym przebiegu oceniał tylko gracza wykonującego akcję, więc narracja „Theron HP 0/100” nie zmieniła jego HP, a gra zakończyła się „sukcesem”; przypisał też −20 HP za samą groźbę. Teraz arbiter ocenia wszystkich graczy, a prompt wymaga jawnych obrażeń. Po poprawce sprawdzono go testami jednostkowymi i jednym przebiegiem (dziennik); nie sprawdzono, czy gra kończy się porażką przy 0 HP obu graczy
- 🟡 Nie widziałem logu konsoli z ostatniego przebiegu, więc komunikat końcowy i brak błędów na wyjściu nie są potwierdzone; użytkownik zgłosił, że proces po zakończeniu rozmowy „wisiał” (przyczyna nieznana, wcześniejsze przebiegi kończyły się normalnie)
- 🟡 Jakość narracji `llama3`: gracze zaczęli atakować siebie nawzajem po pomyłce modelu (GM opisał „dwóch ludzi”, a gracze uznali się za przeciwników); GM nadal dopisuje linie typu „Koncesje: Theron HP 0/100…”, których filtr słowników nie łapie
- 🟡 Pierwsza rozmowa swobodna kończy się po jednej wymianie (heurystyka słów kluczowych jest zbyt czuła)

## 📊 ZGODNOŚĆ Z TEZĄ DYPLOMOWĄ

### ✅ ZAIMPLEMENTOWANE wymagania z dokumentu
1. ✅ Wielu graczy AI (2 graczy: Arin, Theron)
2. ✅ Mistrz Gry LLM (GameMasterAgent)
3. ✅ RAG dla różnych domen (Lore, NPC, Rules, Chronicle) - działają, indeksy bez duplikatów; `CombatRAG` i `Reranker` istnieją, lecz nie są podłączone; folder `data/lore` ma tylko ok. 760 B (jeden fragment), więc lore jest bardzo skromne
4. ✅ Tryby konwersacji (FREE i TURN_BASED)
5. ✅ Wspólna szyna komunikacyjna (Message Bus)
6. ✅ Osobowości graczy (persona dict)
7. ✅ Autonomiczne podejmowanie decyzji (PlayerAgent.decide_action)
8. ✅ Rozgrywka bez ludzkiego inputu
9. ✅ Ilustracje z przebiegu gry (rozszerzenie spoza pierwotnej tezy: SD 1.5 + LoRA + ewaluacja)

### 🔄 CZĘŚCIOWO ZAIMPLEMENTOWANE
1. 🟡 Vibe Profiles - vibe zmienia tylko jedno zdanie w prompcie GM; wartość jest zaszyta w `main.py` (`"zrównoważona"`), brak wyboru w CLI; `data/player_preferences/` nie jest używane
2. 🟡 Dynamiczna trudność - `adjust_difficulty()` istnieje w `GameState` i `GameOrchestrator`, ale nic jej nie wywołuje; `difficulty` zawsze 1.0
3. 🟡 Tryby rozmowy - przełączanie w obu kierunkach działa (FREE → TURN_BASED heurystyką słów kluczowych, TURN_BASED → FREE po 3 rundach); heurystyka bywa zbyt czuła, a decyzji nie podejmuje GM-LLM
4. 🟡 Kronikarz - dziennik jest per sesja (archiwum), kompresja po >40 wpisach działa w teście jednostkowym, ale w żadnym przebiegu gry nie została wywołana (miały <40 wpisów); kronika nie trafia do promptów graczy
5. 🟡 Walidacja przez Sędziego - zasady z `JudgeRAG` trafiają do promptu GM (widoczne w narracji), ale kod nie egzekwuje zasad
6. 🟡 Szyna komunikatów - wszystkie wiadomości mają `visible_to: ["all"]`; wiadomości prywatne i `hidden_info` nie są używane
7. 🟡 Rzuty kostką - GM-LLM opisuje „rzuty” w tekście (np. k20 + 5 = 25), ale nie ma ich w kodzie, więc wyniki są zmyślone
8. 🟡 Stan gry (HP, ekwipunek, `active`) - aktualizowany w kodzie na podstawie oceny arbitra LLM; jakość zależy od modelu, a nie ma walidacji np. posiadania przedmiotu użytego w akcji
9. 🟡 Osobne modele dla GM i graczy - opcje CLI i obsługa w orkiestratorze są (testy jednostkowe), ale nie uruchomiono jeszcze gry z różnymi modelami

### ❌ NIE ZAIMPLEMENTOWANE (wymaga dalszej pracy)
1. ❌ Pełny system walki z k20 + modifier w kodzie (`CombatRAG` i `data/combat/` istnieją, ale nie są podłączone do orkiestratora)
2. ❌ Zarządzanie ekwipunkiem na poziomie akcji (walidacja posiadania, użycie przedmiotu)
3. ❌ NPC Agent - `add_npc()`/`play_npc()` nie są wywoływane; NPC w narracji (np. „Grunt”, „Screamer”) to halucynacje GM, a `active_npcs` pozostaje puste
4. ❌ Wybór scenariusza, vibe i liczby graczy w CLI (`start_adventure()` ma zaszyty „Las Szeptów”; `data/scenarios/` nieużywane)
5. ❌ Podłączenie `Reranker` (BM25/semantyczny) do któregokolwiek RAG - klasa jest tworzona w orkiestratorze, ale nieużywana
6. ❌ Eksperyment porównujący modele w rolach GM/gracz (cel pracy) - jest infrastruktura (`--gm-model`, `--player-model`), brak skryptu i metryk dla rozgrywki
7. ❌ Testy dla całej starej części (`test_core_functionality.py`, `test_polish.py`): to skrypty wymagające Ollamy, poza `pytest tests`; nie były uruchamiane

## 🎯 STAN KOMPONENTÓW (2026-11-20)

| Komponent | Status | Uwagi |
|-----------|--------|-------|
| Gracze AI (Arin, Theron) | ✅ | decyzje i dialogi działają; znają swój HP i ekwipunek; mogą mieć osobne modele (`--player-model`) |
| Mistrz Gry (narracja, reakcje) | 🟡 | zna gracza, zasady i stan; jakość tekstu zależy od modelu (`llama3` myli role, dopisuje linie stanu) |
| Szyna komunikatów | ✅ | broadcast i historia działają; brak wiadomości prywatnych |
| Tryby rozmowy | ✅ | FREE ↔ TURN_BASED w obie strony; heurystyki bywają zbyt czułe |
| RAG: Lore, NPC, Judge, Chronicle | ✅ | bez duplikatów (odcisk danych); lore ma tylko ok. 760 B |
| RAG: Combat, Reranker | ❌ | zaimplementowane, nie podłączone |
| GameState (HP, ekwipunek, `active`) | ✅ | aktualizowane w kodzie wg arbitra LLM; trudność, NPC i `hidden_info` nadal nieużywane |
| Dziennik (Kronikarz) | ✅ | sesje z archiwum, kompresja po >40 wpisach (tylko test jednostkowy) |
| Ilustracje (pipeline, galeria) | ✅ | sprawdzone w trybie `deferred` |
| Trening LoRA i eksperyment | ✅ | uruchomione, wyniki w `outputs/` i README |
| Testy automatyczne | ✅ | 37 testów jednostkowych (`pytest tests`); stare skrypty testowe poza zestawem |

Pokrycie wymagań tezy jest szacowane jakościowo: warstwa konwersacyjna, RAG i stan postaci działają, a mechanika gry (walka w kodzie, NPC, scenariusze) nie. Poprzednie liczbowe szacunki (70-75%) i liczby linii kodu zostały usunięte jako nieaktualne.

## 🔍 WNIOSKI

### Pozytywne
1. **Architektura działa** - RAG + Agents + Orchestrator to solidna podstawa
2. **Gracze AI są wiarygodni** - różne style, logiczne decyzje
3. **GM prowadzi fabułę** - tworzy napięcie, eskaluje sytuacje
4. **Tryby przełączają się automatycznie** - GM wykrywa potrzebę walki
5. **Kod jest modularny** - łatwo dodać nowe funkcje

### Problemy wykryte w weryfikacji

#### Priorytet wysoki - ✅ naprawione i sprawdzone (tabela opisuje stan przed poprawką)

Naprawy: 1 - imię i klasa gracza w prompcie GM; 2 - arbiter ustala HP/ekwipunek/`active`, kod je stosuje; 3 - odcisk danych w `BaseRAG`, indeks bez duplikatów; 4 - dziennik per sesja, kompresja, tura rosnąca też w trybie swobodnym; 5 - zasady Sędziego w prompcie GM; 6 - powrót do FREE po 3 rundach turowych; 7 - `--gm-model` i `--player-model`.

| # | Problem | Dowód | Proponowana poprawka |
|---|---------|-------|----------------------|
| 1 | GM nie wie, który gracz działa: `process_player_action()` nie przekazuje `player_name` do `react_to_player_action()` | w `journal.json` GM zwraca się do Therona jako „Arin", a Theron pojawia się jako NPC | przekazać imię i personę gracza do promptu GM |
| 2 | HP, ekwipunek i `active` nie są aktualizowane przez kod; narracja zawiera zmyślone słowniki „Stan gry: {...}" z innymi wartościami niż `GameState` | `display_game_state()` pokazuje HP 100/100, gdy GM pisze o 30 HP; `is_game_over()` nigdy nie zwróci `True` | GM zwraca ustrukturyzowany wynik (obrażenia, zmiany ekwipunku), kod waliduje i stosuje go w `GameState`; zakaz generowania stanu w tekście |
| 3 | Duplikaty w ChromaDB: `BaseRAG._build_index()` wczytuje dokumenty przy każdym starcie | kolekcja `lore`: 9 wpisów, 1 unikalny tekst; `npcs` 9/1; `judge` 9/1; `chronicle` 79/42; top-k zwraca kopie tego samego fragmentu | indeksować tylko, gdy kolekcja jest pusta, lub nadawać deterministyczne ID (hash pliku/fragmentu) |
| 4 | Dziennik `journal.json` jest trwały między sesjami, nie jest czyszczony ani kompresowany | 52 wpisy, w tym z testów; `compress_journal()` nigdy nie jest wołane; numer tury 0 powtarza się, bo `next_turn()` działa tylko w trybie turowym | osobny plik na sesję, wywołanie kompresji co N wpisów, zwiększanie tury także w trybie swobodnym |
| 5 | Wynik `JudgeRAG` jest ignorowany | `rules_context` w `process_player_action()` jest liczony i nieużywany; to dodatkowe zapytanie LLM na każdą akcję bez efektu | przekazać zasady do promptu GM albo usunąć zapytanie |
| 6 | Brak powrotu z TURN_BASED do FREE | `conversation_mode` jest ustawiany tylko na `TURN_BASED` | reguła lub decyzja GM kończąca walkę/scenę |
| 7 | Jeden model LLM dla wszystkich ról | `OLLAMA_MODEL` w `main.py`; brak parametrów dla GM i graczy | opcje `--gm-model`, `--player-model` (osobno dla każdego gracza) |

#### Priorytet średni

| # | Problem | Uwagi |
|---|---------|-------|
| 8 | `PlayerAgent` dostaje tylko ostatnie 500 znaków historii (`context[-500:]`), ucięte w środku zdania; brak dostępu do kroniki i lore | ograniczyć po granicy wiadomości, dodać streszczenie z kroniki |
| 9 | Jakość tekstu `llama3`: powtórzenia fragmentów między graczami, błędy gramatyczne, GM dopisuje własne opcje i stan | w eksperymencie `qwen2.5:7b` najlepiej rozpoznawał postać w scenie; warto sprawdzić go w roli GM |
| 10 | Dynamiczna trudność, NPC (`add_npc`/`play_npc`), `hidden_info` i wiadomości prywatne nie są używane | podłączyć albo usunąć martwy kod |
| 11 | Brak wyboru scenariusza i vibe w CLI | `--vibe`, `--scenario` zamiast stałych w `main.py` i `start_adventure()` |
| 12 | Testy `test_core_functionality.py` i `test_polish.py` to skrypty wymagające działającej Ollamy i LLM; funkcje z argumentem `orchestrator`/`llm` nie zadziałają pod `pytest` bez fixture; nie były uruchamiane | dodano 37 testów jednostkowych z atrapą LLM w `tests/` (✅); stare skrypty nadal poza zestawem (`pytest.ini` zbiera tylko `tests/`) |

#### Ilustracje - do poprawy

| # | Problem | Uwagi |
|---|---------|-------|
| 13 | Każda narracja GM uruchamia dodatkowe wywołania LLM (`lore_rag.query()` i `SceneDirector.analyze()`) jeszcze przed filtrem ważności | wydłuża turę; wykonać `lore_rag.query()` dopiero po przejściu filtra lub filtrować wstępnie regułami |
| 14 | Kontekst lore dla ilustracji pochodził z indeksu z duplikatami; w eksperymencie użyto retrievera top-2 | duplikaty usunięte; `data/lore` ma jednak tylko ok. 760 B (jeden fragment), więc kontekst to całe lore, a wpływ „kontekstu” w eksperymencie wynika głównie z kart postaci; po rozszerzeniu lore powtórzyć eksperyment |
| 15 | Eksperyment: wariant „kontekst" łączy lore i karty postaci | nie rozdziela ich wpływu; dodać osobne warunki |
| 16 | Eksperyment: tylko 12 scen; przedziały dla spójności są zbyt wąskie (jednostką jest para postać-seed, nie scena) | powiększyć zbiór scen, agregować po scenach/postaciach |
| 17 | LoRA nie poprawia CLIP Score, a jej wpływ mierzy metryka pośrednia (podobieństwo do środka zbioru treningowego) | dodać ocenę ludzką (np. porównanie parami) |
| 18 | Prompty zostały wygenerowane przed zmianą budżetu tokenów (`SAFETY_TOKENS`); źródłem prawdy jest `prompts.json` | faza `eval` czyta już `prompts.json`; przy ponownym uruchomieniu `render` obrazy powstaną z nowym budżetem |
| 19 | Sesje testowe dopisały wpisy do `data/chronicle/journal.json` | rozwiązane przez archiwizację; archiwa sesji testowych leżą w `data/chronicle/archive/` (3 pliki) i można je usunąć ręcznie |

Naprawione w tej sesji: zgodność z `transformers` 5.x w ewaluacji CLIP (`_as_tensor`), `diffusers` (`pipe.vae.enable_slicing()`, `dtype`), ucinanie bloku stylu w prompcie przez limit 77 tokenów CLIP, pomiar opóźnienia LLM (rozgrzewka modelu).

#### Otwarte problemy (wykryte po naprawach)

| # | Problem | Uwagi |
|---|---------|-------|
| 20 | Arbiter to dodatkowe wywołanie LLM na każdą akcję (dłuższe tury) i bywa zawodny (przypisał obrażenia za samą groźbę) | doprecyzowany prompt, ale nie zmierzono skuteczności; rozważyć rzuty i obrażenia w kodzie |
| 21 | GM dopisuje linie ze stanem w formie innej niż słownik (np. „Koncesje: Theron HP 0/100…”), których filtr nie usuwa; tekst może rozmijać się ze stanem | rozszerzyć filtr albo wymusić format odpowiedzi |
| 22 | Gracze mogą atakować siebie nawzajem po pomyłce modelu; w stanie gry nie ma wrogów (NPC) | podłączyć NPC i zabronić PvP w prompcie graczy; sprawdzić `qwen2.5:7b` jako GM |
| 23 | Heurystyka końca rozmowy swobodnej jest zbyt czuła (pierwsza rozmowa kończy się po jednej wymianie) | słowa kluczowe dopasowywane jako podciągi; zaweżić albo zlecić decyzję GM-LLM |
| 24 | Zgłoszone wiszące zakończenie procesu po końcu gry (przyczyna nieznana, nie odtworzone) | uruchomić z `faulthandler.dump_traceback_later(...)` i wkleić stosy wątków |
| 25 | Kompresja dziennika nie była jeszcze wywołana w prawdziwej grze (przebiegi miały <40 wpisów) | uruchomić dłuższą sesję (>10 tur) |

### Rekomendacje (kolejność)
1. Uruchomić grę z innym modelem GM (`--gm-model qwen2.5:7b`) i porównać z `llama3` - pierwsze realne użycie osobnych modeli (cel pracy)
2. Podłączyć NPC jako wrogów w stanie gry i zabronić walki graczy między sobą (pkt 22)
3. Przenieść rzuty k20 i obrażenia do kodu (`CombatRAG` + wynik przekazany GM) zamiast oceniać je z narracji
4. Rozszerzyć `data/lore` i powtórzyć eksperyment z ilustracjami; zwiększyć zbiór scen i dodać ocenę ludzką
5. Zbadać zawieszanie procesu po końcu gry (pkt 24) i przetestować dłuższą sesję z kompresją dziennika
6. Dodać wybór scenariusza i vibe w CLI; zdecydować, czy usunąć martwy kod (`Reranker`, `hidden_info`, `adjust_difficulty`)

---

**Status**: 🟢 CORE I ILUSTRACJE DZIAŁAJĄ - gra AI vs AI + GM jest demonstracyjna, stan postaci jest liczony w kodzie, a RAG-i i dziennik działają bez duplikatów; brakuje mechaniki walki w kodzie, NPC i wyboru scenariusza, a jakość narracji zależy od modelu (patrz „Otwarte problemy”)
