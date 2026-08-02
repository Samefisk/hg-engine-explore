"""Closed operator eligibility for serialized OWBD v40 modifier fields."""

SET = 1
ADD = 2
AT_LEAST = 3
AT_MOST = 4
ADD_AT_LEAST = 5
ADD_AT_MOST = 6

ALL_OPERATORS = frozenset(range(SET, ADD_AT_MOST + 1))
SIGNED_DELTA_OPERATORS = frozenset((ADD, ADD_AT_LEAST, ADD_AT_MOST))

NUMERIC_FIELDS = {
    4: frozenset((3, 4, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 24, 25)),
    5: frozenset((3, 4, 6, 7)),
    7: frozenset((3, 4, 5)),
    9: frozenset((1,)),
}

# Closed scalar domains shared by authored-body validation, serialized
# modifier validation, and the independent executor. Tuples are inclusive
# numeric bounds; frozensets are exact enum/bit-domain memberships.
SCALAR_DOMAINS = {
    4: {
        1: frozenset(range(8)),
        2: frozenset((*range(7), 8, 9)),
        3: (1, 4), 4: (0, 64), 5: frozenset(range(3)),
        6: frozenset((*range(6), 15)), 7: frozenset((*range(6), 15)),
        8: frozenset((0, 1)), 9: (0, 12), 10: (0, 12),
        11: (0, 255), 12: (0, 64), 13: (0, 15), 14: (0, 64),
        15: (0, 255), 16: (0, 32), 17: (0, 255), 18: (0, 32),
        19: (0, 4), 20: (0, 8), 21: frozenset((0, 1)),
        22: frozenset((0, 1)), 23: frozenset(range(3)), 24: (0, 32),
        25: (0, 255), 26: frozenset(range(3)), 27: (0, 15),
    },
    5: {
        1: frozenset(range(3)), 2: frozenset((*range(11), 255)),
        3: (0, 64), 4: (0, 64), 5: frozenset(range(6)),
        6: (0, 100), 7: (0, 64),
    },
    7: {
        1: frozenset(range(4)), 2: frozenset(range(17)),
        3: (1, 8), 4: (1, 8), 5: (0, 64),
    },
    9: {1: (0, 10)},
}

BEHAVIOR_KIND_MEMBERS = frozenset((*range(9), 10, 11))


def operator_allowed(kind: int, field: int, operator: int) -> bool:
    if operator not in ALL_OPERATORS:
        return False
    if kind == 11:
        return field == 1 and operator in (SET, ADD)
    return operator in ALL_OPERATORS if field in NUMERIC_FIELDS.get(kind, ()) else operator == SET


def scalar_value_valid(kind: int, field: int, value: int) -> bool:
    domain = SCALAR_DOMAINS.get(kind, {}).get(field)
    if domain is None:
        return False
    if isinstance(domain, tuple):
        return domain[0] <= value <= domain[1]
    return value in domain


def numeric_bounds(kind: int, field: int) -> tuple[int, int]:
    domain = SCALAR_DOMAINS.get(kind, {}).get(field)
    if field not in NUMERIC_FIELDS.get(kind, ()) or not isinstance(domain, tuple):
        raise ValueError("field has no numeric scalar bounds")
    return domain


def state_body_values_valid(values: bytes) -> bool:
    return (len(values) == 28 and values[0] in BEHAVIOR_KIND_MEMBERS
            and all(scalar_value_valid(4, field, values[field]) for field in range(1, 28))
            and values[9] <= values[10])
