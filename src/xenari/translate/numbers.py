import re
from typing import List


class NumberTranslationMixin:
    def _base6_digit_roots(self):
        return {
            0: "nul",
            1: "ca",
            2: "vriq",
            3: "prit",
            4: "qang",
            5: "cum",
        }

    def _base6_number_words(self):
        return {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

    def _math_operator_roots(self):
        return {
            "plus": "plomt",
            "add": "plomt",
            "added to": "plomt",
            "addition": "plomt",
            "minus": "krut",
            "subtract": "krut",
            "subtracted by": "krut",
            "subtraction": "krut",
            "times": "vrot",
            "multiply": "vrot",
            "multiplied by": "vrot",
            "grouped by": "vrot",
            "divided by": "flopq",
            "divide by": "flopq",
            "divide": "flopq",
            "split by": "flopq",
            "equals": "zlem",
            "equal to": "zlem",
            "same as": "zlem",
            "greater than": "grak",
            "more than": "grak",
            "less than": "vlox",
            "fewer than": "vlox",
            "fraction": "nok",
            "ratio": "nok",
            "over": "nok",
            "+": "plomt",
            "-": "krut",
            "*": "vrot",
            "x": "vrot",
            "×": "vrot",
            "/": "flopq",
            "=": "zlem",
            ">": "grak",
            "<": "vlox",
        }

    def _english_math_operator(self, root: str) -> str:
        return {
            "plomt": "plus",
            "krut": "minus",
            "vrot": "times",
            "flopq": "divided by",
            "zlem": "equals",
            "grak": "greater than",
            "vlox": "less than",
            "nok": "fraction",
        }[root]

    def _parse_english_number_value(self, text: str):
        clean = re.sub(r"[\s_-]+", " ", text.lower().strip())
        clean = clean.strip(".,!?;:")
        if re.fullmatch(r"\d+", clean):
            return int(clean)
        return self._base6_number_words().get(clean)

    def _base6_number_parts(self, value: int):
        if value < 0:
            return None
        digit_roots = self._base6_digit_roots()
        if value == 0:
            return [digit_roots[0]]
        parts = []
        highest_place = 0
        probe = value
        while probe >= 6:
            highest_place += 1
            probe //= 6
        for place in range(highest_place, -1, -1):
            digit = (value // (6 ** place)) % 6
            if digit == 0:
                continue
            parts.append(digit_roots[digit])
            parts.extend(["xang"] * place)
        return parts

    def _number_value_from_xenari_tokens(self, tokens: List[str]):
        if not tokens:
            return None
        root_digits = {root: digit for digit, root in self._base6_digit_roots().items()}
        if tokens == [self._base6_digit_roots()[0]]:
            return 0
        total = 0
        i = 0
        saw_group = False
        seen_places = set()
        while i < len(tokens):
            token = tokens[i]
            if token not in root_digits:
                return None
            digit = root_digits[token]
            i += 1
            place = 0
            while i < len(tokens) and tokens[i] == "xang":
                place += 1
                i += 1
            if digit == 0 and (place or len(tokens) > 1):
                return None
            if place in seen_places:
                return None
            seen_places.add(place)
            total += digit * (6 ** place)
            saw_group = True
        return total if saw_group else None

    def _speak_number_or_math(self, english: str):
        raw = english.strip()
        if not raw:
            return None
        clean = self._phrase_key(raw)
        operator_roots = self._math_operator_roots()

        symbol_match = re.fullmatch(r"(.+?)\s*([+\-*/=<>×])\s*(.+)", raw.strip())
        if symbol_match:
            left, operator, right = symbol_match.groups()
            left_value = self._parse_english_number_value(left)
            right_value = self._parse_english_number_value(right)
            if left_value is not None and right_value is not None:
                return " ".join([
                    *self._base6_number_parts(left_value),
                    operator_roots[operator],
                    *self._base6_number_parts(right_value),
                ])

        for operator in sorted(operator_roots, key=len, reverse=True):
            if len(operator) == 1 and operator not in {"x"}:
                continue
            pattern = rf"(.+?)\s+{re.escape(operator)}\s+(.+)"
            match = re.fullmatch(pattern, clean)
            if not match:
                continue
            left, right = match.groups()
            left_value = self._parse_english_number_value(left)
            right_value = self._parse_english_number_value(right)
            if left_value is None or right_value is None:
                continue
            return " ".join([
                *self._base6_number_parts(left_value),
                operator_roots[operator],
                *self._base6_number_parts(right_value),
            ])

        value = self._parse_english_number_value(clean)
        if value is not None:
            return " ".join(self._base6_number_parts(value))
        return None

    def _reverse_number_or_math(self, xenari: str):
        tokens = re.findall(r"[a-z']+", xenari.lower())
        if not tokens:
            return None
        operator_roots = {root for root in self._math_operator_roots().values()}
        if any(token in operator_roots for token in tokens):
            for index, token in enumerate(tokens):
                if token not in operator_roots:
                    continue
                left = self._number_value_from_xenari_tokens(tokens[:index])
                right = self._number_value_from_xenari_tokens(tokens[index + 1:])
                if left is None or right is None:
                    return None
                return f"{left} {self._english_math_operator(token)} {right}"
            return None
        value = self._number_value_from_xenari_tokens(tokens)
        return str(value) if value is not None else None
