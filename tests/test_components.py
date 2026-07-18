"""Explicit component ownership and flat-API compatibility tests."""

from xenari.components import (
    CurationService,
    HealthService,
    LexiconService,
    TranslationService,
)
from xenari.services.curation import CurationMixin
from xenari.services.export import ExportMixin
from xenari.services.health import HealthMixin
from xenari.services.llm import LlmMixin
from xenari.services.lookup import LookupMixin
from xenari.translate import TranslatorMixin


def test_facade_uses_explicit_components_instead_of_behavior_mixins(fresh_xenari):
    assert isinstance(fresh_xenari.lexicon_service, LexiconService)
    assert isinstance(fresh_xenari.translator, TranslationService)
    assert isinstance(fresh_xenari.curation, CurationService)
    assert isinstance(fresh_xenari.health, HealthService)

    inherited_mixins = (
        LookupMixin,
        TranslatorMixin,
        LlmMixin,
        ExportMixin,
        HealthMixin,
        CurationMixin,
    )
    assert not isinstance(fresh_xenari, inherited_mixins)


def test_component_methods_and_flat_api_share_one_state(fresh_xenari):
    assert fresh_xenari.lexicon_service.lookup("you") == fresh_xenari.lookup("you")
    assert fresh_xenari.translator.speak("I love you") == fresh_xenari.speak(
        "I love you"
    )
    assert fresh_xenari.health.stats() == fresh_xenari.stats()
    assert fresh_xenari.curation.export_json() == fresh_xenari.export_json()


def test_components_can_use_cross_service_helpers(fresh_xenari):
    # Translation uses lookup helpers and the health service uses translation;
    # neither component inherits the other's implementation mixin.
    assert fresh_xenari.translator.compound("lake", "water") == fresh_xenari.compound(
        "lake", "water"
    )
    doctor_ok, doctor_report = fresh_xenari.health.doctor()
    assert doctor_ok, doctor_report


def test_forwarded_methods_remain_discoverable(fresh_xenari):
    discovered = dir(fresh_xenari)
    for name in ("lookup", "speak", "llm_context", "export_json", "doctor", "coin_root"):
        assert name in discovered
