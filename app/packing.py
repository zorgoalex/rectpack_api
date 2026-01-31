from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Dict, Iterable, List, Optional, Tuple

from rectpack import newPacker

from .config import settings
from .errors import ConstraintError, TimeoutError, ValidationError
from .models import (
    Artifacts,
    Engine,
    EngineSummary,
    OptimizeRequest,
    OptimizeResponse,
    Placement,
    Solution,
    Summary,
)
from .svg import render_svg


try:
    from rectpack import (
        PackingMode,
        BinAlgo,
        SORT_NONE,
        GuillotineBssfSas,
        MaxRectsBssf,
        SkylineBl,
    )
except Exception:  # pragma: no cover - fallback for older rectpack versions
    PackingMode = None
    BinAlgo = None
    SORT_NONE = None
    GuillotineBssfSas = None
    MaxRectsBssf = None
    SkylineBl = None


@dataclass
class _BinMeta:
    stock_id: str
    index: int
    width_mm: float
    height_mm: float
    trim_left: float
    trim_top: float
    bin_w_int: int
    bin_h_int: int
    bin_w_mm: float
    bin_h_mm: float


@dataclass
class _RectMeta:
    item_id: str
    instance: int
    width_mm: float
    height_mm: float
    rotated: bool
    pattern_direction: str
    width_eff_int: int
    height_eff_int: int


@dataclass
class _PackedRect:
    bin_index: int
    x_int: int
    y_int: int
    w_int: int
    h_int: int
    rid: int


@dataclass(frozen=True)
class _GuillotineRect:
    x: int
    y: int
    w: int
    h: int


def _mm_to_int(value_mm: float, scale: int) -> int:
    return int(round(value_mm * scale))


def _int_to_mm(value_int: int, scale: int) -> float:
    return value_int / scale


def _splitmix64(seed: int) -> int:
    x = (seed + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return z ^ (z >> 31)


def _resolve_mode_engine(params: OptimizeRequest) -> Tuple[str, Engine]:
    mode = params.params.mode or "guillotine"
    engine = params.params.engine

    default_packer = "guillotine" if mode == "guillotine" else "maxrects"
    default_sort = "area_desc"
    default_bin_select = "best_fit"

    if engine is None:
        engine = Engine(packer=default_packer, sort=default_sort, bin_select=default_bin_select)
    else:
        engine = Engine(
            packer=engine.packer or default_packer,
            sort=engine.sort or default_sort,
            bin_select=engine.bin_select or default_bin_select,
        )

    if mode == "guillotine" and engine.packer != "guillotine":
        raise ValidationError("engine.packer must be 'guillotine' for mode='guillotine'")
    if mode == "nested" and engine.packer == "guillotine":
        raise ValidationError("engine.packer must not be 'guillotine' for mode='nested'")

    return mode, engine


def _allowed_orientations(
    width_mm: float, height_mm: float, rotation: str, pattern: str
) -> List[Tuple[float, float, bool]]:
    if width_mm == height_mm:
        return [(width_mm, height_mm, False)]

    base = [(width_mm, height_mm, False)]
    if rotation == "allow_90":
        base.append((height_mm, width_mm, True))

    if pattern == "none":
        return base

    larger_is_width = width_mm >= height_mm

    if pattern == "along_width":
        if larger_is_width:
            return [(width_mm, height_mm, False)]
        if rotation != "allow_90":
            raise ValidationError("pattern_direction requires rotation but rotation is forbidden")
        return [(height_mm, width_mm, True)]

    if pattern == "along_height":
        if not larger_is_width:
            return [(width_mm, height_mm, False)]
        if rotation != "allow_90":
            raise ValidationError("pattern_direction requires rotation but rotation is forbidden")
        return [(height_mm, width_mm, True)]

    return base


def _validate_request(req: OptimizeRequest, scale: int) -> None:
    if req.units != "mm":
        raise ValidationError("units must be 'mm'")

    total_qty = sum(item.qty for item in req.items)
    if total_qty > min(5000, settings.max_instances):
        raise ValidationError("items.qty total exceeds limit")

    if len(req.stock) > 50:
        raise ValidationError("stock length exceeds limit")

    for stock in req.stock:
        trim = req.params.trim_mm
        if trim.left + trim.right >= stock.width_mm:
            raise ValidationError("trim.left + trim.right must be less than stock.width_mm")
        if trim.top + trim.bottom >= stock.height_mm:
            raise ValidationError("trim.top + trim.bottom must be less than stock.height_mm")

    if scale <= 0:
        raise ValidationError("unit_scale must be positive")


def _build_bins(req: OptimizeRequest, scale: int) -> List[_BinMeta]:
    bins: List[_BinMeta] = []
    trim = req.params.trim_mm
    for stock in req.stock:
        bin_w_mm = stock.width_mm - trim.left - trim.right
        bin_h_mm = stock.height_mm - trim.top - trim.bottom
        bin_w_int = _mm_to_int(bin_w_mm, scale)
        bin_h_int = _mm_to_int(bin_h_mm, scale)
        for i in range(stock.qty):
            bins.append(
                _BinMeta(
                    stock_id=stock.id,
                    index=i,
                    width_mm=stock.width_mm,
                    height_mm=stock.height_mm,
                    trim_left=trim.left,
                    trim_top=trim.top,
                    bin_w_int=bin_w_int,
                    bin_h_int=bin_h_int,
                    bin_w_mm=bin_w_mm,
                    bin_h_mm=bin_h_mm,
                )
            )
    return bins


def _validate_fit(req: OptimizeRequest, bins: List[_BinMeta], scale: int) -> None:
    spacing = req.params.spacing_mm
    for item in req.items:
        orientations = _allowed_orientations(
            item.width_mm, item.height_mm, item.rotation, item.pattern_direction
        )
        can_fit = False
        for w_mm, h_mm, _ in orientations:
            w_eff = w_mm + spacing
            h_eff = h_mm + spacing
            w_eff_int = _mm_to_int(w_eff, scale)
            h_eff_int = _mm_to_int(h_eff, scale)
            for b in bins:
                if w_eff_int <= b.bin_w_int and h_eff_int <= b.bin_h_int:
                    can_fit = True
                    break
            if can_fit:
                break
        if not can_fit:
            raise ValidationError(f"item {item.id} cannot fit into any stock")


def _resolve_bin_algo(bin_select: str):
    if BinAlgo is None:
        return None
    if bin_select == "best_fit":
        return getattr(BinAlgo, "BBF", None) or getattr(BinAlgo, "BFF", None)
    if bin_select == "first_fit":
        return getattr(BinAlgo, "BFF", None) or getattr(BinAlgo, "BNF", None)
    return None


def _resolve_pack_algo(packer: str):
    if packer == "guillotine":
        return GuillotineBssfSas
    if packer == "maxrects":
        return MaxRectsBssf
    if packer == "skyline":
        return SkylineBl
    return None


def _new_packer(engine: Engine):
    pack_algo = _resolve_pack_algo(engine.packer or "guillotine")
    bin_algo = _resolve_bin_algo(engine.bin_select or "best_fit")
    kwargs = {"rotation": False}
    if PackingMode is not None:
        kwargs["mode"] = PackingMode.Offline
    if pack_algo is not None:
        kwargs["pack_algo"] = pack_algo
    if bin_algo is not None:
        kwargs["bin_algo"] = bin_algo
    if SORT_NONE is not None:
        kwargs["sort_algo"] = SORT_NONE
    return newPacker(**kwargs)


def _extract_rects(packer) -> List[_PackedRect]:
    rects: List[_PackedRect] = []

    if hasattr(packer, "rect_list"):
        raw = packer.rect_list()
        for entry in raw:
            if isinstance(entry, tuple):
                if len(entry) >= 6:
                    bin_index, x, y, w, h, rid = entry[:6]
                    rects.append(_PackedRect(bin_index, x, y, w, h, rid))
                elif len(entry) == 5:
                    bin_index, x, y, w, h = entry
                    rects.append(_PackedRect(bin_index, x, y, w, h, -1))
            else:
                bin_index = getattr(entry, "bin", 0)
                rects.append(
                    _PackedRect(
                        int(bin_index),
                        int(entry.x),
                        int(entry.y),
                        int(entry.width),
                        int(entry.height),
                        int(getattr(entry, "rid", -1)),
                    )
                )
        return rects

    for bin_index, abin in enumerate(packer):
        if hasattr(abin, "rect_list"):
            raw_rects = abin.rect_list()
        else:
            raw_rects = abin
        for entry in raw_rects:
            if isinstance(entry, tuple):
                if len(entry) >= 5:
                    x, y, w, h, rid = entry[:5]
                    rects.append(_PackedRect(bin_index, x, y, w, h, rid))
            else:
                rects.append(
                    _PackedRect(
                        bin_index,
                        int(entry.x),
                        int(entry.y),
                        int(entry.width),
                        int(entry.height),
                        int(getattr(entry, "rid", -1)),
                    )
                )
    return rects


def _is_guillotine(rects: List[_GuillotineRect], x0: int, y0: int, w: int, h: int) -> bool:
    if len(rects) <= 1:
        return True

    xs = sorted({r.x for r in rects} | {r.x + r.w for r in rects})
    for x in xs:
        if x <= x0 or x >= x0 + w:
            continue
        if any(r.x < x < r.x + r.w for r in rects):
            continue
        left = [r for r in rects if r.x + r.w <= x]
        right = [r for r in rects if r.x >= x]
        if _is_guillotine(left, x0, y0, x - x0, h) and _is_guillotine(
            right, x, y0, x0 + w - x, h
        ):
            return True

    ys = sorted({r.y for r in rects} | {r.y + r.h for r in rects})
    for y in ys:
        if y <= y0 or y >= y0 + h:
            continue
        if any(r.y < y < r.y + r.h for r in rects):
            continue
        bottom = [r for r in rects if r.y + r.h <= y]
        top = [r for r in rects if r.y >= y]
        if _is_guillotine(bottom, x0, y0, w, y - y0) and _is_guillotine(
            top, x0, y, w, y0 + h - y
        ):
            return True

    return False


def _build_instances(
    req: OptimizeRequest, engine: Engine, scale: int, seed: int
) -> Tuple[List[Tuple[int, _RectMeta]], int]:
    spacing = req.params.spacing_mm
    rng = random.Random(seed)
    instances: List[Tuple[int, _RectMeta]] = []
    rect_id = 0

    for item in req.items:
        orientations = _allowed_orientations(
            item.width_mm, item.height_mm, item.rotation, item.pattern_direction
        )
        for idx in range(1, item.qty + 1):
            if len(orientations) == 1:
                w_mm, h_mm, rotated = orientations[0]
            else:
                w_mm, h_mm, rotated = rng.choice(orientations)

            w_eff = w_mm + spacing
            h_eff = h_mm + spacing
            w_eff_int = _mm_to_int(w_eff, scale)
            h_eff_int = _mm_to_int(h_eff, scale)

            rect_id += 1
            meta = _RectMeta(
                item_id=item.id,
                instance=idx,
                width_mm=w_mm,
                height_mm=h_mm,
                rotated=rotated,
                pattern_direction=item.pattern_direction,
                width_eff_int=w_eff_int,
                height_eff_int=h_eff_int,
            )
            instances.append((rect_id, meta))

    rng.shuffle(instances)

    sort_mode = engine.sort or "area_desc"
    if sort_mode != "none":
        if sort_mode == "maxside_desc":
            key_fn = lambda pair: max(pair[1].width_eff_int, pair[1].height_eff_int)
        else:
            key_fn = lambda pair: pair[1].width_eff_int * pair[1].height_eff_int
        instances.sort(key=key_fn, reverse=True)

    return instances, rect_id


def _evaluate_solution(
    bins: List[_BinMeta],
    rects: List[_PackedRect],
    rect_meta: Dict[int, _RectMeta],
    scale: int,
) -> Tuple[int, float, float, Dict[int, List[Placement]], int]:
    placements_by_bin: Dict[int, List[Placement]] = {}
    for rect in rects:
        if rect.rid not in rect_meta:
            continue
        meta = rect_meta[rect.rid]
        bin_meta = bins[rect.bin_index]
        x_mm = _int_to_mm(rect.x_int, scale) + bin_meta.trim_left
        y_mm = _int_to_mm(rect.y_int, scale) + bin_meta.trim_top
        placement = Placement(
            item_id=meta.item_id,
            instance=meta.instance,
            x_mm=x_mm,
            y_mm=y_mm,
            width_mm=meta.width_mm,
            height_mm=meta.height_mm,
            rotated=meta.rotated,
            pattern_direction=meta.pattern_direction,
        )
        placements_by_bin.setdefault(rect.bin_index, []).append(placement)

    used_bins = list(placements_by_bin.keys())
    used_bins_count = len(used_bins)
    used_bins_area = sum(bins[idx].bin_w_mm * bins[idx].bin_h_mm for idx in used_bins)

    item_area = 0.0
    for plist in placements_by_bin.values():
        for plc in plist:
            item_area += plc.width_mm * plc.height_mm

    waste_area = max(0.0, used_bins_area - item_area)
    waste_percent = 0.0
    if used_bins_area > 0:
        waste_percent = waste_area / used_bins_area * 100.0

    placed_count = sum(len(v) for v in placements_by_bin.values())
    return used_bins_count, waste_area, waste_percent, placements_by_bin, placed_count


def optimize(req: OptimizeRequest) -> OptimizeResponse:
    scale = req.params.unit_scale or settings.default_unit_scale
    mode, engine = _resolve_mode_engine(req)

    _validate_request(req, scale)
    bins = _build_bins(req, scale)
    _validate_fit(req, bins, scale)

    start_time = time.monotonic()

    time_limit_ms = req.params.time_limit_ms
    restarts = req.params.restarts
    slice_ms = time_limit_ms // restarts
    if slice_ms < 30:
        restarts_used = max(1, time_limit_ms // 30)
        restarts_used = min(restarts, restarts_used)
    else:
        restarts_used = restarts

    used_seed = req.params.seed or int(time.time() * 1000)

    best: Optional[Tuple[int, float, float, Dict[int, List[Placement]], Dict[int, _RectMeta]]] = None

    for i in range(restarts_used):
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        if elapsed_ms > time_limit_ms:
            raise TimeoutError()

        seed_i = _splitmix64(used_seed + i)
        instances, _ = _build_instances(req, engine, scale, seed_i)

        packer = _new_packer(engine)
        for b in bins:
            packer.add_bin(b.bin_w_int, b.bin_h_int)

        rect_meta: Dict[int, _RectMeta] = {}
        for rid, meta in instances:
            rect_meta[rid] = meta
            packer.add_rect(meta.width_eff_int, meta.height_eff_int, rid=rid)

        packer.pack()
        rects = _extract_rects(packer)

        if len(rects) < len(instances):
            continue

        used_bins_count, waste_area, waste_percent, placements_by_bin, placed_count = _evaluate_solution(
            bins, rects, rect_meta, scale
        )
        if placed_count < len(instances):
            continue

        if mode == "guillotine":
            rects_by_bin: Dict[int, List[_GuillotineRect]] = {}
            for rect in rects:
                rects_by_bin.setdefault(rect.bin_index, []).append(
                    _GuillotineRect(rect.x_int, rect.y_int, rect.w_int, rect.h_int)
                )
            violated = False
            for bin_index, rect_list in rects_by_bin.items():
                bin_meta = bins[bin_index]
                if not _is_guillotine(rect_list, 0, 0, bin_meta.bin_w_int, bin_meta.bin_h_int):
                    violated = True
                    break
            if violated:
                continue

        if best is None:
            best = (used_bins_count, waste_area, waste_percent, placements_by_bin, rect_meta)
        else:
            best_used, best_waste, _, _, _ = best
            if req.params.objective == "min_sheets":
                better = (used_bins_count, waste_area) < (best_used, best_waste)
            else:
                better = (waste_area, used_bins_count) < (best_waste, best_used)
            if better:
                best = (used_bins_count, waste_area, waste_percent, placements_by_bin, rect_meta)

    if best is None:
        raise ConstraintError("Unable to place all items with provided stock")

    used_bins_count, waste_area, waste_percent, placements_by_bin, _ = best

    solutions: List[Solution] = []
    for bin_index, placements in placements_by_bin.items():
        bin_meta = bins[bin_index]
        solutions.append(
            Solution(
                stock_id=bin_meta.stock_id,
                index=bin_meta.index,
                width_mm=bin_meta.width_mm,
                height_mm=bin_meta.height_mm,
                trim_mm=req.params.trim_mm,
                placements=placements,
            )
        )

    svg = render_svg(solutions)
    time_ms = int((time.monotonic() - start_time) * 1000)

    summary = Summary(
        mode=mode,
        objective=req.params.objective,
        used_stock_count=used_bins_count,
        total_waste_area_mm2=waste_area,
        waste_percent=waste_percent,
        time_ms=time_ms,
        restarts_used=restarts_used,
        seed=used_seed,
        engine=EngineSummary(
            packer=engine.packer or "guillotine",
            bin_select=engine.bin_select or "best_fit",
            sort=engine.sort or "area_desc",
        ),
    )

    return OptimizeResponse(
        status="ok",
        summary=summary,
        solutions=solutions,
        artifacts=Artifacts(svg=svg),
    )
