"""
Kerala Vehicle Number Plate OCR
================================
Groq Vision API (primary) + EasyOCR (fallback).

Architecture
------------
1. **Groq Vision (primary)** — sends the image to Llama-4-Scout via Groq
   with a structured prompt. The vision model reads the plate directly
   from the photograph and returns text like "KL-63-F-3227".

2. **EasyOCR (fallback)** — only runs when Groq is unavailable or returns
   no valid Kerala plate. Uses contour-based plate detection → upscale →
   multi-variant preprocessing → OCR → Kerala format correction.

Kerala plate format:  KL  DD  X{1,2}  NNNN
  KL   – state code
  DD   – district code  01-15, 41, 55, 63
  X(X) – series: 1 or 2 uppercase letters
  NNNN – registration: 1-4 digits (usually 4; 3-digit plates exist)
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

# ── Optional dependency guards ──────────────────────────────────────────────
try:
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ── Constants ───────────────────────────────────────────────────────────────

PLATE_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

KERALA_DISTRICTS: Dict[str, str] = {
    "01": "Thiruvananthapuram", "02": "Kollam",       "03": "Pathanamthitta",
    "04": "Alappuzha",         "05": "Kottayam",      "06": "Idukki",
    "07": "Ernakulam",         "08": "Thrissur",      "09": "Palakkad",
    "10": "Malappuram",        "11": "Kozhikode",     "12": "Wayanad",
    "13": "Kannur",            "14": "Kasaragod",     "15": "Kochi",
    "41": "Ernakulam (old)",   "55": "Kottayam (old)","63": "Pathanamthitta (old)",
}

# OCR misread maps (used by EasyOCR fallback)
LETTER_TO_DIGIT: Dict[str, str] = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1",
    "Z": "2", "E": "3", "A": "4",
    "S": "5", "G": "6", "T": "7", "B": "8",
}
DIGIT_TO_LETTER: Dict[str, str] = {v: k for k, v in LETTER_TO_DIGIT.items()}
DIGIT_TO_LETTER.update({"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G"})

SIMILAR_DIGITS: Dict[str, List[str]] = {
    "0": ["8"],   "8": ["0"],
    "1": ["7"],   "7": ["1"],
    "4": ["5"],   "5": ["4"],
    "3": ["8"],   "6": ["0"],
}

MIN_RAW_CONF = 0.25

# Kerala plate regex (compact form): KL + 2 digits + 1-2 letters + 1-4 digits
KERALA_PLATE_RE = re.compile(r"^KL(\d{2})([A-Z]{1,2})(\d{1,4})$")


# ═══════════════════════════════════════════════════════════════════════════
#  GROQ VISION (PRIMARY)
# ═══════════════════════════════════════════════════════════════════════════

_groq_ocr_client = None


def _init_groq_ocr() -> bool:
    """Initialize a Groq client for OCR. Returns True on success."""
    global _groq_ocr_client

    if _groq_ocr_client is not None:
        return True
    if not GROQ_AVAILABLE:
        return False

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("GROQ_API_KEY", "").strip()
        except ImportError:
            pass

    if not api_key:
        print("[OCR] No GROQ_API_KEY found — Groq OCR disabled, using EasyOCR fallback")
        return False

    try:
        _groq_ocr_client = Groq(api_key=api_key)
        print("[OCR] Groq Vision configured (llama-4-scout)")
        return True
    except Exception as exc:
        print(f"[OCR] Groq init failed: {exc}")
        return False


def _encode_image_for_groq(image_path: str) -> Optional[str]:
    """Encode image to base64 JPEG for Groq Vision API."""
    try:
        from PIL import Image

        img = Image.open(image_path)

        # Convert to RGB
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg

        # Resize to max 1920x1080 for API efficiency
        max_size = (1920, 1080)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90, optimize=True)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    except Exception as exc:
        print(f"[OCR] Image encode failed: {exc}")
        return None


def _normalize_plate(text: str) -> str:
    """Strip everything except A-Z and 0-9, uppercase."""
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def _validate_kerala_plate(compact: str) -> bool:
    """Check if compact text matches KLddX(X)nnnn format."""
    return bool(KERALA_PLATE_RE.match(compact))


def _groq_extract_plate(image_path: str, debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    Use Groq Vision (Llama-4-Scout) to read the number plate from an image.

    Returns a result dict (same shape as extract_number_plate) or None on failure.
    """
    if not _init_groq_ocr():
        return None

    try:
        base64_image = _encode_image_for_groq(image_path)
        if not base64_image:
            return None

        prompt = (
            "You are an expert Indian vehicle number plate reader. "
            "Look at this image and find the vehicle registration number plate. "
            "The plate is from Kerala, India. Kerala plates follow the format: "
            "KL DD X(X) NNNN where KL=state, DD=district digits, X=1-2 series letters, NNNN=1-4 registration digits. "
            "Examples: KL 63 F 3227, KL 07 CU 7475, KL 63 C 599. "
            "\n\nReturn ONLY the plate text in the format KL-DD-XX-NNNN (with hyphens). "
            "If you cannot find a plate, return exactly: NO_PLATE_FOUND"
        )

        if debug:
            print("[GROQ] Sending image to Groq Vision API...")

        response = _groq_ocr_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }],
            temperature=0.0,
            max_tokens=50,
        )

        raw_response = response.choices[0].message.content.strip()

        if debug:
            print(f"[GROQ] Raw response: '{raw_response}'")

        if "NO_PLATE_FOUND" in raw_response.upper():
            if debug:
                print("[GROQ] No plate found")
            return None

        # Normalize the response
        compact = _normalize_plate(raw_response)

        if debug:
            print(f"[GROQ] Normalized: '{compact}'")

        # Validate as Kerala plate
        if _validate_kerala_plate(compact):
            formatted = format_kerala_plate(compact)
            m = KERALA_PLATE_RE.match(compact)
            district_code = m.group(1) if m else None
            district_name = KERALA_DISTRICTS.get(district_code) if district_code else None

            if debug:
                print(f"[GROQ] ✓ Valid Kerala plate: {formatted}")

            return {
                "plate_text": formatted,
                "confidence": 0.95,
                "district_name": district_name,
                "raw_texts": [raw_response],
                "source": "groq",
            }
        else:
            if debug:
                print(f"[GROQ] Response '{compact}' doesn't match Kerala format, trying EasyOCR...")
            return None

    except Exception as exc:
        if debug:
            print(f"[GROQ] Error: {exc}")
            traceback.print_exc()
        else:
            print(f"[OCR] Groq Vision failed: {exc}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  EASYOCR FALLBACK
# ═══════════════════════════════════════════════════════════════════════════

_ocr_reader: Optional[Any] = None


def _get_ocr_reader():
    """Lazy-initialize EasyOCR reader singleton."""
    global _ocr_reader
    if _ocr_reader is None:
        if not OCR_AVAILABLE:
            raise RuntimeError("easyocr is not installed.  Run: pip install easyocr")

        use_gpu = False
        try:
            import torch
            if torch.cuda.is_available():
                use_gpu = True
                print(f"[OCR] CUDA available – device: {torch.cuda.get_device_name(0)}")
            else:
                print("[OCR] CUDA not available – running EasyOCR on CPU")
        except ImportError:
            print("[OCR] PyTorch not found – running EasyOCR on CPU")

        print("Initialising EasyOCR (may download model on first run)…")
        _ocr_reader = easyocr.Reader(["en"], gpu=use_gpu)
        print(f"[OK] EasyOCR ready  (gpu={use_gpu})")
    return _ocr_reader


# ── Image helpers ────────────────────────────────────────────────────────────

def _detect_plate_region(img) -> Optional[Any]:
    """Locate number-plate rectangle using contour analysis."""
    h, w = img.shape[:2]

    scale = min(1.0, 1200 / max(h, w))
    small = cv2.resize(img, None, fx=scale, fy=scale) if scale < 1.0 else img.copy()
    sh, sw = small.shape[:2]

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(blur, 20, 150)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
    edges = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:100]

    best_box = None
    best_score = 0.0

    min_area = sh * sw * 0.0003
    max_area = sh * sw * 0.50

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue

        rx, ry, rw, rh = cv2.boundingRect(cnt)
        if rh == 0:
            continue

        ar = rw / rh
        if ar < 1.8 or ar > 7.5:
            continue

        extent = area / (rw * rh)
        if extent < 0.35:
            continue

        centre_y = (ry + rh / 2) / sh
        ar_score = max(0.0, 1.0 - abs(ar - 4.0) / 4.0)
        rect_score = min(1.0, extent)
        size_score = min(1.0, rw / (sw * 0.20))

        score = (centre_y * 0.40 + ar_score * 0.35 +
                 rect_score * 0.10 + size_score * 0.15)

        if score > best_score:
            best_score = score
            best_box = (rx, ry, rw, rh)

    if best_box is None:
        return None

    rx, ry, rw, rh = best_box
    inv = 1.0 / scale
    rx2, ry2, rw2, rh2 = int(rx * inv), int(ry * inv), int(rw * inv), int(rh * inv)

    if rw2 < 150 or rh2 < 30:
        return None

    pad_x = max(10, int(rw2 * 0.10))
    pad_y = max(6, int(rh2 * 0.20))
    x1 = max(0, rx2 - pad_x)
    y1 = max(0, ry2 - pad_y)
    x2 = min(w, rx2 + rw2 + pad_x)
    y2 = min(h, ry2 + rh2 + pad_y)

    crop = img[y1:y2, x1:x2]
    ch, cw = crop.shape[:2]
    if ch < 30 or cw < 150 or cw / max(ch, 1) < 1.5:
        return None

    return crop


def _get_candidate_regions(img) -> List[Tuple[str, Any]]:
    """Return (name, crop) pairs to attempt OCR on."""
    regions = []
    h, w = img.shape[:2]

    detected = _detect_plate_region(img)
    if detected is not None and detected.size > 0:
        regions.append(("detected", detected))

    regions.append(("bottom_third", img[int(h * 0.67):, :]))
    regions.append(("bottom_half", img[int(h * 0.50):, :]))
    regions.append(("full", img))
    return regions


def _upscale_plate(crop, target_height: int = 160):
    """Upscale plate crop for better OCR. Uses LANCZOS4."""
    h, w = crop.shape[:2]
    if h >= target_height:
        return crop
    scale = target_height / h
    new_w = int(w * scale)
    return cv2.resize(crop, (new_w, target_height), interpolation=cv2.INTER_LANCZOS4)


def _unsharp_mask(gray, radius: int = 3, amount: float = 1.5):
    """Controlled unsharp mask."""
    blurred = cv2.GaussianBlur(gray, (2 * radius + 1, 2 * radius + 1), 0)
    sharpened = cv2.addWeighted(gray, 1.0 + amount, blurred, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def _preprocess_variants(crop) -> List[Tuple[str, Any]]:
    """Produce preprocessed versions of a plate crop for multi-pass OCR."""
    variants = []
    crop = _upscale_plate(crop)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

    # Blur-adaptive extra upscale
    blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_var < 80:
        h, w = gray.shape[:2]
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
        gray = _unsharp_mask(gray, radius=2, amount=1.2)

    variants.append(("clahe", clahe.apply(gray)))

    nlm = cv2.fastNlMeansDenoising(gray, h=7, templateWindowSize=7, searchWindowSize=21)
    variants.append(("nlm_clahe", clahe.apply(nlm)))

    denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    variants.append(("bilateral_clahe", clahe.apply(denoised)))

    sharp = _unsharp_mask(gray, radius=3, amount=1.5)
    variants.append(("unsharp_clahe", clahe.apply(sharp)))

    ada = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8
    )
    variants.append(("adaptive_thresh", ada))

    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("otsu", otsu))
    variants.append(("otsu_inv", cv2.bitwise_not(otsu)))

    return variants


def _run_easyocr(img_bytes: bytes, debug: bool = False) -> List[Tuple[str, float]]:
    """Run EasyOCR on PNG bytes. Returns (text, confidence) pairs."""
    reader = _get_ocr_reader()
    try:
        detections = reader.readtext(
            img_bytes, allowlist=PLATE_ALLOWLIST, detail=1, paragraph=False,
        )
    except Exception as exc:
        if debug:
            print(f"  [EasyOCR error] {exc}")
        return []

    results = []
    for det in detections:
        text = det[1] if len(det) > 1 else ""
        conf = float(det[2]) if len(det) > 2 else 0.0
        clean = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        if clean and conf >= MIN_RAW_CONF:
            results.append((clean, conf))
    return results


# ── Kerala plate correction (EasyOCR fallback) ──────────────────────────────

def _fix_state_code(ch0: str, ch1: str) -> Optional[Tuple[str, int]]:
    """Attempt to parse first two chars as 'KL'."""
    K_OK = {"K"}
    K_NEAR = {"1", "I", "L"}
    L_OK = {"L"}
    L_NEAR = {"1", "I", "J"}

    c0, c1 = ch0.upper(), ch1.upper()
    k_cost = 0 if c0 in K_OK else (1 if c0 in K_NEAR else 99)
    l_cost = 0 if c1 in L_OK else (1 if c1 in L_NEAR else 99)

    if k_cost + l_cost > 2:
        return None
    return ("KL", k_cost + l_cost)


def _parse_district(ch0: str, ch1: str) -> Optional[Tuple[str, int]]:
    """Parse two chars as a 2-digit district code."""
    def to_digit(c):
        c = c.upper()
        if c.isdigit():
            return c, 0
        if c in LETTER_TO_DIGIT:
            return LETTER_TO_DIGIT[c], 1
        return None

    r0, r1 = to_digit(ch0), to_digit(ch1)
    if r0 is None or r1 is None:
        return None
    return r0[0] + r1[0], r0[1] + r1[1]


def _parse_series_and_number(rest: str) -> List[Tuple[str, str, int]]:
    """Split characters after district into (series, number, cost)."""
    HIGHLY_DIGIT_LIKE = {"E", "S", "Z", "O", "Q"}
    results = []

    for series_len in (1, 2):
        if series_len >= len(rest):
            continue

        raw_series = rest[:series_len]
        raw_number = rest[series_len:]
        if len(raw_number) < 1 or len(raw_number) > 5:
            continue

        series, s_cost, ok = "", 0, True
        for c in raw_series:
            if c.isalpha():
                series += c
            elif c in DIGIT_TO_LETTER:
                series += DIGIT_TO_LETTER[c]
                s_cost += 1
            else:
                ok = False
                break
        if not ok or not series:
            continue

        series_suspect = 3 if (series_len == 2 and series[1] in HIGHLY_DIGIT_LIKE) else 0

        number, n_cost = "", 0
        for c in raw_number:
            if c.isdigit():
                number += c
            elif c in LETTER_TO_DIGIT:
                number += LETTER_TO_DIGIT[c]
                n_cost += 1
            else:
                ok = False
                break
        if not ok or not number:
            continue

        trunc_penalty = 0
        if len(number) > 4:
            first_from_letter = (raw_number[0] not in "0123456789")
            if first_from_letter and len(number) == 5:
                results.append((series, number[1:],
                                s_cost + n_cost * 2 + series_suspect + 1))
                number = number[:4]
                trunc_penalty = 4
            else:
                number = number[:4]
                trunc_penalty = 4

        total = s_cost + n_cost * 2 + series_suspect + trunc_penalty
        results.append((series, number, total))

    # Generate 1-letter alternatives from suspicious 2-letter series
    extra = []
    for series, number, cost in results:
        if len(series) == 2 and series[1] in LETTER_TO_DIGIT and len(number) == 4:
            alt_series = series[0]
            alt_digit = LETTER_TO_DIGIT[series[1]]
            if alt_digit == number[0]:
                alt_number = alt_digit + number[1:]
            else:
                alt_number = alt_digit + number[:3]
            extra.append((alt_series, alt_number, max(0, cost - 2)))
    results += extra

    results.sort(key=lambda x: x[2])
    return results


def _correct_kerala_plate(raw: str) -> List[Tuple[str, int]]:
    """Return ranked (plate_compact, corrections) from raw OCR text."""
    text = _normalize_plate(raw)
    if len(text) < 6 or len(text) > 13:
        return []

    candidates = []
    for skip in range(min(4, len(text) - 5)):
        chunk = text[skip:]
        if len(chunk) < 6:
            break

        state_r = _fix_state_code(chunk[0], chunk[1])
        if state_r is None:
            continue
        state, state_cost = state_r

        if len(chunk) < 4:
            continue
        dist_r = _parse_district(chunk[2], chunk[3])
        if dist_r is None:
            continue
        district, dist_cost = dist_r

        rest = chunk[4:]
        if not rest:
            continue

        for series, number, sn_cost in _parse_series_and_number(rest):
            total = state_cost + dist_cost + sn_cost + skip * 2
            plate = f"{state}{district}{series}{number}"
            if 6 <= len(plate) <= 10:
                candidates.append((plate, total))

    best: Dict[str, int] = {}
    for plate, cost in candidates:
        if plate not in best or cost < best[plate]:
            best[plate] = cost

    return sorted(best.items(), key=lambda x: x[1])


def _generate_digit_swaps(plate: str) -> List[Tuple[str, int]]:
    """Swap visually similar digits in number section."""
    m = KERALA_PLATE_RE.match(plate)
    if not m:
        return []

    prefix = "KL" + m.group(1) + m.group(2)
    number = m.group(3)
    alts = []
    for i, ch in enumerate(number):
        if ch in SIMILAR_DIGITS:
            for alt_ch in SIMILAR_DIGITS[ch]:
                alt_number = number[:i] + alt_ch + number[i + 1:]
                alts.append((prefix + alt_number, 1))
    return alts


def _score_candidate(plate: str, correction_cost: int, raw_conf: float) -> float:
    """Score a plate candidate. Higher = more likely correct."""
    m = KERALA_PLATE_RE.match(plate)
    if not m:
        return 0.0

    district = m.group(1)
    number = m.group(3)

    district_bonus = 0.25 if district in KERALA_DISTRICTS else 0.0
    number_bonus = 0.15 if len(number) == 4 else (0.05 if len(number) == 3 else 0.0)
    correction_penalty = 0.12 * correction_cost

    score = raw_conf + district_bonus + number_bonus - correction_penalty
    return round(max(0.0, min(score, 1.0)), 4)


def _easyocr_extract_plate(image_path: str, debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    Full EasyOCR pipeline: region detection → preprocessing → OCR → correction.
    Returns result dict or None.
    """
    if not CV2_AVAILABLE:
        print("[ERROR] OpenCV not installed for EasyOCR fallback")
        return None

    img = cv2.imread(image_path)
    if img is None:
        return None

    if debug:
        h, w = img.shape[:2]
        print(f"\n[EasyOCR] Processing {os.path.basename(image_path)}  {w}×{h}")

    regions = _get_candidate_regions(img)

    raw_detections: List[Tuple[str, float, str]] = []
    for region_name, crop in regions:
        if crop is None or crop.size == 0:
            continue

        for variant_name, processed in _preprocess_variants(crop):
            src = f"{region_name}/{variant_name}"
            _, buf = cv2.imencode(".png", processed)
            img_bytes = buf.tobytes()
            ocr_hits = _run_easyocr(img_bytes, debug=debug)

            if debug and ocr_hits:
                print(f"  [OCR] {src}")
                for t, c in ocr_hits:
                    print(f"    '{t}'  conf={c:.3f}")

            for text, conf in ocr_hits:
                raw_detections.append((text, conf, src))

    if not raw_detections:
        if debug:
            print("[EasyOCR] No text detected")
        return None

    # Merge adjacent detections from same source
    from collections import defaultdict
    by_source: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for text, conf, src in raw_detections:
        by_source[src].append((text, conf))

    merged_extra = []
    for src, hits in by_source.items():
        for i in range(len(hits) - 1):
            t1, c1 = hits[i]
            t2, c2 = hits[i + 1]
            merged = t1 + t2
            if len(merged) >= 6:
                merged_extra.append((merged, (c1 + c2) / 2, f"merge/{src}"))

    all_detections = raw_detections + merged_extra

    SKIP_WORDS = {"KIA", "IND", "INDIA", "INDI", "HYUNDAI", "TOYOTA", "HONDA",
                  "SUZUKI", "MARUTI", "NISSAN", "FORD", "TATA", "MAHINDRA"}

    scored: List[Tuple[str, float, str, str]] = []
    for raw_text, raw_conf, source in all_detections:
        if raw_text in SKIP_WORDS or len(raw_text) < 6:
            continue
        if not any(c.isalpha() for c in raw_text) or not any(c.isdigit() for c in raw_text):
            continue

        for plate, cost in _correct_kerala_plate(raw_text):
            s = _score_candidate(plate, cost, raw_conf)
            if s > 0.0:
                scored.append((plate, s, source, raw_text))
                for alt_plate, swap_cost in _generate_digit_swaps(plate):
                    alt_s = _score_candidate(alt_plate, cost + swap_cost, raw_conf)
                    if alt_s > 0.0:
                        scored.append((alt_plate, alt_s, f"swap/{source}", raw_text))

    if not scored:
        if debug:
            print("[EasyOCR] No valid Kerala plate found")
        return None

    best_per_plate: Dict[str, Tuple[float, str, str]] = {}
    for plate, score, source, raw in scored:
        if plate not in best_per_plate or score > best_per_plate[plate][0]:
            best_per_plate[plate] = (score, source, raw)

    ranked = sorted(best_per_plate.items(), key=lambda x: x[1][0], reverse=True)

    if debug:
        print("\n[EasyOCR CANDIDATES] (top 10)")
        for p, (s, src, raw) in ranked[:10]:
            print(f"  {format_kerala_plate(p):18s}  score={s:.4f}  raw='{raw}'  src={src}")

    best_plate, (best_score, best_source, best_raw) = ranked[0]
    m = KERALA_PLATE_RE.match(best_plate)
    district_name = KERALA_DISTRICTS.get(m.group(1)) if m else None

    return {
        "plate_text": format_kerala_plate(best_plate),
        "confidence": best_score,
        "district_name": district_name,
        "raw_texts": sorted({t for t, _, _ in raw_detections}),
        "source": "easyocr",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def format_kerala_plate(plate: str) -> str:
    """Format compact plate as KL-DD-XX-NNNN."""
    m = KERALA_PLATE_RE.match(plate)
    if m:
        return f"KL-{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return plate


def extract_number_plate(image_path: str, debug: bool = False) -> Dict[str, Any]:
    
    result: Dict[str, Any] = {
        "plate_text": None,
        "confidence": None,
        "district_name": None,
        "raw_texts": [],
    }

    if not os.path.exists(image_path):
        print(f"[ERROR] File not found: {image_path}")
        return result

    # ── 1. Try Groq Vision (primary) ─────────────────────────────────────
    if debug:
        print(f"\n{'='*55}")
        print(f"[OCR] Processing: {os.path.basename(image_path)}")
        print(f"{'='*55}")

    groq_result = _groq_extract_plate(image_path, debug=debug)

    if groq_result is not None:
        if debug:
            print(f"[OCR] ✓ Groq returned: {groq_result['plate_text']} "
                  f"(confidence={groq_result['confidence']})")
        return groq_result

    # ── 2. Fall back to EasyOCR ──────────────────────────────────────────
    if debug:
        print("[OCR] Groq unavailable or returned no valid plate — trying EasyOCR...")

    easyocr_result = _easyocr_extract_plate(image_path, debug=debug)

    if easyocr_result is not None:
        if debug:
            print(f"[OCR] ✓ EasyOCR returned: {easyocr_result['plate_text']} "
                  f"(confidence={easyocr_result['confidence']})")
        return easyocr_result

    if debug:
        print("[OCR] ✗ No plate detected by either method")

    return result


def extract_plates_batch(
    image_paths: List[str], debug: bool = False
) -> List[Dict[str, Any]]:
    """Convenience wrapper to process a list of images."""
    return [extract_number_plate(p, debug=debug) for p in image_paths]


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ocr_service.py <image> [<image2> …] [--debug]")
        sys.exit(1)

    # Load .env for CLI usage
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    debug_flag = "--debug" in sys.argv
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]

    for path in paths:
        res = extract_number_plate(path, debug=debug_flag)
        print("\n" + "=" * 55)
        print(f"Image    : {path}")
        print(f"Plate    : {res['plate_text']}")
        print(f"Conf     : {res['confidence']}")
        print(f"District : {res['district_name']}")
        print(f"Source   : {res.get('source', 'none')}")
        if debug_flag:
            print(f"Raw OCR  : {res['raw_texts']}")