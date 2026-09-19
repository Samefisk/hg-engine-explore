import argparse
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tools.overworld.melonds_backend import MelonDS

# Settings
SHOW_VIDEO_OUTPUT = False
TEST_START_INDEX = 0
IDLE_TIMEOUT_SECONDS = 1 * 60  # 1 minute

g_EmulatorCommunicationSendHoleAddress = 0x02FFF81C
TEST_CASE_PASS = -1
TEST_CASE_FAIL = -2
TEST_CASE_KNOWN_FAILING = -3

test_case_names: list[str] = list()


# https://stackoverflow.com/questions/287871/how-do-i-print-colored-text-to-the-terminal
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


has_finished_testing_flag = False
current_test_case = TEST_START_INDEX
return_value = 0
last_activity_time = time.monotonic()

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--video", action="store_true")

emu = None
emu_memory = None


def get_test_names() -> list[str]:
    build_folder = pathlib.Path(os.path.join(os.getcwd(), "build", "battle_tests"))
    test_case_names: list[str] = list()
    with open(os.path.join(build_folder, "BattleTests.c"), "r") as file:
        for line in file:
            match_group = re.match(r'#include "../../data/(.+)"', line)
            if match_group:
                test_file_path = pathlib.Path(
                    os.path.join(os.getcwd(), "data", match_group.group(1))
                )
                with open(test_file_path, "r") as test_file:
                    test_case_match_group = re.match(
                        r"// Test: (.+)", test_file.readline().strip()
                    )
                    if test_case_match_group:
                        test_case_names.append(test_case_match_group.group(1))

    return test_case_names


def read_communication_hole_value():
    address = g_EmulatorCommunicationSendHoleAddress
    return emu_memory.signed[address:address:4]


def has_finished_testing() -> bool:
    return current_test_case == NUMBER_OF_TESTS_TO_RUN


def callback_function_when_game_put_thing_into_communication_hole(
    address, size
) -> None:
    global \
        current_test_case, \
        has_finished_testing_flag, \
        return_value, \
        last_activity_time

    last_activity_time = time.monotonic()

    value = read_communication_hole_value()
    if value not in (TEST_CASE_FAIL, TEST_CASE_PASS, TEST_CASE_KNOWN_FAILING):
        return
    if current_test_case >= NUMBER_OF_TESTS_TO_RUN:
        raise RuntimeError("battle tester reported an extra result")

    if value == TEST_CASE_FAIL:
        print(
            f"{bcolors.FAIL}[Fail] {test_case_names[current_test_case]}{bcolors.ENDC}",
            flush=True,
        )
        return_value += 1
    elif value == TEST_CASE_PASS:
        print(
            f"{bcolors.OKGREEN}[Pass] {test_case_names[current_test_case]}{bcolors.ENDC}",
            flush=True,
        )
    elif value == TEST_CASE_KNOWN_FAILING:
        print(
            f"{bcolors.WARNING}[Known Failing] {test_case_names[current_test_case]}{bcolors.ENDC}",
            flush=True,
        )

    current_test_case += 1


def read_total_tests_from_header() -> int:
    header_path = "include/constants/generated/test_battle.h"

    with open(header_path, "r", encoding="utf-8") as f:
        text = f.read()

    m = re.search(r"#define\s+TEST_BATTLE_TOTAL_TESTS\s+(\d+)", text)
    if not m:
        raise RuntimeError(f"Could not find TEST_BATTLE_TOTAL_TESTS in {header_path}")
    return int(m.group(1))


NUMBER_OF_TESTS_TO_RUN = 0


class BattleWindow:
    """Optional human view. Created only for explicit --video."""
    def __init__(self):
        import tkinter
        from PIL import ImageTk
        self.ImageTk = ImageTk
        self.root = tkinter.Tk()
        self.root.title("melonDS battle tests")
        self.label = tkinter.Label(self.root)
        self.label.pack()
        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def draw(self):
        if self.closed:
            raise RuntimeError("battle test window closed")
        self.image = self.ImageTk.PhotoImage(emu.screenshot())
        self.label.configure(image=self.image)
        self.root.update()

    def close(self):
        if not self.closed:
            self.closed = True
            self.root.destroy()


def main():
    global emu, emu_memory, test_case_names, NUMBER_OF_TESTS_TO_RUN
    global current_test_case, return_value, last_activity_time
    args = parser.parse_args()
    NUMBER_OF_TESTS_TO_RUN = read_total_tests_from_header()
    test_case_names = get_test_names()
    if NUMBER_OF_TESTS_TO_RUN <= 0 or len(test_case_names) != NUMBER_OF_TESTS_TO_RUN:
        raise RuntimeError("battle test names and generated count differ or are empty")
    current_test_case, return_value = TEST_START_INDEX, 0
    emu = MelonDS()
    emu_memory = emu.memory
    window = None
    try:
        emu.volume_set(0)
        emu_memory.register_write(
            g_EmulatorCommunicationSendHoleAddress,
            callback_function_when_game_put_thing_into_communication_hole,
            size=4,
        )
        emu.open("test.nds")
        emu.backup.import_file("test.sav")
        if args.video:
            window = BattleWindow()
        last_activity_time = time.monotonic()
        # This is the in-ROM battle harness, not an overworld test driver.
        while not has_finished_testing():
            if (time.monotonic() - last_activity_time) > IDLE_TIMEOUT_SECONDS:
                print(f"{bcolors.FAIL}[Timeout] No activity for {IDLE_TIMEOUT_SECONDS // 60} minutes. Aborting.{bcolors.ENDC}", flush=True)
                return 1
            if window is not None:
                window.draw()
            emu.cycle(False)
        print("Tests complete!\n", flush=True)
        return return_value
    finally:
        if window is not None:
            window.close()
        emu.destroy()


if __name__ == "__main__":
    sys.exit(main())
