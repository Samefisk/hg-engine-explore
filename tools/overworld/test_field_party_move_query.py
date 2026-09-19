"""Source-level control-flow check of the small native Thumb replacement.

This walks the production assembly with mocked native calls. It checks query
answers, checksum-before-lock, lock ownership and ABI restoration, not game
cadence. The ROM build separately enforces assembly/slot bounds; live CPU work
data and user play are still needed for the stutter report.
"""
from copy import deepcopy
from pathlib import Path
import random
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "armips/asm/field_party_move_query.s"


def run_query(party, wanted):
    code, labels = [], {}
    for raw in SOURCE.read_text().splitlines():
        line = raw.split("//")[0].strip()
        if not line or line.startswith("."):
            continue
        if line.endswith(":"):
            labels[line[:-1]] = len(code)
        else:
            code.append(line)
    regs = {f"r{i}": 0xAA00 + i for i in range(8)}
    saved = dict(regs)
    regs.update(r0=0x9000, r1=wanted, sp=0x8000, lr=-1)
    stack, checked, calls = {}, set(), []
    mon_ptrs = {0x1000 + i * 256: mon for i, mon in enumerate(party)}
    pc, compare = 0, 0

    def value(operand):
        return int(operand[1:], 0) if operand.startswith("#") else regs[operand]

    for _ in range(2000):
        line = code[pc]
        pc += 1
        op, args = line.split(" ", 1)
        args = args.strip()
        if op in ("push", "pop"):
            names = ["r3", "r4", "r5", "r6", "r7", "lr" if op == "push" else "pc"]
            if op == "push":
                regs["sp"] -= 24
                for i, name in enumerate(names):
                    stack[regs["sp"] + 4 * i] = regs[name]
            else:
                for i, name in enumerate(names):
                    regs[name] = stack[regs["sp"] + 4 * i]
                regs["sp"] += 24
                assert regs["pc"] == -1 and regs["sp"] == 0x8000
                assert all(regs[name] == saved[name] for name in ("r4", "r5", "r6", "r7"))
                return regs["r0"], calls
        elif op in ("str", "ldr"):
            match = re.fullmatch(r"(r\d), \[sp, #(\d+)\]", args)
            assert match, line
            name, offset = match.groups()
            address = regs["sp"] + int(offset)
            if op == "str":
                stack[address] = regs[name]
            else:
                regs[name] = stack[address]
        elif op in ("mov", "add", "sub", "cmp"):
            left, right = args.split(", ")
            operand = value(right)
            if op == "mov":
                regs[left] = operand
            elif op == "cmp":
                compare = regs[left] - operand
            else:
                regs[left] += operand if op == "add" else -operand
        elif op == "bl":
            address = int(args, 0)
            mon = mon_ptrs.get(regs["r0"])
            if address == 0x02074640:
                answer = len(party)
            elif address == 0x02074644:
                assert regs["r0"] == 0x9000
                answer = 0x1000 + regs["r1"] * 256
            elif address == 0x0206E540:
                field = regs["r1"]
                calls.append((regs["r0"], "read", field, mon["locked"]))
                assert regs["r2"] == 0
                if field == 76:
                    checked.add(regs["r0"])
                    answer = mon["egg"] or mon["bad"]
                else:
                    assert mon["locked"] and regs["r0"] in checked
                    answer = mon["moves"][field - 54]
            elif address == 0x0206DD40:
                assert regs["r0"] in checked and not (mon["egg"] or mon["bad"])
                answer = not mon["locked"]
                calls.append((regs["r0"], "lock", answer))
                mon["locked"] = True
            elif address == 0x0206DD8C:
                assert mon["locked"]
                calls.append((regs["r0"], "release", regs["r1"]))
                if regs["r1"]:
                    mon["locked"] = False
                answer = 0
            else:
                raise AssertionError(line)
            # Native calls may overwrite every caller-saved argument register.
            regs.update(r0=answer, r1=-19, r2=-20, r3=-21)
        elif op in ("b", "beq", "bne", "blt"):
            if op == "b" or (op == "beq" and compare == 0) or (op == "bne" and compare != 0) or (op == "blt" and compare < 0):
                pc = labels[args]
        else:
            raise AssertionError(line)
    raise AssertionError("query did not terminate")


class FieldPartyMoveQueryTests(unittest.TestCase):
    def test_stock_results_and_all_lock_exits(self):
        rng = random.Random(204542)
        for count in range(7):
            for _ in range(100):
                party = [dict(moves=[rng.randrange(5) for _ in range(4)],
                              egg=rng.randrange(5) == 0, bad=rng.randrange(7) == 0,
                              locked=bool(rng.randrange(2))) for _ in range(count)]
                original = deepcopy(party)
                wanted = rng.randrange(6)
                expected = next((i for i, mon in enumerate(party)
                                 if not (mon["egg"] or mon["bad"]) and wanted in mon["moves"]), 255)
                answer, calls = run_query(party, wanted)
                self.assertEqual(answer, expected)
                self.assertEqual(party, original)
                self.assertEqual([row[2] for row in calls if row[1] == "lock"],
                                 [row[2] for row in calls if row[1] == "release"])

    def test_worst_case_four_move_reads_share_one_lock(self):
        party = [dict(moves=[1, 2, 3, 4], egg=False, bad=False, locked=False) for _ in range(6)]
        answer, calls = run_query(party, 127)
        self.assertEqual(answer, 255)
        self.assertEqual(sum(row[1] == "read" and not row[3] for row in calls), 6)
        self.assertEqual(sum(row[1] == "lock" for row in calls), 6)


if __name__ == "__main__":
    unittest.main()
