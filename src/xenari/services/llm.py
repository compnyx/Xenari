import re
from typing import Dict, List

from ..translate.report import TranslationReport, build_translation_report


class LlmMixin:
    """LLM bridge helpers.

    These helpers do not call a model. They package canon context for an LLM
    translator and lint model-proposed Xenari for objective canon violations.
    """

    def translation_report(
        self, text: str, tense: str = "auto", evidential: str = "auto"
    ) -> TranslationReport:
        """Return deterministic output with explicit completeness diagnostics."""
        direction = "xenari_to_english" if self.looks_xenari(text) else "english_to_xenari"
        output = (
            self.reverse(text)
            if direction == "xenari_to_english"
            else self.speak(text, tense=tense, evidential=evidential)
        )
        return build_translation_report(source=text, direction=direction, output=output)

    def _llm_particle_roots(self):
        particles = set(self.p.values())
        particles.update({
            "pevoq", "frex", "troz", "zre", "vro", "cruv", "prexq", "vrem",
            "qlez",
        })
        return particles

    def _llm_tokenize_xenari(self, text: str) -> List[str]:
        return re.findall(r"[a-z']+", text.lower())

    def _llm_attested_verb_roots(self):
        """Return roots with explicit verb evidence in reviewed canon data."""
        roots = set(self.verb_map.values())
        roots.update(self.db.attested_verb_roots())
        return roots

    @staticmethod
    def _llm_matching_ti(tokens: List[str], start: int) -> int:
        """Find the ``ti`` that closes a structural ``su`` or ``pevoq``."""
        depth = 1
        for index in range(start + 1, len(tokens)):
            if tokens[index] in {"su", "pevoq"}:
                depth += 1
            elif tokens[index] == "ti":
                depth -= 1
                if depth == 0:
                    return index
        return -1

    def _llm_clause_regions(self, tokens: List[str], mode: str = "finite") -> List[Dict[str, object]]:
        """Split known structured frames into independently lintable clauses.

        Xenari conditionals, temporal subordinates, relative clauses, and
        purpose clauses can contain more than one ``ta`` inside one written
        sentence. Treating that sentence as a flat clause produces false
        repeated-marker errors, so the hard linter follows the canon boundary
        particles before validating each region.
        """
        tokens = list(tokens)
        while tokens and tokens[0] in {"kex", "xen", "noq", "qlez"}:
            tokens = tokens[1:]
        if not tokens:
            return []

        if tokens[0] == "pevoq":
            boundary = self._llm_matching_ti(tokens, 0)
            if boundary >= 0:
                return (
                    self._llm_clause_regions(tokens[1:boundary], "conditional")
                    + self._llm_clause_regions(tokens[boundary + 1:], mode)
                )

        if len(tokens) > 1 and tokens[0] == "su" and tokens[1] in {
            "cruv", "prexq", "vrem", "troz", "truq",
        }:
            boundary = self._llm_matching_ti(tokens, 0)
            if boundary >= 0:
                return (
                    self._llm_clause_regions(tokens[2:boundary], "subordinate")
                    + self._llm_clause_regions(tokens[boundary + 1:], mode)
                )

        for index in range(len(tokens) - 1):
            if tokens[index:index + 2] not in (["su", "zre"], ["su", "vro"]):
                continue
            boundary = self._llm_matching_ti(tokens, index)
            if boundary < 0:
                break
            matrix = tokens[:index] + tokens[boundary + 1:]
            relative = tokens[index + 2:boundary]
            return (
                self._llm_clause_regions(matrix, mode)
                + self._llm_clause_regions(relative, "relative")
            )

        if "frex" in tokens:
            boundary = tokens.index("frex")
            return (
                self._llm_clause_regions(tokens[:boundary], mode)
                + self._llm_clause_regions(tokens[boundary + 1:], "purpose")
            )

        return [{"tokens": tokens, "mode": mode}]

    def _llm_english_hints(self, text: str, limit: int = 40) -> List[Dict[str, str]]:
        words = re.findall(r"[a-z']+", self._expand_english_contractions(text))
        hints = []
        seen = set()
        for word in words:
            if word in seen or word in self.skip_words:
                continue
            seen.add(word)
            root = self._known_verb_root(word)
            source = "verb_map"
            if not root:
                root, _meaning = self.lookup(word)
                source = "lookup"
            if root:
                hints.append({
                    "english": word,
                    "root": root,
                    "meaning": self.lexicon.get(root, ""),
                    "source": source,
                })
            else:
                hints.append({
                    "english": word,
                    "root": "",
                    "meaning": "",
                    "source": "missing",
                })
            if len(hints) >= limit:
                break
        return hints

    def _llm_xenari_hints(self, text: str, limit: int = 80) -> List[Dict[str, str]]:
        particles = self._llm_particle_roots()
        hints = []
        seen = set()
        for token in self._llm_tokenize_xenari(text):
            if token in seen:
                continue
            seen.add(token)
            if token in particles:
                kind = "particle"
                meaning = "grammar particle"
            elif token in self.lexicon:
                kind = "root"
                meaning = self.lexicon[token]
            else:
                kind = "unknown"
                meaning = ""
            hints.append({"token": token, "kind": kind, "meaning": meaning})
            if len(hints) >= limit:
                break
        return hints

    def lint_xenari_candidate(self, candidate: str) -> Dict[str, object]:
        """Hard-check an LLM-proposed Xenari string.

        This is intentionally not a semantic judge. It only checks objective
        constraints: known roots/particles and simple finite-clause shape.
        """
        particles = self._llm_particle_roots()
        tense_roots = {"sa", "lo", "ve", "du", "pe", "ko"}
        evidence_roots = {"xa", "xe", "xi", "xo", "zu"}
        case_markers = {"ra", "ka", "na", "fa", "mo"}
        ignorable_after_ta = {"vi", "nu"}
        attested_verb_roots = self._llm_attested_verb_roots()
        tokens = self._llm_tokenize_xenari(candidate)
        unknown = sorted({
            token for token in tokens
            if token not in particles and token not in self.lexicon
        })
        errors = []
        warnings = []
        frames = []

        if not tokens:
            errors.append("no Xenari tokens found")

        if self._reverse_number_or_math(" ".join(tokens)) is not None:
            frames.append({"type": "number_or_math", "tokens": tokens})
        else:
            expected_boundaries = tokens.count("su") + tokens.count("pevoq")
            if tokens.count("ti") != expected_boundaries:
                errors.append(
                    "unbalanced structural boundaries: "
                    f"expected {expected_boundaries} ti marker(s), found {tokens.count('ti')}"
                )
            written_clauses = [
                self._llm_tokenize_xenari(part)
                for part in re.split(r"[.!?]+", candidate)
                if self._llm_tokenize_xenari(part)
            ] or ([tokens] if tokens else [])
            regions = []
            for clause_tokens in written_clauses:
                regions.extend(self._llm_clause_regions(clause_tokens))
            for index, region in enumerate(regions, start=1):
                clause_tokens = region["tokens"]
                mode = region["mode"]
                frame = {
                    "index": index,
                    "tokens": clause_tokens,
                    "mode": mode,
                    "type": "fragment",
                }
                frames.append(frame)
                if "ta" not in clause_tokens:
                    if any(marker in clause_tokens for marker in case_markers):
                        errors.append(
                            f"clause {index}: case marker present without verb marker ta"
                        )
                    continue

                frame["type"] = "finite_or_imperative"
                ta_index = clause_tokens.index("ta")
                if clause_tokens.count("ta") > 1:
                    errors.append(f"clause {index}: repeated verb marker ta")
                if "ka" in clause_tokens and clause_tokens.index("ka") > ta_index:
                    errors.append(f"clause {index}: subject marker ka appears after ta")
                for marker in case_markers - {"ka"}:
                    if marker in clause_tokens and clause_tokens.index(marker) > ta_index:
                        errors.append(
                            f"clause {index}: case marker {marker} appears after ta"
                        )
                if (
                    mode != "relative"
                    and "ka" not in clause_tokens
                    and "ko" not in clause_tokens[ta_index + 1:]
                ):
                    errors.append(
                        f"clause {index}: finite non-imperative frame missing ka subject marker"
                    )

                verb_index = ta_index + 1
                while verb_index < len(clause_tokens) and clause_tokens[verb_index] in ignorable_after_ta:
                    verb_index += 1
                if verb_index >= len(clause_tokens):
                    errors.append(f"clause {index}: ta has no verb root")
                    continue
                verb_root = clause_tokens[verb_index]
                frame["verb"] = verb_root
                if verb_root in particles:
                    errors.append(f"clause {index}: ta is followed by particle {verb_root}, not a verb root")
                elif verb_root in self.lexicon and verb_root not in attested_verb_roots:
                    errors.append(
                        f"clause {index}: root {verb_root} is not attested as a verb"
                    )

                tail = clause_tokens[verb_index + 1:]
                tense_positions = [i for i, token in enumerate(tail) if token in tense_roots]
                if not tense_positions:
                    if mode != "purpose":
                        errors.append(f"clause {index}: missing tense/aspect root after verb")
                    continue
                if len(tense_positions) > 1:
                    errors.append(f"clause {index}: multiple tense/aspect roots")
                tense_pos = tense_positions[0]
                frame["tense"] = tail[tense_pos]
                evidentials = [token for token in tail[tense_pos + 1:] if token in evidence_roots]
                evidence = evidentials[0] if evidentials else ""
                if evidence:
                    frame["evidential"] = evidence
                    if len(evidentials) > 1:
                        errors.append(f"clause {index}: multiple evidential roots")
                else:
                    errors.append(f"clause {index}: missing evidential root after tense/aspect")

                for marker in ("ra", "ka", "na", "fa", "mo"):
                    if clause_tokens.count(marker) > 1:
                        errors.append(f"clause {index}: repeated marker {marker}")

        if unknown:
            errors.append("unknown root or particle: " + ", ".join(unknown))

        return {
            "schema": "xenari.llm_lint.v1",
            "ok": not errors,
            "candidate": candidate,
            "tokens": tokens,
            "unknown_tokens": unknown,
            "errors": errors,
            "warnings": warnings,
            "frames": frames,
            "tool_role": "hard canon linter only; not a semantic judge",
        }

    def llm_context(self, text: str, tense: str = "auto", evidential: str = "auto") -> Dict[str, object]:
        """Return a compact canon packet for an LLM translation sidecar."""
        direction = "xenari_to_english" if self.looks_xenari(text) else "english_to_xenari"
        deterministic = (
            self.reverse(text)
            if direction == "xenari_to_english"
            else self.speak(text, tense=tense, evidential=evidential)
        )
        packet: Dict[str, object] = {
            "schema": "xenari.llm_context.v1",
            "source": text,
            "direction": direction,
            "architecture": {
                "llm_role": "semantic translator/interpreter",
                "tool_role": "canon linter and constraint checker",
                "tool_is_semantic_authority": False,
                "on_disagreement": "surface the disagreement instead of trusting the tool blindly",
            },
            "deterministic_tool_output": deterministic,
            "candidate_contract": {
                "candidate_translation": "string",
                "literal_gloss": "string",
                "roots_used": [{"root": "xenari-root", "meaning": "DB meaning"}],
                "grammar_frame": "brief parse of clauses/particles",
                "confidence": "low|medium|high",
                "unsupported_bits": ["anything guessed, missing, or not canon"],
            },
            "canon_constraints": {
                "default_order": "OSV: ra OBJECT ka SUBJECT ta VERB TENSE EVIDENTIAL",
                "do_not_invent_roots": True,
                "pronouns_carry_animacy": True,
                "base": 6,
                "digit_roots": dict(self._base6_digit_roots()),
                "particle_roots": sorted(self._llm_particle_roots()),
                "reference": "docs/reference/LLM_REFERENCE.md",
            },
        }
        if direction == "xenari_to_english":
            packet["token_hints"] = self._llm_xenari_hints(text)
            packet["candidate_lint"] = self.lint_xenari_candidate(text)
        else:
            packet["lexicon_hints"] = self._llm_english_hints(text)
        return packet
