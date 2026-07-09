from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from xenari_tool import Xenari


def test_known_phrase_generation():
    x = Xenari(REPO / "xenari.db")

    cases = {
        "I love you": "ra mex ka neq ta zrent sa xo",
        "you little bitch": "mex krengk frem",
        "I see the alien": "ra vi qex ka neq ta toq sa xo",
        "the alien sees me": "ra neq ka vi qex ta toq vi sa xo",
        "the alien is dangerous": "ra fatwih ka vi qex ta zux vi sa xo",
        "the hat is red": "ra rlis ka nu brid ta zux nu sa xo",
        "I approach the figure by the lake. The figure's hat blows off": (
            "ra vi loco na nu qlon ka neq ta frig sa xo. "
            "ra vi loco po brid ka vi cuq ta qruq vi sa xo"
        ),
    }

    for english, expected in cases.items():
        assert x.speak(english, evidential="assumed") == expected


def test_lookup_prefers_pronouns_and_synonyms():
    x = Xenari(REPO / "xenari.db")

    assert x.lookup("you")[0] == "mex"
    assert x.lookup("me")[0] == "neq"
    assert x.lookup("wrath")[0] == "nud"
    assert x.lookup("perilous")[0] == "fatwih"
