from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class ColorEngineConfig:
    minimum_turf_coverage: float = 0.08
    affected_z_threshold: float = 1.15
    minimum_region_pixels: int = 250
    lower_image_weight_start: float = 0.35


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return float(max(minimum, min(maximum, value)))


def _decode_image(image_bytes: bytes) -> np.ndarray:
    if not image_bytes:
        raise ValueError("Bilden är tom.")

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Bilden kunde inte läsas.")

    return image


def _resize_for_analysis(image: np.ndarray, max_width: int = 1400) -> np.ndarray:
    height, width = image.shape[:2]

    if width <= max_width:
        return image

    scale = max_width / width
    new_size = (max_width, max(1, int(height * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def _build_turf_mask(image_bgr: np.ndarray, config: ColorEngineConfig) -> np.ndarray:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)

    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    a_channel = lab[:, :, 1]
    b_channel = lab[:, :, 2]

    hsv_green = (
        (hue >= 25)
        & (hue <= 95)
        & (saturation >= 25)
        & (value >= 30)
    )

    lab_green = (
        (a_channel <= 132)
        & (b_channel >= 118)
        & (value >= 30)
    )

    mask = (hsv_green & lab_green).astype(np.uint8) * 255

    height, _ = mask.shape
    y_start = int(height * config.lower_image_weight_start)

    strong_green = (
        (hue >= 30)
        & (hue <= 88)
        & (saturation >= 45)
        & (a_channel <= 126)
    ).astype(np.uint8) * 255

    mask[:y_start] = cv2.bitwise_and(mask[:y_start], strong_green[:y_start])

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cleaned = np.zeros_like(mask)

    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= config.minimum_region_pixels:
            cleaned[labels == label] = 255

    return cleaned


def _robust_z_scores(values: np.ndarray) -> np.ndarray:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))

    if mad < 1e-6:
        return np.zeros_like(values, dtype=np.float32)

    return (0.6745 * (values - median) / mad).astype(np.float32)


def _texture_score(gray: np.ndarray, turf_mask: np.ndarray) -> float:
    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    local_variation = np.abs(laplacian)[turf_mask > 0]

    if local_variation.size == 0:
        return 0.0

    variation = float(np.percentile(local_variation, 75))
    ideal = 18.0
    distance = abs(variation - ideal)
    return _clamp(100.0 - distance * 2.4)


def _connected_affected_regions(
    affected_mask: np.ndarray,
    minimum_region_pixels: int,
) -> list[dict[str, Any]]:
    count, _, stats, centroids = cv2.connectedComponentsWithStats(
        affected_mask.astype(np.uint8),
        8,
    )

    regions: list[dict[str, Any]] = []

    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])

        if area < minimum_region_pixels:
            continue

        regions.append(
            {
                "areaPixels": area,
                "boundingBox": {
                    "x": int(stats[label, cv2.CC_STAT_LEFT]),
                    "y": int(stats[label, cv2.CC_STAT_TOP]),
                    "width": int(stats[label, cv2.CC_STAT_WIDTH]),
                    "height": int(stats[label, cv2.CC_STAT_HEIGHT]),
                },
                "center": {
                    "x": round(float(centroids[label][0]), 1),
                    "y": round(float(centroids[label][1]), 1),
                },
            }
        )

    regions.sort(key=lambda item: item["areaPixels"], reverse=True)
    return regions[:8]


def analyze_color_uniformity(
    image_bytes: bytes,
    config: ColorEngineConfig | None = None,
) -> dict[str, Any]:
    settings = config or ColorEngineConfig()

    image = _resize_for_analysis(_decode_image(image_bytes))
    height, width = image.shape[:2]

    turf_mask = _build_turf_mask(image, settings)
    turf_pixels = turf_mask > 0
    turf_pixel_count = int(np.count_nonzero(turf_pixels))
    total_pixels = int(height * width)
    turf_coverage = turf_pixel_count / max(total_pixels, 1)

    if turf_coverage < settings.minimum_turf_coverage:
        return {
            "status": "insufficient_turf",
            "message": (
                "För liten säker gräsyta identifierades. "
                "Ta en närmare bild eller markera greenytan."
            ),
            "imageWidth": width,
            "imageHeight": height,
            "turfCoveragePercent": round(turf_coverage * 100, 1),
        }

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    lightness = lab[:, :, 0].astype(np.float32)
    green_red = lab[:, :, 1].astype(np.float32)
    yellow_blue = lab[:, :, 2].astype(np.float32)
    saturation = hsv[:, :, 1].astype(np.float32)

    l_values = lightness[turf_pixels]
    a_values = green_red[turf_pixels]
    b_values = yellow_blue[turf_pixels]
    s_values = saturation[turf_pixels]

    l_z = _robust_z_scores(l_values)
    a_z = _robust_z_scores(a_values)
    b_z = _robust_z_scores(b_values)

    combined_deviation = np.sqrt(
        (l_z * 0.45) ** 2
        + (a_z * 0.40) ** 2
        + (b_z * 0.35) ** 2
    )

    affected_values = combined_deviation >= settings.affected_z_threshold
    affected_area_percent = float(np.mean(affected_values) * 100.0)

    deviation_map = np.zeros((height, width), dtype=np.float32)
    deviation_map[turf_pixels] = combined_deviation

    affected_mask = (
        (deviation_map >= settings.affected_z_threshold)
        & turf_pixels
    )

    affected_mask_uint8 = affected_mask.astype(np.uint8) * 255
    affected_mask_uint8 = cv2.morphologyEx(
        affected_mask_uint8,
        cv2.MORPH_CLOSE,
        np.ones((9, 9), np.uint8),
    )
    affected_mask_uint8 = cv2.morphologyEx(
        affected_mask_uint8,
        cv2.MORPH_OPEN,
        np.ones((5, 5), np.uint8),
    )

    regions = _connected_affected_regions(
        affected_mask_uint8,
        settings.minimum_region_pixels,
    )

    lab_spread = (
        float(np.std(l_values)) * 0.45
        + float(np.std(a_values)) * 0.35
        + float(np.std(b_values)) * 0.20
    )

    color_uniformity = _clamp(
        100.0
        - lab_spread * 2.25
        - affected_area_percent * 0.55
    )

    color_intensity = _clamp(
        55.0
        + (128.0 - float(np.median(a_values))) * 2.2
        + (float(np.median(s_values)) - 70.0) * 0.18
    )

    stress_index = _clamp(
        affected_area_percent * 1.35
        + max(0.0, 75.0 - color_uniformity) * 0.75
    )

    texture = _texture_score(gray, turf_mask)

    visual_quality_score = _clamp(
        color_uniformity * 0.45
        + color_intensity * 0.20
        + texture * 0.20
        + (100.0 - stress_index) * 0.15
    )

    if color_uniformity < 70 or affected_area_percent >= 18:
        variation_level = "hög"
    elif color_uniformity < 84 or affected_area_percent >= 9:
        variation_level = "måttlig"
    else:
        variation_level = "låg"

    observations: list[str] = []

    if affected_area_percent >= 18:
        observations.append(
            "En stor andel av gräsytan avviker tydligt i färg."
        )
    elif affected_area_percent >= 9:
        observations.append(
            "Ett mätbart sammanhängande område avviker i färg."
        )

    if color_uniformity < 75:
        observations.append(
            "Färgjämnheten är för låg för en jämnt presenterad green."
        )

    if color_intensity < 65:
        observations.append(
            "Gräsfärgens intensitet är låg och bör följas upp."
        )

    if not observations:
        observations.append(
            "Ingen större färgavvikelse identifierades i den säkra gräsytan."
        )

    return {
        "status": "ok",
        "engineVersion": "color-uniformity-v1",
        "imageWidth": width,
        "imageHeight": height,
        "turfCoveragePercent": round(turf_coverage * 100, 1),
        "colorUniformityScore": round(color_uniformity, 1),
        "colorIntensityScore": round(color_intensity, 1),
        "stressIndex": round(stress_index, 1),
        "affectedAreaPercent": round(affected_area_percent, 1),
        "textureScore": round(texture, 1),
        "visualQualityScore": round(visual_quality_score, 1),
        "variationLevel": variation_level,
        "affectedRegions": regions,
        "observations": observations,
        "measurementNotes": [
            "Poängen bygger på mätbar variation i Lab- och HSV-färgrymd.",
            "Resultatet är inte en sjukdomsdiagnos.",
            "Exakt greenpolygon och referensbilder kommer förbättra träffsäkerheten.",
        ],
    }


def create_color_heatmap(image_bytes: bytes) -> bytes:
    settings = ColorEngineConfig()
    image = _resize_for_analysis(_decode_image(image_bytes))
    turf_mask = _build_turf_mask(image, settings)
    turf_pixels = turf_mask > 0

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness = lab[:, :, 0].astype(np.float32)
    green_red = lab[:, :, 1].astype(np.float32)
    yellow_blue = lab[:, :, 2].astype(np.float32)

    l_z = _robust_z_scores(lightness[turf_pixels])
    a_z = _robust_z_scores(green_red[turf_pixels])
    b_z = _robust_z_scores(yellow_blue[turf_pixels])

    combined = np.sqrt(
        (l_z * 0.45) ** 2
        + (a_z * 0.40) ** 2
        + (b_z * 0.35) ** 2
    )

    deviation = np.zeros(turf_mask.shape, dtype=np.float32)
    deviation[turf_pixels] = combined

    normalized = np.clip(deviation / 2.8, 0.0, 1.0)
    heat = (normalized * 255).astype(np.uint8)
    heat = cv2.applyColorMap(heat, cv2.COLORMAP_JET)

    overlay = image.copy()
    overlay[turf_pixels] = cv2.addWeighted(
        image[turf_pixels],
        0.48,
        heat[turf_pixels],
        0.52,
        0,
    )

    success, encoded = cv2.imencode(
        ".jpg",
        overlay,
        [cv2.IMWRITE_JPEG_QUALITY, 90],
    )

    if not success:
        raise RuntimeError("Kunde inte skapa heatmap-bilden.")

    return encoded.tobytes()
