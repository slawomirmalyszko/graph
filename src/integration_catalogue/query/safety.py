"""Defence-in-depth validation for model-generated Cypher."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MAX_RESULT_LIMIT = 500

_WRITE_OR_UNSUPPORTED = re.compile(
    r"\b(?:CREATE|INSERT|MERGE|DELETE|DETACH|SET|REMOVE|DROP|ALTER|RENAME|GRANT|DENY|"
    r"REVOKE|START|STOP|TERMINATE|FOREACH|CALL|LOAD\s+CSV|USE)\b",
    re.IGNORECASE,
)
_ALLOWED_START = re.compile(r"^\s*(?:MATCH|OPTIONAL\s+MATCH|WITH|UNWIND|RETURN)\b", re.IGNORECASE)
_PARAMETER = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
_LIMIT_PARAMETER = re.compile(r"\bLIMIT\s+\$([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
_COUNT_ONLY = re.compile(
    r"\bRETURN\s+count\s*\([^)]*\)\s+(?:AS\s+[A-Za-z_][A-Za-z0-9_]*\s*)?$",
    re.IGNORECASE,
)


class CypherSafetyError(ValueError):
    """Raised when generated Cypher fails the read-only safety policy."""


@dataclass(frozen=True)
class ValidatedQuery:
    """A candidate query that passed application-level safety validation."""

    cypher: str
    parameters: dict[str, Any]


def _mask_literals_and_comments(cypher: str) -> tuple[str, bool]:
    """Mask content that must not participate in keyword checks."""
    output = list(cypher)
    index = 0
    has_string_literal = False
    length = len(cypher)

    while index < length:
        character = cypher[index]
        next_character = cypher[index + 1] if index + 1 < length else ""

        if character == "/" and next_character == "/":
            end = cypher.find("\n", index + 2)
            end = length if end == -1 else end
            output[index:end] = " " * (end - index)
            index = end
            continue
        if character == "/" and next_character == "*":
            end = cypher.find("*/", index + 2)
            if end == -1:
                raise CypherSafetyError("Cypher contains an unterminated block comment.")
            end += 2
            output[index:end] = " " * (end - index)
            index = end
            continue
        if character in {"'", '"', "`"}:
            quote = character
            has_string_literal |= quote != "`"
            end = index + 1
            while end < length:
                if cypher[end] == quote:
                    if end + 1 < length and cypher[end + 1] == quote:
                        end += 2
                        continue
                    end += 1
                    break
                if cypher[end] == "\\" and end + 1 < length:
                    end += 2
                else:
                    end += 1
            else:
                raise CypherSafetyError("Cypher contains an unterminated quoted value.")
            output[index:end] = " " * (end - index)
            index = end
            continue
        index += 1

    return "".join(output), has_string_literal


def _is_parameter_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    return isinstance(value, list) and all(
        item is None or isinstance(item, (str, int, float, bool)) for item in value
    )


def validate_read_only_cypher(cypher: str, parameters: dict[str, Any]) -> ValidatedQuery:
    """Validate one bounded, parameterized, read-only Cypher statement."""
    candidate = cypher.strip()
    if not candidate:
        raise CypherSafetyError("Cypher cannot be empty.")
    if not isinstance(parameters, dict):
        raise CypherSafetyError("Cypher parameters must be an object.")

    visible, has_string_literal = _mask_literals_and_comments(candidate)
    if ";" in visible:
        raise CypherSafetyError("Semicolons and multiple Cypher statements are not allowed.")
    if has_string_literal:
        raise CypherSafetyError("Literal strings are not allowed; use Cypher parameters.")
    forbidden = _WRITE_OR_UNSUPPORTED.search(visible)
    if forbidden:
        raise CypherSafetyError(f"Unsupported Cypher clause: {forbidden.group(0).upper()}.")
    if not _ALLOWED_START.match(visible):
        raise CypherSafetyError("Cypher must begin with a read query clause.")

    referenced = set(_PARAMETER.findall(visible))
    supplied = set(parameters)
    if referenced != supplied:
        missing = sorted(referenced - supplied)
        unused = sorted(supplied - referenced)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unused:
            details.append("unused: " + ", ".join(unused))
        raise CypherSafetyError("Cypher parameter mismatch (" + "; ".join(details) + ").")

    invalid_parameters = sorted(
        name for name, value in parameters.items() if not _is_parameter_value(value)
    )
    if invalid_parameters:
        raise CypherSafetyError(
            "Unsupported parameter values: " + ", ".join(invalid_parameters) + "."
        )

    limit_match = _LIMIT_PARAMETER.search(visible)
    if limit_match:
        limit_name = limit_match.group(1)
        limit = parameters.get(limit_name)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_RESULT_LIMIT
        ):
            raise CypherSafetyError(
                f"{limit_name} must be an integer from 1 to {MAX_RESULT_LIMIT}."
            )
    elif not _COUNT_ONLY.search(visible):
        raise CypherSafetyError("Queries returning rows must use a parameterized LIMIT.")

    return ValidatedQuery(cypher=candidate, parameters=dict(parameters))
