"""Focused Xenari behavior tests."""

from .support import load_fixtures


def test_known_phrase_generation(xenari):
    fixtures = load_fixtures()

    for case in fixtures["forward"]:
        assert xenari.speak(case["english"], evidential="assumed") == case["xenari"]

def test_bare_english_they_defaults_to_plural_known_req_ha(xenari):
    assert xenari.lookup("they")[0] == "req"
    assert xenari.lookup("their")[0] == "req"
    assert xenari.speak("They'll build the door tomorrow.", evidential="assumed") == (
        "ra nu zrump ka req ha ta mrob ve xo glent"
    )
    assert xenari.speak("Their door", evidential="assumed") == "req ha po zrump"
    assert xenari.reverse("ra nu zrump ka req ha ta mrob ve xo glent") == "they will build door tomorrow"

def test_sentence_final_time_words_are_preserved_in_both_directions(xenari):
    cases = {
        "I am going to work today": "fa nu kashatyong ka neq ta qeng ve xo bro",
        "I run tomorrow": "ka neq ta zaqa sa xo glent",
        "I ran yesterday": "ka neq ta zaqa lo xo hreh",
        "I work tonight": "ka neq ta qxundraz sa xo kohfrep",
    }
    for english, expected in cases.items():
        assert xenari.speak(english, evidential="assumed") == expected

    assert xenari.reverse("ka neq ta zaqa sa xo glent") == "I run tomorrow"
    assert xenari.reverse("ka neq ta zaqa lo xo hreh") == "I ran yesterday"
    assert xenari.reverse("ka neq ta qxundraz sa xo kohfrep") == "I operate tonight"
    assert "[fragment:" not in xenari.reverse("ka neq ta zaqa sa xo bro")
    assert "[warning:" not in xenari.reverse("ka neq ta zaqa sa xo bro")

def test_base6_numbers_and_math_particles_are_canon(xenari):
    numbers = {
        "0": "nul",
        "1": "ca",
        "2": "vriq",
        "3": "prit",
        "4": "qang",
        "5": "cum",
        "6": "ca xang",
        "7": "ca xang ca",
        "12": "vriq xang",
        "35": "cum xang cum",
        "36": "ca xang xang",
        "six": "ca xang",
        "seven": "ca xang ca",
    }
    for english, expected in numbers.items():
        assert xenari.speak(english, evidential="assumed") == expected
        assert xenari.reverse(expected) == str(int(english) if english.isdigit() else {"six": 6, "seven": 7}[english])

    expressions = {
        "2 plus 3": "vriq plomt prit",
        "6 minus 1": "ca xang krut ca",
        "2 times 3": "vriq vrot prit",
        "6 divided by 2": "ca xang flopq vriq",
        "3 equals 3": "prit zlem prit",
        "5 greater than 2": "cum grak vriq",
        "2 less than 5": "vriq vlox cum",
        "2 + 3": "vriq plomt prit",
        "2 < 5": "vriq vlox cum",
    }
    for english, expected in expressions.items():
        assert xenari.speak(english, evidential="assumed") == expected

    assert xenari.reverse("vriq plomt prit") == "2 plus 3"
    assert xenari.reverse("ca xang flopq vriq") == "6 divided by 2"
    assert xenari.translate("ca xang xang") == "36"

def test_reverse_uses_shared_fixtures(xenari):
    fixtures = load_fixtures()

    for case in fixtures["reverse"]:
        assert xenari.reverse(case["xenari"]) == case["english"]

def test_multiclause_hardening_regression_is_bounded_and_honest(xenari):
    case = load_fixtures()["hardening"]

    translated = xenari.speak(case["regression_input"], evidential="assumed")

    assert translated == case["expected"]
    for fragment in case["must_include"]:
        assert fragment in translated
    for fragment in case["must_not_include"]:
        assert fragment not in translated
    assert translated.count("[partial:") == 0
    assert translated.startswith("prax. ")
    assert xenari.speak("hey friend", evidential="assumed") == "prax"

def test_smart_apostrophes_expand_like_ascii_apostrophes(xenari):
    ascii_forms = "I'm working; I've gotten the result; You've seen it; we'll go; I can't go"
    for apostrophe in ("’", "‘", "ʼ", "＇"):
        smart_forms = ascii_forms.replace("'", apostrophe)
        assert xenari._expand_english_contractions(smart_forms) == xenari._expand_english_contractions(ascii_forms)

def test_work_senses_and_unknown_subjects_do_not_become_fake_roots(xenari):
    assert xenari._merge_compounds(["red", "hat"]) == ["red", "hat"]
    assert "rlisbrid" not in xenari.speak("I love the red hat", evidential="assumed")
    assert xenari.speak("creative work", evidential="assumed") == "flonx"
    assert "flonx" not in xenari.speak("I work", evidential="assumed")
    assert xenari.speak("the elevator was not working", evidential="assumed") == (
        "ka nu spokta ta qxundraz nu lo xo ngu"
    )
    assert xenari.speak("the turbolift was not working", evidential="assumed").startswith(
        "[untranslated: the turbolift was not working;"
    )

def test_kiss_and_bite_use_distinct_canon_roots(xenari):
    assert xenari.lookup("kiss") == ("nquxe", "to kiss / to press lips together")
    assert xenari.lookup("bite") == ("qruq'", "to bite")
    assert xenari.speak("I kiss you", evidential="assumed") == "ra mex ka neq ta nquxe sa xo"
    assert xenari.speak("I bite you", evidential="assumed") == "ra mex ka neq ta qruq' sa xo"

def test_everyday_verb_overrides_use_established_roots(xenari):
    assert xenari._known_verb_root("hear") == "cromq"
    assert xenari._known_verb_root("heard") == "cromq"
    assert xenari._known_verb_root("listen") == "grip"
    assert xenari._known_verb_root("seen") == "toq"
    for form, root in {
        "build": "mrob",
        "built": "mrob",
        "approach": "frig",
        "blow": "qruq",
        "whisper": "tyequga",
        "say": "krimp",
        "said": "krimp",
        "touch": "qabrerd",
        "touched": "qabrerd",
        "slam": "tulo",
        "slammed": "tulo",
        "stop": "semax",
        "stopped": "semax",
        "break": "zont",
        "broke": "zont",
        "broken": "zont",
        "wait": "trekq",
        "run": "zaqa",
        "open": "xleq",
        "help": "pegzos",
        "find": "trek",
        "enter": "logi",
        "belong": "mifzxuri",
        "solve": "pyoquqab",
        "solves": "pyoquqab",
        "solved": "pyoquqab",
        "solving": "pyoquqab",
        "send": "bern",
        "sent": "bern",
        "give": "flux",
        "gave": "flux",
        "take": "treq",
        "took": "treq",
        "sleep": "pramx",
        "rest": "ezlolax",
        "sit": "bezli",
        "stand": "cirku",
        "running": "zaqa",
    }.items():
        assert xenari._known_verb_root(form) == root

def test_casual_phrase_registry_precedes_structural_fallbacks(xenari):
    cases = {
        "Okay?!": "stux",
        "All right": "stux",
        "Greetings": "prax",
        "Hello, friend!": "prax",
        "Thanks :)": "gral",
        "Thanks for solving that": "gral troz ra zra ka mex ta pyoquqab lo xo",
        "Thank you": "ra mex ka neq ta gral sa xo",
        "Thank you for solving that": "ra mex ka neq ta gral sa xo troz ra zra ka mex ta pyoquqab lo xo",
        "My bad": "qezxol",
        "Oops!": "vrin",
        "Whoops!": "vrin",
        "Bye 👋": "qlox'",
        "See you later!": "qlox' qrolo",
        "Take care!": "qlox'",
        "No worries.": "shengtac nulxant",
        "No problem!": "shengtac nulxant",
        "Not a problem.": "shengtac nulxant",
        "That works": "naxq",
        "Works for me": "naxq",
        "Fair enough": "naxq",
        "Got it": "vreqclir",
        "Gotcha": "vreqclir",
        "Yep": "vroq",
        "Nope": "nguq",
        "Maybe later": "vex qrolo",
        "nice, sounds good": "naxu. naxq",
    }
    for english, expected in cases.items():
        assert xenari.speak(english, evidential="assumed") == expected

def test_audited_verb_map_roots_do_not_use_polluted_fallbacks(xenari):
    cases = {
        "I send water.": "ra nu cruq ka neq ta bern sa xo",
        "I give water.": "ra nu cruq ka neq ta flux sa xo",
        "I take water.": "ra nu cruq ka neq ta treq sa xo",
        "I sleep.": "ka neq ta pramx sa xo",
        "I rest.": "ka neq ta ezlolax sa xo",
        "I sit.": "ka neq ta bezli sa xo",
        "I stand.": "ka neq ta cirku sa xo",
    }
    for english, expected in cases.items():
        rendered = xenari.speak(english, evidential="assumed")
        assert rendered == expected
        assert " ta qlax " not in rendered
        assert " ta qlemp " not in rendered
        assert " ta rlenq " not in rendered
        assert " ta qax " not in rendered
        assert " ta hup " not in rendered
        assert " ta kroc " not in rendered

def test_shared_clause_corpus_is_bounded_shared_and_readable(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 3]
    reverse = [case for case in fixtures["reverse"] if case.get("loop") == 3]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 10
    assert len(reverse) >= 4
    assert len(stress) >= 5
    assert {case["family"] for case in forward} >= {
        "conditional", "purpose", "relative", "temporal", "temporal-wh",
    }
    assert all("[untranslated:" not in case["xenari"] for case in forward)

    initial_when = xenari.speak("When does the door open?", evidential="assumed")
    temporal_when = xenari.speak("When the door opens, I run.", evidential="assumed")
    unsupported_relative = xenari.speak(
        "The alien that the woman said she saw ran.", evidential="assumed"
    )

    assert initial_when == "qan qro ka nu zrump ta xleq nu sa xo"
    assert temporal_when.startswith("su cruv ")
    assert unsupported_relative.startswith("qex [partial: unsupported relative clause:")
    assert all("kam" not in case["xenari"].split() for case in forward)

def test_modifier_corpus_is_bounded_shared_and_readable(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 4]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 15
    assert len(stress) >= 6
    assert {case["family"] for case in forward} >= {
        "comparative", "conditional", "possessive", "purpose",
        "quantity", "relative", "superlative", "temporal",
    }
    assert all("[untranslated:" not in case["xenari"] for case in forward)

    comparative = xenari.speak("The alien is taller than the human.", evidential="assumed")
    superlative = xenari.speak("That is the fastest ship", evidential="assumed")
    no_water = xenari.speak("No water", evidential="assumed")
    no_people = xenari.speak("No people open the door.", evidential="assumed")

    assert comparative.startswith("ra sump maq ")
    assert "comparison-standard canon conflict" in comparative
    assert superlative == "ra nu suhpi kag qruv ka nu zra ta zux nu sa xo"
    assert no_water == "cruq nulxant"
    assert no_people == "ra nu zrump ka vi zifrelk nulxant ta xleq vi sa xo"
    assert "ngu" not in no_water.split()
    assert "ngu" not in no_people.split()
    for stale_root in {"qren", "trox", "xlu"}:
        assert stale_root not in comparative.split()

def test_dialogue_sound_and_imperative_corpus_is_bounded_and_honest(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 5]
    reverse = [case for case in fixtures["reverse"] if case.get("loop") == 5]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 15
    assert len(reverse) >= 1
    assert len(stress) >= 7
    assert {case["family"] for case in forward} >= {
        "dialogue", "imperative", "quote", "sound", "sound-report",
        "stage-direction", "typography", "vocalization", "vocalization-gap",
    }
    assert xenari._known_verb_root("slams") == "tulo"
    assert xenari._known_verb_root("whispered") == "tyequga"

    repeated_beep = xenari.speak("Beep beep beep.", evidential="assumed")
    unknown_ugh = xenari.speak("Ugh...", evidential="assumed")
    negative_command = xenari.speak("Don't touch that!", evidential="assumed")

    assert repeated_beep == "nqozo nqozo nqozo"
    assert " nu" not in repeated_beep
    assert unknown_ugh == "[untranslated: ugh; no Xenari root for: ugh]"
    assert negative_command == "ra nu zra ta qabrerd vi ko xo ngu"
    assert " va" not in negative_command
    assert "ka neq" not in negative_command

def test_fuzz_safety_corpus_is_shared_and_honest(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 6]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 10
    assert len(stress) >= 6
    assert {case["family"] for case in forward} >= {
        "empty-input", "imperative", "speaker-label",
        "speaker-stage", "stage-direction",
    }

    assert xenari.speak("...", evidential="assumed") == "[untranslated: no translatable content]"
    assert xenari.speak("   ", evidential="assumed") == "[untranslated: no translatable content]"
    assert xenari.speak("Run!", evidential="assumed") == "ta zaqa vi ko xo"
    assert xenari.speak("Don't run.", evidential="assumed") == "ta zaqa vi ko xo ngu"
    assert xenari.speak("Help me!", evidential="assumed") == (
        "ra vi neq ta pegzos vi ko xo"
    )
    assert xenari.speak("Translate this!", evidential="assumed") == (
        "ra nu praq ta nrotm vi ko xo"
    )
    assert xenari.speak("Reverse engineer this!", evidential="assumed") == (
        "ra nu praq ta halbru vi ko xo"
    )
    assert xenari.speak("NYX: Shhh.", evidential="assumed") == "shava"
    assert xenari.speak("MARA (O.S.): Beep beep.", evidential="assumed") == "nqozo nqozo"
    assert xenari.speak("(whispers) shhh.", evidential="assumed") == (
        "[partial: omitted subject for action: whisper]. shava"
    )
    assert "ka neq" not in xenari.speak("Run!", evidential="assumed")
    assert " va" not in xenari.speak("Don't run.", evidential="assumed")
    for english in ("run!", "don't run!", "help me!", "translate this!", "reverse engineer this!"):
        rendered = xenari.speak(english, evidential="assumed")
        assert xenari.reverse(rendered).casefold() == english.casefold()

def test_target_language_imperatives_precede_unsupported_fallback(xenari):
    expected_prefix = "ra nu hune fa nu bivuzqa uqel po zuqra ta "
    expected_suffix = " vi ko xo"
    for english, verb_root in {
        "Translate this sentence to English": "nrotm",
        "Translate this sentence back to English": "nrotm",
        "Reverse engineer this sentence back to English": "halbru",
        "Reverse-engineer this sentence back to English": "halbru",
        "Decode this sentence to English": "nimixu",
        "Decipher this sentence to English": "nimixu",
    }.items():
        assert xenari.speak(english, evidential="assumed") == (
            f"{expected_prefix}{verb_root}{expected_suffix}"
        )

def test_noun_subject_auxiliaries_copulas_progressives_and_possession_keep_roles(xenari):
    cases = {
        "The dog eats the hat.": "ra nu brid ka vi zrenq ta xlof vi sa xo",
        "The dog does not see the alien.": "ra vi qex ka vi zrenq ta toq vi sa xo ngu",
        "Does the dog run?": "ka vi zrenq ta zaqa vi sa xo va",
        "Did the alien see the dog?": "ra vi zrenq ka vi qex ta toq vi lo xo va",
        "The dog is dangerous.": "ra fatyih ka vi zrenq ta zux vi sa xo",
        "Is the dog dangerous?": "ra fatyih ka vi zrenq ta zux vi sa xo va",
        "I am running.": "ka neq ta zaqa sa xo",
        "The dog is running.": "ka vi zrenq ta zaqa vi sa xo",
        "The dog was not working.": "ka vi zrenq ta qxundraz vi lo xo ngu",
        "The dog has the hat.": "ra nu brid ka vi zrenq ta xrong vi sa xo",
    }
    for english, expected in cases.items():
        rendered = xenari.speak(english, evidential="assumed")
        assert rendered == expected
        if not english.startswith("I "):
            assert "ka neq" not in rendered

def test_reverse_autodetects_casual_roots_english_label_and_imperatives(xenari):
    cases = {
        "stux": "ok",
        "naxq": "yes",
        "naxu": "nice",
        "bivuzqa uqel po zuqra": "English",
        "ra nu hune fa nu bivuzqa uqel po zuqra ta nrotm vi ko xo": (
            "translate sentence to English!"
        ),
        "ta grip vi ko xo": "listen!",
        "ta semax vi ko xo naxru": "please stop!",
        "ra nu zrump ta xleq vi ko xo ngu": "don't open door!",
        "ra nu zra ta qabrerd vi ko xo ngu": "don't touch that!",
        "gral troz ra zra ka mex ta pyoquqab lo xo": "thanks for solving that",
        "ra mex ka neq ta gral sa xo troz ra zra ka mex ta pyoquqab lo xo": (
            "thank you for solving that"
        ),
    }
    for source, english in cases.items():
        assert xenari.reverse(source) == english
        assert xenari.translate(source) == english

def test_coordination_and_intransitive_fuzz_is_bounded(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 7]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 8
    assert len(stress) >= 5
    assert {case["family"] for case in forward} >= {
        "animacy", "coordination", "intransitive",
        "question", "question-gap", "speaker-stage",
    }

    assert xenari.speak("The door opens.", evidential="assumed") == "ka nu zrump ta xleq nu sa xo"
    assert xenari.speak("The alien runs quickly.", evidential="assumed") == (
        "ka vi qex ta zaqa vi sa xo"
    )
    assert xenari.speak("The dog runs slowly.", evidential="assumed") == (
        "ka vi zrenq ta zaqa vi sa xo"
    )
    assert xenari.speak("I run and she waits.", evidential="assumed") == (
        "ka neq ta zaqa sa xo. xen ka leq ta trekq sa xo"
    )
    assert xenari.speak("Why run?", evidential="assumed") == (
        "[partial: unsupported subjectless question: why run]"
    )
    assert "ra nu zrump ka neq ta xleq" not in xenari.speak("The door opens.", evidential="assumed")
    assert "ra nu xen" not in xenari.speak("I run and she waits.", evidential="assumed")

def test_transitive_coordination_uses_reviewed_roles(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 8]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 7
    assert len(stress) >= 5
    assert {case["family"] for case in forward} >= {"coordination", "transitive"}

    assert xenari.speak("The alien sees the dog.", evidential="assumed") == (
        "ra vi zrenq ka vi qex ta toq vi sa xo"
    )
    assert xenari.speak("The dog sees the alien.", evidential="assumed") == (
        "ra vi qex ka vi zrenq ta toq vi sa xo"
    )
    assert xenari.speak("I see the alien and run.", evidential="assumed") == (
        "ra vi qex ka neq ta toq sa xo. xen ka neq ta zaqa sa xo"
    )
    assert xenari.speak("The dog sees the alien and runs.", evidential="assumed") == (
        "ra vi qex ka vi zrenq ta toq vi sa xo. xen ka vi zrenq ta zaqa vi sa xo"
    )
    assert "ka neq ta toq" not in xenari.speak("The alien sees the dog.", evidential="assumed")
    assert "ra vi qex xen" not in xenari.speak("I see the alien and run.", evidential="assumed")

def test_colon_quotes_do_not_become_speaker_labels(xenari):
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 9]

    assert len(forward) >= 3
    assert {case["family"] for case in forward} >= {"colon-quote", "speaker-colon"}
    assert xenari.speak("She whispers: shhh.", evidential="assumed") == (
        "ka leq ta tyequga sa xo. shava"
    )
    assert xenari.speak("ALEX: She whispers: shhh.", evidential="assumed") == (
        "ka leq ta tyequga sa xo. shava"
    )
    assert xenari.speak("ALEX: She says: run.", evidential="assumed") == (
        "ka leq ta krimp sa xo. ta zaqa vi ko xo"
    )
    assert xenari.speak("NYX: Shhh.", evidential="assumed") == "shava"

def test_reverse_reads_structured_clause_boundaries(xenari):
    assert xenari.reverse(
        "pevoq ra vi qex ka neq ta toq sa xo ti ka neq ta zaqa ve xo"
    ) == "if I see alien, then I will run"
    assert xenari.reverse(
        "pevoq ra xleq ka nu zrump ta zux nu sa xo ti ka neq ha ta logi pe xo"
    ) == "if door is open, then we could enter"
    assert xenari.reverse(
        "su cruv ka nu zrump ta xleq nu sa xo ti ka neq ta zaqa sa xo"
    ) == "when door opens, I run"
    assert xenari.reverse(
        "ka vi habdazluc su zre ra nu zrump ta zont vi lo xo "
        "ti ta zaqa vi sa xo"
    ) == "person who broke door runs"


def test_conditional_state_predicates_keep_the_copula_frame(xenari):
    assert xenari.speak(
        "If the door is open, we can enter.", evidential="assumed"
    ) == "pevoq ra xleq ka nu zrump ta zux nu sa xo ti ka neq ha ta logi pe xo"
    assert xenari.speak(
        "If the door is not open, we can wait.", evidential="assumed"
    ) == (
        "pevoq ra xleq ka nu zrump ta zux nu sa xo ngu "
        "ti ka neq ha ta trekq pe xo"
    )

def test_content_questions_and_safe_noun_subjects_keep_their_roles(xenari):
    why = xenari.speak("Why did the elevator stop?", evidential="assumed")
    where = xenari.speak("Where will you go?", evidential="assumed")
    who = xenari.speak("Who broke the red window?", evidential="assumed")
    when = xenari.speak("When does the door open?", evidential="assumed")

    assert why == "voq ka nu spokta ta semax nu lo xo"
    assert where == "qur ka mex ta qeng ve xo"
    assert who == "qan vi ra nu xlonqtoq rlis ta zont vi lo xo"
    assert when == "qan qro ka nu zrump ta xleq nu sa xo"
    assert " va" not in why
    assert " va" not in where
    assert " va" not in who
    assert " va" not in when
    assert xenari.speak("Have you seen my hat?", evidential="assumed").endswith(" va")
    assert xenari.reverse(who) == "who broke red window?"
    assert xenari.reverse(when) == "when does door open?"
    assert xenari.speak("the elevator stopped", evidential="assumed") == (
        "ka nu spokta ta semax nu lo xo"
    )
    assert xenari.speak("the door slammed", evidential="assumed") == (
        "ka nu zrump ta tulo nu lo xo"
    )

def test_reverse_warns_when_recovering_malformed_clause_frames(xenari):
    malformed = (
        "to fa nu flonx ka nu hey ta qeng nu ve xo ngu na nu xenari "
        "ka nu qzecmru ta qranx nu sa xo mex"
    )

    reversed_text = xenari.reverse(malformed)

    assert "[unknown: hey] will not go" in reversed_text
    assert "anyway throw" in reversed_text
    assert "[warning:" in reversed_text
    assert "recovered separate fragments" in reversed_text

def test_auto_translate_and_inspect_helpers(xenari):
    assert xenari.translate("I love you", evidential="assumed") == "ra mex ka neq ta zrent sa xo"
    assert xenari.translate("ra mex ka neq ta zrent sa xa") == "I love you"
    assert xenari.translate("prax") == "hello"

    report = xenari.inspect_term("fatyih")
    assert "Root: fatyih" in report
    assert "dangerous" in report
    assert "Review-near meanings:" in report

def test_translator_preserves_plural_forms_questions_evidence_and_complements(xenari):
    assert "lamiy" in xenari.speak("The glasses open.", evidential="assumed")
    assert "klam" in xenari.speak("The pants open.", evidential="assumed")
    assert "shirxush" in xenari.speak("The shorts open.", evidential="assumed")
    assert xenari.speak("I loved you.", evidential="assumed") == "ra mex ka neq ta zrent lo xo"
    assert xenari.speak("I kissed you.", evidential="assumed") == "ra mex ka neq ta nquxe lo xo"
    assert xenari.speak("I heard you.", evidential="auto") == "ra mex ka neq ta cromq lo xi"
    assert xenari.speak("I saw the alien", evidential="auto") == "ra vi qex ka neq ta toq lo xa"
    assert xenari.speak("You love me?", evidential="assumed").endswith(" va")
    assert not xenari.speak("You love me.", evidential="assumed").endswith(" va")
    assert xenari.speak("Do you not love me?", evidential="assumed").endswith("ngu va")
    for sentence in ("I want to eat food", "I need to go"):
        rendered = xenari.speak(sentence, evidential="assumed")
        assert rendered.startswith("[partial:")
        assert "infinitive complement retained" in rendered

def test_reverse_imperatives_keep_verb_and_goal_meaning(xenari):
    assert xenari.reverse("ta trekq vi ko xo") == "wait!"
    assert xenari.reverse("ta qroz vi ko xo") == "fuck!"
    assert xenari.reverse("fa vi cuq ta grip vi ko xo") == "listen to wind!"
    assert xenari.reverse("ra neq po ngox ta qroz vi ko xo") == "fuck my ass!"

def test_base6_numbers_and_math_use_productive_xang_places(xenari):
    cases = {
        "zero": "nul",
        "one": "ca",
        "five": "cum",
        "six": "ca xang",
        "seven": "ca xang ca",
        "twelve": "vriq xang",
        "35": "cum xang cum",
        "36": "ca xang xang",
        "2 + 3": "vriq plomt prit",
        "six equals six": "ca xang zlem ca xang",
        "seven greater than five": "ca xang ca grak cum",
        "one over two": "ca nok vriq",
    }
    for english, expected in cases.items():
        assert xenari.speak(english, evidential="assumed") == expected

    assert xenari.reverse("ca xang") == "6"
    assert xenari.reverse("ca xang ca") == "7"
    assert xenari.reverse("vriq xang") == "12"
    assert xenari.reverse("vriq plomt prit") == "2 plus 3"
    assert xenari.reverse("ca xang zlem ca xang") == "6 equals 6"

def test_productive_base6_numbers_work_inside_quantity_noun_phrases(xenari):
    assert xenari.speak("one dick", evidential="assumed") == "kroxvi fqam"
    assert xenari.speak("five dicks", evidential="assumed") == "kroxvi cum"
    assert xenari.speak("six dicks", evidential="assumed") == "kroxvi ca xang"
    assert xenari.speak("seven dicks", evidential="assumed") == "kroxvi ca xang ca"
    assert xenari.speak("I have six dicks", evidential="assumed") == (
        "ra nu kroxvi ca xang ka neq ta xrong sa xo"
    )
    assert xenari.speak("I have 12 dicks", evidential="assumed") == (
        "ra nu kroxvi vriq xang ka neq ta xrong sa xo"
    )
