#!/usr/bin/env python3
import argparse
import importlib.util
import json
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = "documentation/verification_screenshots/overworld_shadow_harness"
LEDGE_SPAWN_TARGET_X_MIN = 70
LEDGE_SPAWN_TARGET_X_MAX = 145
LEDGE_SPAWN_TARGET_Y_MIN = 70
LEDGE_SPAWN_TARGET_Y_MAX = 115
LEDGE_SPAWN_TRACK_CENTER_Y_MAX = 125
LEDGE_SPAWN_MIN_SEED_PINK_PIXELS = 30
LEDGE_SPAWN_MIN_NEW_PINK_PIXELS = 8
LEDGE_SPAWN_DIFF_PIXEL_THRESHOLD = 32
AUTHORITATIVE_SHADOW_START_FRAME = 64
AUTHORITATIVE_SHADOW_END_FRAME = 179


def load_headless_module():
    module_path = REPO_ROOT / "scripts/headless-overworld-test.py"
    spec = importlib.util.spec_from_file_location("headless_overworld_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


headless = load_headless_module()

from PIL import Image, ImageDraw


def repo_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def parse_roi(value: str) -> list[int]:
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x_min,y_min,x_max,y_max")
    try:
        roi = [int(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI values must be integers") from exc
    x_min, y_min, x_max, y_max = roi
    if x_min > x_max or y_min > y_max:
        raise argparse.ArgumentTypeError("ROI minimums must be <= maximums")
    if x_min < 0 or x_max > 255 or y_min < 0 or y_max > 191:
        raise argparse.ArgumentTypeError("ROI must be inside the top screen")
    return roi


def parse_frame_count(value: str, field: str) -> int:
    try:
        frames = int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if frames < 0:
        raise ValueError(f"{field} must be >= 0")
    return frames


def normalize_key_name(value: str) -> str:
    key = value.upper()
    headless.key_constant(key)
    return key


def sanitize_stage_name(value: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in value
    ).strip("_")
    if not safe:
        raise ValueError("capture stage name must contain at least one safe character")
    return safe


def parse_action_spec(spec: str) -> dict[str, Any]:
    parts = spec.split(":")
    action = parts[0]
    if action == "wait":
        if len(parts) != 2:
            raise ValueError("wait action must be wait:frames")
        return {"action": "wait", "frames": parse_frame_count(parts[1], "wait frames")}

    if action == "hold":
        if len(parts) not in (3, 4):
            raise ValueError("hold action must be hold:KEY:frames[:release_frames]")
        parsed = {
            "action": "hold",
            "key": normalize_key_name(parts[1]),
            "frames": parse_frame_count(parts[2], "hold frames"),
        }
        if len(parts) == 4:
            parsed["release_frames"] = parse_frame_count(parts[3], "release frames")
        return parsed

    if action == "capture":
        if len(parts) != 2:
            raise ValueError("capture action must be capture:stage")
        return {"action": "capture", "stage": sanitize_stage_name(parts[1])}

    if action == "capture-hold":
        if len(parts) not in (4, 5):
            raise ValueError(
                "capture-hold action must be "
                "capture-hold:KEY:hold_frames:capture_frames[:release_frames]"
            )
        parsed = {
            "action": "capture-hold",
            "key": normalize_key_name(parts[1]),
            "hold_frames": parse_frame_count(parts[2], "capture-hold frames"),
            "capture_frames": parse_frame_count(parts[3], "capture frames"),
        }
        if len(parts) == 5:
            parsed["release_frames"] = parse_frame_count(parts[4], "release frames")
        return parsed

    raise ValueError(f"unknown action kind: {action}")


def parse_action_specs(specs: list[str]) -> list[dict[str, Any]]:
    actions = [parse_action_spec(spec) for spec in specs]
    capture_hold_indexes = [
        index for index, action in enumerate(actions) if action["action"] == "capture-hold"
    ]
    capture_hold_count = len(capture_hold_indexes)
    if capture_hold_count != 1:
        raise ValueError("--scenario custom requires exactly one capture-hold action")
    if capture_hold_indexes[0] != len(actions) - 1:
        raise ValueError("capture-hold must be the final custom action")
    return actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Boot test.nds/test.dsv, step LEFT to spawn Igglybuff, step RIGHT to "
            "trigger the grass-to-land hop, and capture per-frame shadow evidence."
        )
    )
    parser.add_argument("--rom", default="test.nds", help="ROM to boot. Default: test.nds")
    parser.add_argument("--dsv", help="DeSmuME .dsv to load. Default: ./test.dsv search order.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prefix", default="igglybuff_grass_to_land")
    parser.add_argument(
        "--scenario",
        choices=("ledge-repro", "custom"),
        default="ledge-repro",
        help="Use the built-in ledge repro, or run a custom --action plan.",
    )
    parser.add_argument(
        "--action",
        action="append",
        default=[],
        help=(
            "Custom scenario step. Supported forms: wait:frames, "
            "hold:KEY:frames[:release_frames], capture:stage, and "
            "capture-hold:KEY:hold_frames:capture_frames[:release_frames]."
        ),
    )
    parser.add_argument("--boot-frames", type=int, default=420)
    parser.add_argument("--ready-a-taps", type=int, default=10)
    parser.add_argument("--tap-hold-frames", type=int, default=24)
    parser.add_argument("--tap-gap-frames", type=int, default=36)
    parser.add_argument("--load-frames", type=int, default=60)
    parser.add_argument("--pre-left-wait", type=int, default=0)
    parser.add_argument("--left-hold", type=int, default=20)
    parser.add_argument("--left-release", type=int, default=30)
    parser.add_argument("--after-left-wait", type=int, default=0)
    parser.add_argument("--right-hold", type=int, default=20)
    parser.add_argument("--right-release", type=int, default=30)
    parser.add_argument("--capture-frames", type=int, default=360)
    parser.add_argument("--capture-every", type=int, default=1)
    parser.add_argument("--contact-every", type=int, default=4)
    parser.add_argument("--contact-pre-roll", type=int, default=0)
    parser.add_argument(
        "--contact-delay-after-hop",
        type=int,
        default=0,
        help="Start the contact sheet this many frames after the detected hop marker.",
    )
    parser.add_argument(
        "--contact-start-frame",
        type=int,
        help="Force the contact sheet to start at this capture frame.",
    )
    parser.add_argument("--contact-columns", type=int, default=4)
    parser.add_argument("--shadow-dark-threshold", type=int, default=10)
    parser.add_argument("--shadow-delta-threshold", type=int, default=35)
    parser.add_argument("--relative-shadow-threshold", type=int, default=6)
    parser.add_argument(
        "--shadow-check-start-frame",
        type=int,
        default=AUTHORITATIVE_SHADOW_START_FRAME,
    )
    parser.add_argument(
        "--shadow-check-end-frame",
        type=int,
        default=AUTHORITATIVE_SHADOW_END_FRAME,
    )
    parser.add_argument("--shadow-check-min-present-percent", type=int, default=80)
    parser.add_argument("--shadow-check-min-tracked-percent", type=int, default=90)
    parser.add_argument("--shadow-check-max-missing-run", type=int, default=3)
    parser.add_argument("--movement-check-min-tracked-percent", type=int, default=90)
    parser.add_argument("--movement-check-min-origin-left-delta", type=int, default=60)
    parser.add_argument("--movement-check-min-window-left-delta", type=int, default=24)
    parser.add_argument("--movement-check-min-distinct-center-x", type=int, default=8)
    parser.add_argument(
        "--disable-movement-pass-check",
        action="store_true",
        help="Capture evidence without requiring the tracked Igglybuff to keep moving left.",
    )
    parser.add_argument("--shadow-core-delta-threshold", type=int, default=35)
    parser.add_argument("--shadow-core-min-dark-pixels", type=int, default=10)
    parser.add_argument("--shadow-core-min-delta-mean", type=int, default=10)
    parser.add_argument("--shadow-core-min-local-contrast", type=int, default=8)
    parser.add_argument(
        "--disable-shadow-pass-check",
        action="store_true",
        help="Capture evidence without evaluating the f064-f179 shadow pass rule.",
    )
    parser.add_argument(
        "--no-fail-on-shadow-pass",
        action="store_true",
        help="Report the shadow pass result but keep process exit status 0.",
    )
    parser.add_argument(
        "--no-fail-on-movement-pass",
        action="store_true",
        help="Report the movement pass result but keep process exit status 0.",
    )
    parser.add_argument("--actual-hop-min-x-delta", type=int, default=16)
    parser.add_argument("--actual-hop-min-y-lift", type=int, default=4)
    parser.add_argument("--actual-hop-min-pink-pixels", type=int, default=75)
    parser.add_argument("--actual-hop-min-body-height", type=int, default=13)
    parser.add_argument(
        "--target-igglybuff",
        choices=("ledge-spawn", "left", "right", "largest", "roi"),
        default="ledge-spawn",
        help="Which detected Igglybuff body to track when more than one is visible.",
    )
    parser.add_argument(
        "--target-stage",
        help=(
            "Custom scenario screenshot stage used for initial target selection. "
            "Default: latest captured stage before capture-hold, or ready."
        ),
    )
    parser.add_argument(
        "--target-roi",
        type=parse_roi,
        help="Custom target ROI as x_min,y_min,x_max,y_max on the top screen.",
    )
    parser.add_argument(
        "--target-max-center-y",
        type=int,
        help="Optional maximum component center Y for custom ROI continuity tracking.",
    )
    parser.add_argument(
        "--target-roi-min-pink-pixels",
        type=int,
        default=30,
        help="Minimum pink pixels for a custom ROI seed candidate.",
    )
    parser.add_argument(
        "--show-emulator-log",
        action="store_true",
        help="Let native DeSmuME stdout/stderr logs pass through.",
    )
    parser.add_argument(
        "--memory-read",
        action="append",
        default=[],
        help="Read memory after the repro/capture window as label:type:address.",
    )
    parser.add_argument(
        "--memory-sample-every",
        type=int,
        default=0,
        help=(
            "When positive, also sample all --memory-read addresses every N capture "
            "frames during the capture window."
        ),
    )
    parser.add_argument(
        "--s83-primary-probe-base",
        type=headless.parse_int,
        default=0,
        help=(
            "Optional base address for the S83 primary draw diagnostics. "
            "When set, per-frame memory samples include decoded packed "
            "post-stock object/render/sprite state from that probe."
        ),
    )
    return parser.parse_args()


def capture(emu: Any, path: Path) -> Image.Image:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = emu.screenshot().convert("RGB")
    image.save(path)
    return image


def top_screen(image: Image.Image) -> Image.Image:
    return image.crop((0, 0, 256, 192))


def is_igglybuff_pink(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    pink_lit = (
        r >= 96
        and b >= 88
        and g <= 220
        and r > g - 18
        and b > g - 32
        and max(r, b) > g + 6
    )
    warm_lit = (
        r >= 112
        and g >= 48
        and b >= 56
        and r >= g + 12
        and r >= b + 8
        and max(r, g, b) - min(r, g, b) >= 32
    )
    return pink_lit or warm_lit


def find_pink_components(image: Image.Image) -> list[dict[str, Any]]:
    top = top_screen(image)
    width, height = top.size
    pixels = top.load()
    mask = bytearray(width * height)
    visited = bytearray(width * height)
    components = []

    for y in range(height):
        row = y * width
        for x in range(width):
            if is_igglybuff_pink(pixels[x, y]):
                mask[row + x] = 1

    for y in range(height):
        for x in range(width):
            start_index = y * width + x
            if not mask[start_index] or visited[start_index]:
                continue

            visited[start_index] = 1
            queue = deque([(x, y)])
            count = 0
            min_x = max_x = x
            min_y = max_y = y

            while queue:
                cx, cy = queue.popleft()
                count += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy

                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    index = ny * width + nx
                    if mask[index] and not visited[index]:
                        visited[index] = 1
                        queue.append((nx, ny))

            component_width = max_x - min_x + 1
            component_height = max_y - min_y + 1
            if count >= 4 and component_width <= 32 and component_height <= 32:
                components.append(
                    {
                        "pixel_count": count,
                        "bbox": [min_x, min_y, max_x + 1, max_y + 1],
                    }
                )

    components.sort(key=lambda item: item["pixel_count"], reverse=True)
    return components


def component_center_x(component: dict[str, Any]) -> int:
    x0, _y0, x1, _y1 = component["bbox"]
    return (x0 + x1) // 2


def component_center(component: dict[str, Any]) -> tuple[int, int]:
    x0, y0, x1, y1 = component["bbox"]
    return ((x0 + x1) // 2, (y0 + y1) // 2)


def target_roi_summary(roi: list[int] | None = None) -> dict[str, int]:
    if roi is None:
        roi = [
            LEDGE_SPAWN_TARGET_X_MIN,
            LEDGE_SPAWN_TARGET_Y_MIN,
            LEDGE_SPAWN_TARGET_X_MAX,
            LEDGE_SPAWN_TARGET_Y_MAX,
        ]
    return {
        "x_min": roi[0],
        "y_min": roi[1],
        "x_max": roi[2],
        "y_max": roi[3],
    }


def target_tracking_band_summary(max_center_y: int | None = None) -> dict[str, int | None]:
    if max_center_y is None:
        max_center_y = LEDGE_SPAWN_TRACK_CENTER_Y_MAX
    return {"max_center_y": max_center_y}


def full_body_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sprite_components = [
        component
        for component in components
        if component["pixel_count"] >= 30
    ]
    if sprite_components:
        return sprite_components
    return components


def component_distance_squared(
    first: dict[str, Any],
    second: dict[str, Any],
) -> int:
    first_x, first_y = component_center(first)
    second_x, second_y = component_center(second)
    dx = first_x - second_x
    dy = first_y - second_y
    return dx * dx + dy * dy


def is_ledge_spawn_initial_component(component: dict[str, Any]) -> bool:
    center_x, center_y = component_center(component)
    return (
        LEDGE_SPAWN_TARGET_X_MIN <= center_x <= LEDGE_SPAWN_TARGET_X_MAX
        and LEDGE_SPAWN_TARGET_Y_MIN <= center_y <= LEDGE_SPAWN_TARGET_Y_MAX
    )


def is_ledge_spawn_tracking_component(component: dict[str, Any]) -> bool:
    _center_x, center_y = component_center(component)
    return center_y <= LEDGE_SPAWN_TRACK_CENTER_Y_MAX


def component_center_in_roi(component: dict[str, Any], roi: list[int]) -> bool:
    center_x, center_y = component_center(component)
    return roi[0] <= center_x <= roi[2] and roi[1] <= center_y <= roi[3]


def component_within_max_center_y(
    component: dict[str, Any],
    max_center_y: int | None,
) -> bool:
    if max_center_y is None:
        return True
    _center_x, center_y = component_center(component)
    return center_y <= max_center_y


def component_ready_difference(
    component: dict[str, Any],
    ready_image: Image.Image,
    after_left_image: Image.Image,
) -> dict[str, int]:
    ready_top = top_screen(ready_image)
    after_left_top = top_screen(after_left_image)
    ready_pixels = ready_top.load()
    after_left_pixels = after_left_top.load()
    x0, y0, x1, y1 = component["bbox"]
    x0 = clamp_int(x0, 0, ready_top.width)
    x1 = clamp_int(x1, 0, ready_top.width)
    y0 = clamp_int(y0, 0, ready_top.height)
    y1 = clamp_int(y1, 0, ready_top.height)
    new_pink_pixels = 0
    diff_pixels = 0
    diff_sum = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            ready_pixel = ready_pixels[x, y]
            after_left_pixel = after_left_pixels[x, y]
            delta = sum(
                abs(after_left_pixel[channel] - ready_pixel[channel])
                for channel in range(3)
            )
            diff_sum += delta
            if delta >= LEDGE_SPAWN_DIFF_PIXEL_THRESHOLD:
                diff_pixels += 1
            if is_igglybuff_pink(after_left_pixel) and not is_igglybuff_pink(ready_pixel):
                new_pink_pixels += 1
    return {
        "new_pink_pixels": new_pink_pixels,
        "diff_pixels": diff_pixels,
        "diff_sum": diff_sum,
    }


def score_ledge_spawn_seed_candidate(
    component: dict[str, Any],
    ready_image: Image.Image,
    after_left_image: Image.Image,
) -> dict[str, Any]:
    candidate = dict(component)
    candidate["center"] = list(component_center(component))
    candidate.update(component_ready_difference(component, ready_image, after_left_image))
    candidate["eligible"] = (
        candidate["pixel_count"] >= LEDGE_SPAWN_MIN_SEED_PINK_PIXELS
        and candidate["new_pink_pixels"] >= LEDGE_SPAWN_MIN_NEW_PINK_PIXELS
    )
    return candidate


def choose_ledge_spawn_origin(
    components: list[dict[str, Any]],
    ready_image: Image.Image,
    after_left_image: Image.Image,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    roi_candidates = [
        score_ledge_spawn_seed_candidate(component, ready_image, after_left_image)
        for component in components
        if is_ledge_spawn_initial_component(component)
    ]
    eligible_candidates = [
        candidate for candidate in roi_candidates if candidate["eligible"]
    ]
    selected = None
    if eligible_candidates:
        selected = max(
            eligible_candidates,
            key=lambda candidate: (
                candidate["new_pink_pixels"],
                candidate["diff_pixels"],
                candidate["pixel_count"],
            ),
        )
    selection = {
        "method": (
            "after-left upper ledge ROI, scored by ready-vs-after-left "
            "new Igglybuff-colored pixels"
        ),
        "target_roi": target_roi_summary(),
        "tracking_band": target_tracking_band_summary(),
        "min_seed_pink_pixels": LEDGE_SPAWN_MIN_SEED_PINK_PIXELS,
        "min_new_pink_pixels": LEDGE_SPAWN_MIN_NEW_PINK_PIXELS,
        "diff_pixel_threshold": LEDGE_SPAWN_DIFF_PIXEL_THRESHOLD,
        "roi_candidate_count": len(roi_candidates),
        "eligible_candidate_count": len(eligible_candidates),
        "roi_candidates": roi_candidates[:8],
        "passed": selected is not None,
    }
    if selected is None:
        selection["error"] = (
            "No newly spawned Igglybuff component was found in the upper ledge "
            "ROI; refusing to fall back to a global/lower pink component."
        )
        return None, selection
    return selected, selection


def choose_roi_origin(
    components: list[dict[str, Any]],
    roi: list[int],
    max_center_y: int | None,
    min_pink_pixels: int,
    target_stage: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    roi_candidates = []
    for component in components:
        if not component_center_in_roi(component, roi):
            continue
        candidate = dict(component)
        candidate["center"] = list(component_center(component))
        candidate["eligible"] = (
            component_within_max_center_y(component, max_center_y)
            and candidate["pixel_count"] >= min_pink_pixels
        )
        roi_candidates.append(candidate)

    eligible_candidates = [
        candidate for candidate in roi_candidates if candidate["eligible"]
    ]
    selected = None
    if eligible_candidates:
        selected = max(
            eligible_candidates,
            key=lambda candidate: candidate["pixel_count"],
        )

    selection = {
        "method": "custom screenshot ROI",
        "target_stage": target_stage,
        "target_roi": target_roi_summary(roi),
        "tracking_band": {"max_center_y": max_center_y},
        "min_seed_pink_pixels": min_pink_pixels,
        "roi_candidate_count": len(roi_candidates),
        "eligible_candidate_count": len(eligible_candidates),
        "roi_candidates": roi_candidates[:8],
        "passed": selected is not None,
    }
    if selected is None:
        selection["error"] = (
            "No eligible Igglybuff component was found in the custom ROI."
        )
        return None, selection
    return selected, selection


def choose_target_component(
    components: list[dict[str, Any]],
    target: str,
    previous: dict[str, Any] | None = None,
    target_max_center_y: int | None = None,
) -> dict[str, Any] | None:
    if not components:
        return None

    if target == "ledge-spawn":
        if previous is None:
            return None
        band_components = [
            component
            for component in components
            if is_ledge_spawn_tracking_component(component)
        ]
        if not band_components:
            return None
        sprite_components = full_body_components(band_components)
        return min(
            sprite_components,
            key=lambda component: component_distance_squared(component, previous),
        )

    if target == "roi":
        if previous is None:
            return None
        tracking_components = [
            component
            for component in components
            if component_within_max_center_y(component, target_max_center_y)
        ]
        if not tracking_components:
            return None
        sprite_components = full_body_components(tracking_components)
        return min(
            sprite_components,
            key=lambda component: component_distance_squared(component, previous),
        )

    sprite_components = full_body_components(components)
    if target == "left":
        return min(sprite_components, key=component_center_x)
    if target == "right":
        return max(sprite_components, key=component_center_x)
    return components[0]


def detect_actual_left_hop_start(
    metrics: list[dict[str, Any]],
    origin: dict[str, Any] | None,
    min_x_delta: int,
    min_y_lift: int,
    min_pink_pixels: int,
    min_body_height: int,
) -> int | None:
    if origin is None:
        return None

    origin_x, _origin_y = component_center(origin)
    origin_top = origin["bbox"][1]
    for metric in metrics:
        bbox = metric.get("pink_bbox")
        if bbox is None:
            continue
        if metric.get("pink_pixels", 0) < min_pink_pixels:
            continue
        if bbox[3] - bbox[1] < min_body_height:
            continue
        center_x = (bbox[0] + bbox[2]) // 2
        if center_x <= origin_x - min_x_delta and bbox[1] <= origin_top - min_y_lift:
            return metric["frame"]
    return None


def shadow_region_for_bbox(bbox: list[int]) -> list[int]:
    x0, y0, x1, y1 = bbox
    center_x = (x0 + x1) // 2
    body_width = max(14, x1 - x0)
    half_width = max(10, body_width // 2 + 5)
    region_x0 = max(0, center_x - half_width)
    region_x1 = min(256, center_x + half_width + 1)
    region_y0 = min(191, y1)
    region_y1 = min(192, y1 + 18)
    return [region_x0, region_y0, region_x1, region_y1]


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def is_main_memory_pointer(value: int, size: int = 1) -> bool:
    return 0x02000000 <= value <= 0x02400000 - size


def read_unsigned_memory(emu: Any, address: int, size: int) -> int | None:
    if not is_main_memory_pointer(address, size):
        return None
    value = emu.memory.unsigned[address : address + size : size]
    if isinstance(value, list):
        if len(value) == 1:
            return int(value[0])
        combined = 0
        for index, byte in enumerate(value[:size]):
            combined |= (int(byte) & 0xFF) << (index * 8)
        return combined
    return int(value)


def hex_or_none(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:08X}"


def collect_s83_primary_probe(emu: Any, base_address: int) -> dict[str, Any]:
    entry_count = read_unsigned_memory(emu, base_address, 4) or 0
    e1_draw_count = read_unsigned_memory(emu, base_address + 4, 4) or 0
    object_flags = read_unsigned_memory(emu, base_address + 8, 4) or 0
    vertical_pack = read_unsigned_memory(emu, base_address + 12, 4) or 0
    render_pack = read_unsigned_memory(emu, base_address + 16, 4) or 0
    sprite_pack = read_unsigned_memory(emu, base_address + 20, 4) or 0
    sprite_word_b8 = read_unsigned_memory(emu, base_address + 24, 4) or 0

    return {
        "base": f"0x{base_address:08X}",
        "entry_count": entry_count,
        "e1_draw_count": e1_draw_count,
        "object_flags": hex_or_none(object_flags),
        "active_mask_present": (object_flags & 0x00012004) == 0x00012004,
        "face_vec_y_low16": vertical_pack & 0xFFFF,
        "unk88_y_low16": (vertical_pack >> 16) & 0xFFFF,
        "render_data": {
            "byte_10": render_pack & 0xFF,
            "byte_14": (render_pack >> 8) & 0xFF,
            "byte_15": (render_pack >> 16) & 0xFF,
            "byte_17": (render_pack >> 24) & 0xFF,
        },
        "sprite": {
            "byte_24": sprite_pack & 0xFF,
            "halfword_b6": (sprite_pack >> 8) & 0xFFFF,
            "word_b8": hex_or_none(sprite_word_b8),
        },
    }


def shadow_core_region_for_bbox(bbox: list[int]) -> list[int]:
    x0, _y0, x1, y1 = bbox
    center_x = (x0 + x1) // 2
    return [
        clamp_int(center_x - 7, 0, 255),
        clamp_int(y1 + 5, 0, 191),
        clamp_int(center_x + 8, 0, 256),
        clamp_int(y1 + 14, 0, 192),
    ]


def shadow_side_regions_for_core(region: list[int]) -> list[list[int]]:
    x0, y0, x1, y1 = region
    width = x1 - x0
    gap = 4
    left = [
        clamp_int(x0 - gap - width, 0, 256),
        y0,
        clamp_int(x0 - gap, 0, 256),
        y1,
    ]
    right = [
        clamp_int(x1 + gap, 0, 256),
        y0,
        clamp_int(x1 + gap + width, 0, 256),
        y1,
    ]
    return [side for side in (left, right) if side[0] < side[2]]


def is_dark(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r + g + b < 210


def is_neutral_dark(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r + g + b < 240 and max(r, g, b) - min(r, g, b) < 55


def region_brightness_stats(
    pixels: Any,
    reference_pixels: Any | None,
    region: list[int],
    delta_threshold: int,
) -> dict[str, float | int]:
    pixel_count = 0
    brightness_total = 0
    delta_total = 0
    relative_dark_pixels = 0

    for y in range(region[1], region[3]):
        for x in range(region[0], region[2]):
            brightness = sum(pixels[x, y])
            brightness_total += brightness
            pixel_count += 1
            if reference_pixels is not None:
                reference_brightness = sum(reference_pixels[x, y])
                delta = reference_brightness - brightness
                delta_total += delta
                if delta >= delta_threshold:
                    relative_dark_pixels += 1

    if pixel_count == 0:
        return {
            "brightness_mean": 0,
            "delta_mean": 0,
            "pixel_count": 0,
            "relative_dark_pixels": 0,
        }

    return {
        "brightness_mean": brightness_total / pixel_count,
        "delta_mean": delta_total / pixel_count,
        "pixel_count": pixel_count,
        "relative_dark_pixels": relative_dark_pixels,
    }


def analyze_frame(
    image: Image.Image,
    reference_top: Image.Image | None,
    delta_threshold: int,
    core_delta_threshold: int,
    core_min_dark_pixels: int,
    core_min_delta_mean: int,
    core_min_local_contrast: int,
    target: str,
    previous_target: dict[str, Any] | None = None,
    target_max_center_y: int | None = None,
) -> dict[str, Any]:
    top = top_screen(image)
    components = find_pink_components(image)
    body = choose_target_component(
        components,
        target,
        previous_target,
        target_max_center_y,
    )
    metric: dict[str, Any] = {
        "target_igglybuff": target,
        "pink_components": components[:4],
        "pink_bbox": None,
        "pink_pixels": 0,
        "shadow_region": None,
        "shadow_core_region": None,
        "dark_pixels_under_body": 0,
        "neutral_dark_pixels_under_body": 0,
        "relative_dark_pixels_under_body": 0,
        "shadow_core_relative_dark_pixels": 0,
        "shadow_core_delta_mean": 0,
        "shadow_core_local_contrast": 0,
        "shadow_present": False,
    }
    if body is None:
        return metric

    bbox = body["bbox"]
    region = shadow_region_for_bbox(bbox)
    core_region = shadow_core_region_for_bbox(bbox)
    side_regions = shadow_side_regions_for_core(core_region)
    pixels = top.load()
    reference_pixels = reference_top.load() if reference_top is not None else None
    dark_pixels = 0
    neutral_dark_pixels = 0
    relative_dark_pixels = 0
    for y in range(region[1], region[3]):
        for x in range(region[0], region[2]):
            pixel = pixels[x, y]
            if is_dark(pixel):
                dark_pixels += 1
            if is_neutral_dark(pixel):
                neutral_dark_pixels += 1
            if reference_pixels is not None:
                reference_pixel = reference_pixels[x, y]
                if sum(pixel) <= sum(reference_pixel) - delta_threshold:
                    relative_dark_pixels += 1

    core_stats = region_brightness_stats(
        pixels,
        reference_pixels,
        core_region,
        core_delta_threshold,
    )
    side_brightness_total = 0.0
    side_pixel_total = 0
    for side_region in side_regions:
        side_stats = region_brightness_stats(
            pixels,
            reference_pixels,
            side_region,
            core_delta_threshold,
        )
        side_brightness_total += side_stats["brightness_mean"] * side_stats["pixel_count"]
        side_pixel_total += side_stats["pixel_count"]
    side_brightness_mean = (
        side_brightness_total / side_pixel_total
        if side_pixel_total != 0
        else core_stats["brightness_mean"]
    )
    core_local_contrast = side_brightness_mean - core_stats["brightness_mean"]
    shadow_present = (
        core_stats["relative_dark_pixels"] >= core_min_dark_pixels
        and core_stats["delta_mean"] >= core_min_delta_mean
        and core_local_contrast >= core_min_local_contrast
    )

    metric.update(
        {
            "pink_bbox": bbox,
            "pink_pixels": body["pixel_count"],
            "shadow_region": region,
            "shadow_core_region": core_region,
            "dark_pixels_under_body": dark_pixels,
            "neutral_dark_pixels_under_body": neutral_dark_pixels,
            "relative_dark_pixels_under_body": relative_dark_pixels,
            "shadow_core_relative_dark_pixels": core_stats["relative_dark_pixels"],
            "shadow_core_delta_mean": round(core_stats["delta_mean"], 3),
            "shadow_core_local_contrast": round(core_local_contrast, 3),
            "shadow_present": shadow_present,
        }
    )
    return metric


def annotate_top_screen(image: Image.Image, metric: dict[str, Any], label: str) -> Image.Image:
    annotated = top_screen(image).copy()
    draw = ImageDraw.Draw(annotated)
    bbox = metric.get("pink_bbox")
    region = metric.get("shadow_region")
    core_region = metric.get("shadow_core_region")
    if region is not None:
        draw.rectangle(region, outline=(64, 128, 255), width=1)
    if core_region is not None:
        draw.rectangle(core_region, outline=(255, 208, 64), width=1)
    if bbox is not None:
        draw.rectangle(bbox, outline=(255, 64, 128), width=1)
    draw.rectangle((0, 0, 255, 13), fill=(255, 255, 255))
    draw.text((2, 2), label, fill=(0, 0, 0))
    return annotated


def make_contact_sheet(
    annotated_frames: list[tuple[int, Image.Image, dict[str, Any]]],
    path: Path,
    every: int,
    columns: int,
    start_frame: int = 0,
) -> None:
    selected = [
        item
        for item in annotated_frames
        if item[0] >= start_frame and (item[0] - start_frame) % every == 0
    ]
    if not selected:
        return

    scale = 2
    tile_width = 256 * scale
    tile_height = 192 * scale
    rows = (len(selected) + columns - 1) // columns
    sheet = Image.new("RGB", (tile_width * columns, tile_height * rows), (255, 255, 255))

    for index, (_frame, image, _metric) in enumerate(selected):
        tile = image.resize((tile_width, tile_height), Image.Resampling.NEAREST)
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        sheet.paste(tile, (x, y))

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def max_consecutive_false(values: list[bool]) -> int:
    best = 0
    current = 0
    for value in values:
        if value:
            current = 0
        else:
            current += 1
            if current > best:
                best = current
    return best


def longest_run(values: list[int]) -> int:
    best = 0
    current = 0
    previous = None
    for value in values:
        if previous is None or value == previous + 1:
            current += 1
        else:
            current = 1
        if current > best:
            best = current
        previous = value
    return best


def is_authoritative_ledge_run(args: argparse.Namespace) -> bool:
    return (
        args.scenario == "ledge-repro"
        and args.target_igglybuff == "ledge-spawn"
        and args.shadow_check_start_frame == AUTHORITATIVE_SHADOW_START_FRAME
        and args.shadow_check_end_frame == AUTHORITATIVE_SHADOW_END_FRAME
    )


def metric_has_valid_body(
    metric: dict[str, Any],
    min_pink_pixels: int,
    min_body_height: int,
) -> bool:
    bbox = metric.get("pink_bbox")
    return (
        bbox is not None
        and metric.get("pink_pixels", 0) >= min_pink_pixels
        and bbox[3] - bbox[1] >= min_body_height
    )


def evaluate_shadow_pass(
    metrics: list[dict[str, Any]],
    start_frame: int,
    end_frame: int,
    min_present_percent: int,
    min_tracked_percent: int,
    max_missing_run: int,
    min_pink_pixels: int,
    min_body_height: int,
) -> dict[str, Any]:
    if end_frame < start_frame:
        start_frame, end_frame = end_frame, start_frame

    expected_frame_count = max(0, end_frame - start_frame + 1)
    window_metrics = [
        metric
        for metric in metrics
        if start_frame <= metric["frame"] <= end_frame
    ]
    valid_body_metrics = [
        metric
        for metric in window_metrics
        if metric_has_valid_body(metric, min_pink_pixels, min_body_height)
    ]
    invalid_body_frames = [
        metric["frame"]
        for metric in window_metrics
        if not metric_has_valid_body(metric, min_pink_pixels, min_body_height)
    ]
    present_frames = [
        metric["frame"]
        for metric in valid_body_metrics
        if metric.get("shadow_present")
    ]
    present_by_frame = {
        metric["frame"]: bool(metric.get("shadow_present"))
        for metric in valid_body_metrics
    }
    shadow_presence = [
        present_by_frame.get(frame, False)
        for frame in range(start_frame, end_frame + 1)
    ]
    present_percent = (
        int(round(100 * len(present_frames) / expected_frame_count))
        if expected_frame_count != 0
        else 0
    )
    tracked_percent = (
        int(round(100 * len(valid_body_metrics) / expected_frame_count))
        if expected_frame_count != 0
        else 0
    )
    max_missing = max_consecutive_false(shadow_presence)
    passed = (
        expected_frame_count != 0
        and tracked_percent >= min_tracked_percent
        and present_percent >= min_present_percent
        and max_missing <= max_missing_run
    )

    return {
        "enabled": True,
        "passed": passed,
        "window_start_frame": start_frame,
        "window_end_frame": end_frame,
        "expected_frame_count": expected_frame_count,
        "valid_body_frame_count": len(valid_body_metrics),
        "tracked_percent": tracked_percent,
        "invalid_body_frame_count": len(invalid_body_frames),
        "invalid_body_frames_first": invalid_body_frames[:12],
        "invalid_body_frames_last": invalid_body_frames[-12:],
        "present_frame_count": len(present_frames),
        "present_percent": present_percent,
        "present_frames_first": present_frames[:12],
        "present_frames_last": present_frames[-12:],
        "missing_shadow_frame_count": expected_frame_count - len(present_frames),
        "max_missing_run": max_missing,
        "required_min_present_percent": min_present_percent,
        "required_min_tracked_percent": min_tracked_percent,
        "required_max_missing_run": max_missing_run,
        "body_min_pink_pixels": min_pink_pixels,
        "body_min_height": min_body_height,
    }


def bbox_center_x(bbox: list[int]) -> int:
    return (bbox[0] + bbox[2]) // 2


def body_centers_from_metrics(
    metrics: list[dict[str, Any]],
    min_pink_pixels: int,
    min_body_height: int,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> list[dict[str, Any]]:
    centers = []
    for metric in metrics:
        frame = metric["frame"]
        if start_frame is not None and frame < start_frame:
            continue
        if end_frame is not None and frame > end_frame:
            continue
        if not metric_has_valid_body(metric, min_pink_pixels, min_body_height):
            continue
        centers.append(
            {
                "frame": frame,
                "center_x": bbox_center_x(metric["pink_bbox"]),
                "bbox": metric["pink_bbox"],
            }
        )
    return centers


def left_progress_records(centers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    best_center_x = None
    for center in centers:
        center_x = center["center_x"]
        if best_center_x is None or center_x < best_center_x:
            records.append(center)
            best_center_x = center_x
    return records


def summarize_movement_progress(
    centers: list[dict[str, Any]],
    actual_left_hop_start_frame: int | None,
    shadow_window_start_frame: int,
    shadow_window_end_frame: int,
    min_left_delta: int,
    min_distinct_center_x: int,
) -> dict[str, Any]:
    if actual_left_hop_start_frame is None:
        return {
            "passed": False,
            "reason": "actual left hop start was not detected",
            "actual_left_hop_start_frame": None,
            "required_min_left_delta": min_left_delta,
            "required_min_distinct_center_x": min_distinct_center_x,
        }

    hop_centers = [
        center
        for center in centers
        if actual_left_hop_start_frame <= center["frame"] <= shadow_window_end_frame
    ]
    if not hop_centers:
        return {
            "passed": False,
            "reason": "no valid tracked body centers after actual left hop start",
            "actual_left_hop_start_frame": actual_left_hop_start_frame,
            "required_min_left_delta": min_left_delta,
            "required_min_distinct_center_x": min_distinct_center_x,
        }

    records = left_progress_records(hop_centers)
    progress_records = records[1:]
    distinct_center_x_count = len({center["center_x"] for center in hop_centers})
    progress_left_delta = records[0]["center_x"] - records[-1]["center_x"]
    progress_frames_in_shadow_window = [
        center["frame"]
        for center in progress_records
        if shadow_window_start_frame <= center["frame"] <= shadow_window_end_frame
    ]
    progress_reaches_shadow_window = bool(progress_frames_in_shadow_window)
    passed = (
        progress_left_delta >= min_left_delta
        and distinct_center_x_count >= min_distinct_center_x
        and progress_reaches_shadow_window
    )
    reason = None
    if not passed:
        missing = []
        if progress_left_delta < min_left_delta:
            missing.append("left delta")
        if distinct_center_x_count < min_distinct_center_x:
            missing.append("distinct center-x positions")
        if not progress_reaches_shadow_window:
            missing.append("left progress inside shadow window")
        reason = "missing " + ", ".join(missing)

    return {
        "passed": passed,
        "reason": reason,
        "actual_left_hop_start_frame": actual_left_hop_start_frame,
        "progress_window_start_frame": records[0]["frame"],
        "progress_window_end_frame": records[-1]["frame"],
        "progress_window_start_center_x": records[0]["center_x"],
        "progress_window_end_center_x": records[-1]["center_x"],
        "progress_left_delta": progress_left_delta,
        "left_progress_record_count": len(progress_records),
        "distinct_center_x_count": distinct_center_x_count,
        "shadow_window_start_frame": shadow_window_start_frame,
        "shadow_window_end_frame": shadow_window_end_frame,
        "left_progress_frames_in_shadow_window_count": len(progress_frames_in_shadow_window),
        "first_left_progress_frame_in_shadow_window": (
            progress_frames_in_shadow_window[0]
            if progress_frames_in_shadow_window
            else None
        ),
        "last_left_progress_frame_in_shadow_window": (
            progress_frames_in_shadow_window[-1]
            if progress_frames_in_shadow_window
            else None
        ),
        "required_min_left_delta": min_left_delta,
        "required_min_distinct_center_x": min_distinct_center_x,
        "progress_records_first": records[:6],
        "progress_records_last": records[-6:],
    }


def summarize_landing_stall(
    centers: list[dict[str, Any]],
    min_center_frame: int | None,
    end_frame: int,
) -> dict[str, Any]:
    if min_center_frame is None:
        return {
            "detected": False,
            "reason": "minimum center frame unavailable",
        }

    tail_centers = [
        center
        for center in centers
        if min_center_frame <= center["frame"] <= end_frame
    ]
    if not tail_centers:
        return {
            "detected": False,
            "reason": "no tracked body centers from minimum center frame to window end",
            "start_frame": min_center_frame,
            "window_end_frame": end_frame,
        }

    tail_x_values = [center["center_x"] for center in tail_centers]
    tail_min_x = min(tail_x_values)
    tail_max_x = max(tail_x_values)
    distinct_tail_x_count = len(set(tail_x_values))
    detected = len(tail_centers) >= 6 and tail_max_x - tail_min_x <= 2
    return {
        "detected": detected,
        "start_frame": tail_centers[0]["frame"],
        "window_end_frame": end_frame,
        "tracked_frame_count": len(tail_centers),
        "center_x_min": tail_min_x,
        "center_x_max": tail_max_x,
        "center_x_delta": tail_max_x - tail_min_x,
        "distinct_center_x_count": distinct_tail_x_count,
        "first_bboxes": tail_centers[:6],
        "last_bboxes": tail_centers[-6:],
    }


def evaluate_movement_pass(
    metrics: list[dict[str, Any]],
    target_origin: dict[str, Any] | None,
    actual_left_hop_start_frame: int | None,
    start_frame: int,
    end_frame: int,
    min_origin_left_delta: int,
    min_window_left_delta: int,
    min_distinct_center_x: int,
    min_tracked_percent: int,
    min_pink_pixels: int,
    min_body_height: int,
) -> dict[str, Any]:
    if end_frame < start_frame:
        start_frame, end_frame = end_frame, start_frame

    expected_frame_count = max(0, end_frame - start_frame + 1)
    all_centers = body_centers_from_metrics(
        metrics,
        min_pink_pixels,
        min_body_height,
    )
    centers = [
        center
        for center in all_centers
        if start_frame <= center["frame"] <= end_frame
    ]
    tracked_percent = (
        int(round(100 * len(centers) / expected_frame_count))
        if expected_frame_count != 0
        else 0
    )
    movement_progress_pass = summarize_movement_progress(
        all_centers,
        actual_left_hop_start_frame,
        start_frame,
        end_frame,
        min_window_left_delta,
        min_distinct_center_x,
    )
    if not centers or target_origin is None:
        return {
            "enabled": True,
            "passed": False,
            "window_start_frame": start_frame,
            "window_end_frame": end_frame,
            "expected_frame_count": expected_frame_count,
            "tracked_percent": tracked_percent,
            "reason": "missing target origin or tracked body",
            "required_min_tracked_percent": min_tracked_percent,
            "required_min_origin_left_delta": min_origin_left_delta,
            "required_min_window_left_delta": min_window_left_delta,
            "required_min_distinct_center_x": min_distinct_center_x,
            "movement_progress_pass": movement_progress_pass,
            "landing_stall": summarize_landing_stall(all_centers, None, end_frame),
        }

    origin_center_x = component_center_x(target_origin)
    first_center_x = centers[0]["center_x"]
    min_center_item = min(centers, key=lambda item: item["center_x"])
    origin_left_delta = origin_center_x - min_center_item["center_x"]
    window_left_delta = first_center_x - min_center_item["center_x"]
    landing_stall = summarize_landing_stall(
        all_centers,
        min_center_item["frame"],
        end_frame,
    )
    passed = (
        tracked_percent >= min_tracked_percent
        and origin_left_delta >= min_origin_left_delta
        and window_left_delta >= min_window_left_delta
        and movement_progress_pass["passed"]
    )

    return {
        "enabled": True,
        "passed": passed,
        "window_start_frame": start_frame,
        "window_end_frame": end_frame,
        "expected_frame_count": expected_frame_count,
        "tracked_frame_count": len(centers),
        "tracked_percent": tracked_percent,
        "origin_center_x": origin_center_x,
        "first_window_center_x": first_center_x,
        "min_center_x": min_center_item["center_x"],
        "min_center_frame": min_center_item["frame"],
        "origin_left_delta": origin_left_delta,
        "window_left_delta": window_left_delta,
        "required_min_tracked_percent": min_tracked_percent,
        "required_min_origin_left_delta": min_origin_left_delta,
        "required_min_window_left_delta": min_window_left_delta,
        "required_min_distinct_center_x": min_distinct_center_x,
        "movement_progress_pass": movement_progress_pass,
        "landing_stall": landing_stall,
        "first_bboxes": centers[:6],
        "last_bboxes": centers[-6:],
    }


def choose_initial_target_for_stage(
    args: argparse.Namespace,
    components: list[dict[str, Any]],
    ready_image: Image.Image,
    target_image: Image.Image,
    target_stage: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if args.target_igglybuff == "ledge-spawn":
        target_origin, target_selection = choose_ledge_spawn_origin(
            components,
            ready_image,
            target_image,
        )
        target_selection["mode"] = args.target_igglybuff
        target_selection["target_stage"] = target_stage
        return target_origin, target_selection

    if args.target_igglybuff == "roi":
        if args.target_roi is None:
            raise ValueError("--target-roi is required when --target-igglybuff roi")
        target_origin, target_selection = choose_roi_origin(
            components,
            args.target_roi,
            args.target_max_center_y,
            args.target_roi_min_pink_pixels,
            target_stage,
        )
        target_selection["mode"] = args.target_igglybuff
        return target_origin, target_selection

    target_origin = choose_target_component(
        components,
        args.target_igglybuff,
    )
    return target_origin, {
        "mode": args.target_igglybuff,
        "method": f"{args.target_igglybuff} pink component from screenshot stage",
        "target_stage": target_stage,
        "passed": target_origin is not None,
    }


def capture_metric_window(
    emu: Any,
    args: argparse.Namespace,
    frame_dir: Path,
    capture_key: str,
    hold_frames: int,
    capture_frames: int,
    release_frames: int,
    parsed_memory_reads: list[Any],
    previous_target: dict[str, Any] | None,
) -> tuple[
    list[dict[str, Any]],
    list[tuple[int, Image.Image, dict[str, Any]]],
    list[dict[str, Any]],
    dict[str, Any] | None,
]:
    metrics = []
    annotated_frames = []
    memory_samples = []
    reference_top = None

    key_mask = headless.keymask(headless.key_constant(capture_key))
    emu.input.keypad_add_key(key_mask)
    key_is_held = True
    for frame in range(capture_frames + 1):
        if key_is_held and frame > hold_frames:
            emu.input.keypad_rm_key(key_mask)
            key_is_held = False
        if frame % args.capture_every == 0:
            frame_path = frame_dir / f"{args.prefix}_f{frame:03d}.png"
            image = capture(emu, frame_path)
            if reference_top is None:
                reference_top = top_screen(image)
            metric = analyze_frame(
                image,
                reference_top,
                args.shadow_delta_threshold,
                args.shadow_core_delta_threshold,
                args.shadow_core_min_dark_pixels,
                args.shadow_core_min_delta_mean,
                args.shadow_core_min_local_contrast,
                args.target_igglybuff,
                previous_target,
                args.target_max_center_y,
            )
            if metric["pink_bbox"] is not None:
                previous_target = {
                    "bbox": metric["pink_bbox"],
                    "pixel_count": metric["pink_pixels"],
                }
            metric.update(
                {
                    "frame": frame,
                    "path": str(frame_path),
                    "capture_key": capture_key,
                    "capture_key_held": key_is_held,
                }
            )
            if capture_key == "RIGHT":
                metric["right_held"] = key_is_held
            core_contrast = metric.get("shadow_core_local_contrast", 0)
            try:
                core_contrast_text = f"{float(core_contrast):.0f}"
            except (TypeError, ValueError):
                core_contrast_text = "0"
            label = (
                f"f{frame:03d} core={metric['shadow_core_relative_dark_pixels']} "
                f"c={core_contrast_text} "
                f"{'ok' if metric['shadow_present'] else '--'}"
            )
            annotated_frames.append(
                (frame, annotate_top_screen(image, metric, label), metric)
            )
            metrics.append(metric)

        if (
            (parsed_memory_reads or args.s83_primary_probe_base)
            and args.memory_sample_every > 0
            and frame % args.memory_sample_every == 0
        ):
            sample = {
                "frame": frame,
                "reads": [
                    headless.read_memory(emu, read)
                    for read in parsed_memory_reads
                ],
            }
            if args.s83_primary_probe_base:
                sample["s83_primary_probe"] = collect_s83_primary_probe(
                    emu,
                    args.s83_primary_probe_base,
                )
            memory_samples.append(sample)
        if frame < capture_frames:
            headless.cycle(emu, 1)
    if key_is_held:
        emu.input.keypad_rm_key(key_mask)
        key_is_held = False
    headless.cycle(emu, release_frames)

    return metrics, annotated_frames, memory_samples, previous_target


def run_custom_actions(
    args: argparse.Namespace,
    emu: Any,
    output_dir: Path,
    frame_dir: Path,
    ready_image: Image.Image,
    ready_components: list[dict[str, Any]],
    ready_path: Path,
    parsed_memory_reads: list[Any],
) -> dict[str, Any]:
    actions = getattr(args, "parsed_actions", parse_action_specs(args.action))
    stage_images = {"ready": ready_image}
    stage_components = {"ready": ready_components}
    stage_screenshots = {"ready": str(ready_path)}
    latest_stage = "ready"
    capture_index = 1
    metrics = []
    annotated_frames = []
    memory_samples = []
    target_origin = None
    previous_target = None
    target_selection = {
        "mode": args.target_igglybuff,
        "passed": True,
    }
    action_log = []

    for action in actions:
        if action["action"] == "wait":
            headless.cycle(emu, action["frames"])
            action_log.append(dict(action))
            continue

        if action["action"] == "hold":
            release_frames = action.get("release_frames", args.tap_gap_frames)
            headless.hold_key(
                emu,
                action["key"],
                action["frames"],
                release_frames,
            )
            logged = dict(action)
            logged["release_frames"] = release_frames
            action_log.append(logged)
            continue

        if action["action"] == "capture":
            stage = action["stage"]
            stage_path = output_dir / f"{args.prefix}_{capture_index:02d}_{stage}.png"
            capture_index += 1
            stage_image = capture(emu, stage_path)
            stage_images[stage] = stage_image
            stage_components[stage] = find_pink_components(stage_image)
            stage_screenshots[stage] = str(stage_path)
            latest_stage = stage
            logged = dict(action)
            logged["path"] = str(stage_path)
            action_log.append(logged)
            continue

        target_stage = args.target_stage or latest_stage
        if target_stage not in stage_components:
            raise ValueError(
                f"--target-stage {target_stage!r} was not captured before capture-hold"
            )
        target_origin, target_selection = choose_initial_target_for_stage(
            args,
            stage_components[target_stage],
            ready_image,
            stage_images[target_stage],
            target_stage,
        )
        previous_target = target_origin
        release_frames = action.get("release_frames", args.right_release)
        (
            window_metrics,
            window_annotated_frames,
            window_memory_samples,
            previous_target,
        ) = capture_metric_window(
            emu,
            args,
            frame_dir,
            action["key"],
            action["hold_frames"],
            action["capture_frames"],
            release_frames,
            parsed_memory_reads,
            previous_target,
        )
        metrics.extend(window_metrics)
        annotated_frames.extend(window_annotated_frames)
        memory_samples.extend(window_memory_samples)
        logged = dict(action)
        logged["target_stage"] = target_stage
        logged["release_frames"] = release_frames
        logged["capture_every"] = args.capture_every
        action_log.append(logged)

    return {
        "actions": action_log,
        "metrics": metrics,
        "annotated_frames": annotated_frames,
        "memory_samples": memory_samples,
        "target_origin": target_origin,
        "target_selection": target_selection,
        "stage_screenshots": stage_screenshots,
        "stage_components": {
            stage: components[:4]
            for stage, components in stage_components.items()
        },
    }


def run_harness(args: argparse.Namespace) -> dict[str, Any]:
    parsed_memory_reads = [headless.parse_read(spec) for spec in args.memory_read]
    rom = repo_path(args.rom)
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")

    dsv = headless.find_dsv(args.dsv)
    raw_save = headless.extract_raw_save(dsv)
    output_dir = repo_path(args.output_dir)
    frame_dir = output_dir / f"{args.prefix}_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.monotonic()
    metrics = []
    annotated_frames = []
    ready_components = []
    after_left_components = []
    after_left_path = None
    target_origin = None
    target_selection = {
        "mode": args.target_igglybuff,
        "passed": True,
    }
    action_log = []
    stage_screenshots = {}
    stage_components = {}
    memory_reads = []
    memory_samples = []
    s83_primary_probe_final = None

    with headless.silence_native_output(not args.show_emulator_log):
        emu = headless.DeSmuME()
        emu.volume_set(0)
        emu.open(str(rom))
        with tempfile.NamedTemporaryFile(suffix=".sav") as raw_file:
            raw_file.write(raw_save)
            raw_file.flush()
            emu.backup.import_file(raw_file.name, force_size=0)

            ready_frames = headless.boot_to_ready(args, emu)
            ready_path = output_dir / f"{args.prefix}_00_ready.png"
            ready_image = capture(emu, ready_path)
            ready_components = find_pink_components(ready_image)
            stage_screenshots = {"ready": str(ready_path)}
            stage_components = {"ready": ready_components[:4]}

            if args.scenario == "ledge-repro":
                headless.cycle(emu, args.pre_left_wait)
                headless.hold_key(emu, "LEFT", args.left_hold, args.left_release)
                headless.cycle(emu, args.after_left_wait)
                after_left_path = output_dir / f"{args.prefix}_01_after_left_spawn.png"
                left_image = capture(emu, after_left_path)
                after_left_components = find_pink_components(left_image)
                stage_screenshots["after_left_spawn"] = str(after_left_path)
                stage_components["after_left_spawn"] = after_left_components[:4]
                target_origin, target_selection = choose_initial_target_for_stage(
                    args,
                    after_left_components,
                    ready_image,
                    left_image,
                    "after_left_spawn",
                )
                previous_target = target_origin
                (
                    metrics,
                    annotated_frames,
                    memory_samples,
                    _previous_target,
                ) = capture_metric_window(
                    emu,
                    args,
                    frame_dir,
                    "RIGHT",
                    args.right_hold,
                    args.capture_frames,
                    args.right_release,
                    parsed_memory_reads,
                    previous_target,
                )
                action_log = [
                    {"action": "wait", "frames": args.pre_left_wait},
                    {
                        "action": "hold",
                        "key": "LEFT",
                        "frames": args.left_hold,
                        "release_frames": args.left_release,
                        "intent": "spawn ledge-adjacent Igglybuff",
                    },
                    {"action": "wait", "frames": args.after_left_wait},
                    {
                        "action": "hold_and_capture",
                        "key": "RIGHT",
                        "hold_frames": args.right_hold,
                        "release_frames": args.right_release,
                        "capture_frames": args.capture_frames,
                        "capture_every": args.capture_every,
                        "intent": "trigger spawned Igglybuff hop",
                    },
                ]
            else:
                custom_result = run_custom_actions(
                    args,
                    emu,
                    output_dir,
                    frame_dir,
                    ready_image,
                    ready_components,
                    ready_path,
                    parsed_memory_reads,
                )
                metrics = custom_result["metrics"]
                annotated_frames = custom_result["annotated_frames"]
                memory_samples = custom_result["memory_samples"]
                target_origin = custom_result["target_origin"]
                target_selection = custom_result["target_selection"]
                action_log = custom_result["actions"]
                stage_screenshots = custom_result["stage_screenshots"]
                stage_components = custom_result["stage_components"]

            memory_reads = [
                headless.read_memory(emu, read) for read in parsed_memory_reads
            ]
            if args.s83_primary_probe_base:
                s83_primary_probe_final = collect_s83_primary_probe(
                    emu,
                    args.s83_primary_probe_base,
                )
            emu.destroy()

    candidate_shadow_frames = [
        metric["frame"]
        for metric in metrics
        if metric["relative_dark_pixels_under_body"] >= args.relative_shadow_threshold
    ]
    candidate_shadow_frames_in_authoritative_window = [
        frame
        for frame in candidate_shadow_frames
        if AUTHORITATIVE_SHADOW_START_FRAME <= frame <= AUTHORITATIVE_SHADOW_END_FRAME
    ]
    actual_left_hop_start_frame = detect_actual_left_hop_start(
        metrics,
        target_origin,
        args.actual_hop_min_x_delta,
        args.actual_hop_min_y_lift,
        args.actual_hop_min_pink_pixels,
        args.actual_hop_min_body_height,
    )
    contact_start_frame = 0
    if args.contact_start_frame is not None:
        contact_start_frame = max(0, args.contact_start_frame)
    elif is_authoritative_ledge_run(args):
        contact_start_frame = AUTHORITATIVE_SHADOW_START_FRAME
    elif actual_left_hop_start_frame is not None:
        contact_start_frame = max(
            0,
            actual_left_hop_start_frame
            + max(0, args.contact_delay_after_hop)
            - max(0, args.contact_pre_roll),
        )
    contact_path = output_dir / f"{args.prefix}_contact.png"
    make_contact_sheet(
        annotated_frames,
        contact_path,
        max(1, args.contact_every),
        max(1, args.contact_columns),
        contact_start_frame,
    )
    if args.disable_shadow_pass_check:
        shadow_pass = {"enabled": False, "passed": None}
    else:
        shadow_pass = evaluate_shadow_pass(
            metrics,
            args.shadow_check_start_frame,
            args.shadow_check_end_frame,
            args.shadow_check_min_present_percent,
            args.shadow_check_min_tracked_percent,
            args.shadow_check_max_missing_run,
            args.actual_hop_min_pink_pixels,
            args.actual_hop_min_body_height,
        )
    if args.disable_movement_pass_check:
        movement_pass = {"enabled": False, "passed": None}
    else:
        movement_pass = evaluate_movement_pass(
            metrics,
            target_origin,
            actual_left_hop_start_frame,
            args.shadow_check_start_frame,
            args.shadow_check_end_frame,
            args.movement_check_min_origin_left_delta,
            args.movement_check_min_window_left_delta,
            args.movement_check_min_distinct_center_x,
            args.movement_check_min_tracked_percent,
            args.actual_hop_min_pink_pixels,
            args.actual_hop_min_body_height,
        )

    return {
        "rom": str(rom),
        "dsv": str(dsv),
        "dsv_path": str(dsv),
        "output_dir": str(output_dir),
        "scenario": args.scenario,
        "ready_frames": ready_frames,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "actions": action_log,
        "ready_screenshot": str(output_dir / f"{args.prefix}_00_ready.png"),
        "after_left_screenshot": str(after_left_path) if after_left_path else None,
        "stage_screenshots": stage_screenshots,
        "ready_pink_components": ready_components[:4],
        "after_left_pink_components": after_left_components[:4],
        "stage_pink_components": stage_components,
        "target_selection": target_selection,
        "target_origin": target_origin,
        "contact_sheet": str(contact_path),
        "contact_start_frame": contact_start_frame,
        "contact_delay_after_hop": args.contact_delay_after_hop,
        "authoritative_run": {
            "passed": is_authoritative_ledge_run(args),
            "required_scenario": "ledge-repro",
            "required_target_igglybuff": "ledge-spawn",
            "required_shadow_window": [
                AUTHORITATIVE_SHADOW_START_FRAME,
                AUTHORITATIVE_SHADOW_END_FRAME,
            ],
            "actual_shadow_window": [
                args.shadow_check_start_frame,
                args.shadow_check_end_frame,
            ],
        },
        "actual_left_hop_start_frame": actual_left_hop_start_frame,
        "second_left_jump_start_frame": actual_left_hop_start_frame,
        "shadow_dark_threshold": args.shadow_dark_threshold,
        "shadow_delta_threshold": args.shadow_delta_threshold,
        "relative_shadow_threshold": args.relative_shadow_threshold,
        "shadow_core_delta_threshold": args.shadow_core_delta_threshold,
        "shadow_core_min_dark_pixels": args.shadow_core_min_dark_pixels,
        "shadow_core_min_delta_mean": args.shadow_core_min_delta_mean,
        "shadow_core_min_local_contrast": args.shadow_core_min_local_contrast,
        "shadow_pass": shadow_pass,
        "movement_pass": movement_pass,
        "movement_progress_pass": movement_pass.get("movement_progress_pass"),
        "landing_stall": movement_pass.get("landing_stall"),
        "target_igglybuff": args.target_igglybuff,
        "memory_reads": memory_reads,
        "memory_samples": memory_samples,
        "s83_primary_probe_final": s83_primary_probe_final,
        "candidate_shadow_frames": candidate_shadow_frames,
        "candidate_shadow_frames_in_authoritative_window": (
            candidate_shadow_frames_in_authoritative_window
        ),
        "longest_candidate_shadow_run": longest_run(candidate_shadow_frames),
        "longest_authoritative_candidate_shadow_run": longest_run(
            candidate_shadow_frames_in_authoritative_window
        ),
        "metrics": metrics,
        "notes": [
            "Pink and shadow metrics are heuristics for the Igglybuff repro; inspect frames/contact sheet before concluding.",
            "Pink bbox is drawn magenta; broad shadow context is blue; pass/fail shadow core is yellow.",
            "The pass rule uses same-run reference and local contrast so different time-of-day palettes do not need separate absolute thresholds.",
            "The movement pass prevents shadow-only false positives where the target stalls instead of completing the leftward hop.",
        ],
    }


def main() -> int:
    args = parse_args()
    if args.capture_every <= 0:
        raise ValueError("--capture-every must be greater than zero")
    if args.target_max_center_y is not None and not 0 <= args.target_max_center_y <= 191:
        raise ValueError("--target-max-center-y must be inside the top screen")
    if args.target_roi_min_pink_pixels <= 0:
        raise ValueError("--target-roi-min-pink-pixels must be greater than zero")
    if args.target_igglybuff == "roi" and args.target_roi is None:
        raise ValueError("--target-roi is required when --target-igglybuff roi")
    if args.target_stage is not None:
        args.target_stage = sanitize_stage_name(args.target_stage)
    if args.scenario == "ledge-repro":
        if args.action:
            raise ValueError("--action is only valid with --scenario custom")
        args.parsed_actions = []
    else:
        if not args.action:
            raise ValueError("--scenario custom requires at least one --action")
        args.parsed_actions = parse_action_specs(args.action)
    result = run_harness(args)
    output_dir = Path(result["output_dir"])
    summary_path = output_dir / f"{args.prefix}_summary.json"
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["summary"] = str(summary_path)
    compact = dict(result)
    compact["metric_count"] = len(result["metrics"])
    del compact["metrics"]
    print(json.dumps(compact, indent=2, sort_keys=True))
    authoritative = result.get("authoritative_run", {}).get("passed") is True
    target_selection = result.get("target_selection", {})
    if target_selection.get("passed") is False:
        return 2
    shadow_pass = result.get("shadow_pass", {})
    if (
        shadow_pass.get("enabled")
        and shadow_pass.get("passed") is False
        and not args.no_fail_on_shadow_pass
    ):
        return 2
    movement_pass = result.get("movement_pass", {})
    if (
        movement_pass.get("enabled")
        and movement_pass.get("passed") is False
        and not args.no_fail_on_movement_pass
    ):
        return 2
    if (
        not authoritative
        and shadow_pass.get("enabled")
        and movement_pass.get("enabled")
        and not args.no_fail_on_shadow_pass
        and not args.no_fail_on_movement_pass
    ):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print(f"error: {exc}")
        raise SystemExit(1)
