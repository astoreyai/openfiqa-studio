"""Degradation operators (P05 I09–I13).

Every operator is a real image operation. There is no "simulated" degradation: JPEG compression
runs a JPEG encoder, blur convolves, noise adds sampled values to pixels.

**One implementation, two callers.** The P05 gate requires interactive preview and batch execution
to agree for deterministic settings. That is guaranteed structurally rather than by testing two
code paths into alignment — `apply()` is the only place a transform happens, and preview and batch
both call it. A preview that approximated the real transform would teach the researcher something
false about their own experiment.

Stochastic operators take an explicit seed and record it, so "deterministic" is a property of the
recorded parameters rather than a hope.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# ---------------------------------------------------------------------------- operators


def _jpeg(image: Image.Image, *, quality: int) -> Image.Image:
    """Re-encode as JPEG at the given quality. Round-trips through a real encoder."""
    if not 1 <= quality <= 100:
        raise ValueError("jpeg quality must be in 1..100")
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def _resize(image: Image.Image, *, scale: float, resample: str = "bicubic") -> Image.Image:
    """Downsample then restore the original size, so the loss is resolution, not dimensions.

    Keeping the output size fixed is what makes a resolution sweep comparable: a quality engine
    that also reacts to raw pixel dimensions would otherwise confound the two effects.
    """
    if not 0 < scale <= 1:
        raise ValueError("scale must be in (0, 1]")
    filters = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }
    if resample not in filters:
        raise ValueError(f"unknown resample filter: {resample}")
    width, height = image.size
    small = image.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))), filters[resample]
    )
    return small.resize((width, height), filters[resample])


def _gaussian_blur(image: Image.Image, *, radius: float) -> Image.Image:
    if radius < 0:
        raise ValueError("radius must be >= 0")
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def _motion_blur(image: Image.Image, *, length: int, horizontal: bool = True) -> Image.Image:
    if length < 1:
        raise ValueError("length must be >= 1")
    kernel = [0.0] * (length * length)
    for i in range(length):
        index = (length // 2) * length + i if horizontal else i * length + (length // 2)
        kernel[index] = 1.0 / length
    return image.filter(ImageFilter.Kernel((length, length), kernel, scale=1.0))


def _gaussian_noise(image: Image.Image, *, sigma: float, seed: int) -> Image.Image:
    """Additive Gaussian noise. Stochastic, so the seed is required, not optional."""
    if sigma < 0:
        raise ValueError("sigma must be >= 0")
    rng = np.random.default_rng(seed)
    array = np.asarray(image.convert("RGB"), dtype=np.float64)
    noisy = array + rng.normal(0.0, sigma, array.shape)
    return Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8), mode="RGB")


def _brightness(image: Image.Image, *, factor: float) -> Image.Image:
    return ImageEnhance.Brightness(image.convert("RGB")).enhance(factor)


def _contrast(image: Image.Image, *, factor: float) -> Image.Image:
    return ImageEnhance.Contrast(image.convert("RGB")).enhance(factor)


def _gamma(image: Image.Image, *, gamma: float) -> Image.Image:
    if gamma <= 0:
        raise ValueError("gamma must be > 0")
    array = np.asarray(image.convert("RGB"), dtype=np.float64) / 255.0
    return Image.fromarray((np.power(array, gamma) * 255).astype(np.uint8), mode="RGB")


def _grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L").convert("RGB")


def _crop(image: Image.Image, *, fraction: float) -> Image.Image:
    """Centre-crop by a fraction of each edge, then restore the original size."""
    if not 0 <= fraction < 0.5:
        raise ValueError("fraction must be in [0, 0.5)")
    width, height = image.size
    dx, dy = int(width * fraction), int(height * fraction)
    cropped = image.crop((dx, dy, width - dx, height - dy))
    return cropped.resize((width, height), Image.Resampling.BICUBIC)


def _rotate(image: Image.Image, *, degrees: float) -> Image.Image:
    return image.convert("RGB").rotate(degrees, resample=Image.Resampling.BICUBIC, expand=False)


def _occlude(image: Image.Image, *, fraction: float, position: str = "center") -> Image.Image:
    """Paste an opaque block over part of the face. Deterministic given the same arguments."""
    if not 0 <= fraction < 1:
        raise ValueError("fraction must be in [0, 1)")
    out = image.convert("RGB").copy()
    width, height = out.size
    bw, bh = int(width * fraction), int(height * fraction)
    if bw == 0 or bh == 0:
        return out
    anchors = {
        "center": ((width - bw) // 2, (height - bh) // 2),
        "top": ((width - bw) // 2, 0),
        "bottom": ((width - bw) // 2, height - bh),
        "left": (0, (height - bh) // 2),
        "right": (width - bw, (height - bh) // 2),
    }
    if position not in anchors:
        raise ValueError(f"unknown position: {position}")
    x, y = anchors[position]
    out.paste((0, 0, 0), (x, y, x + bw, y + bh))
    return out


OPERATORS: dict[str, Callable[..., Image.Image]] = {
    "jpeg": _jpeg,
    "resize": _resize,
    "gaussian_blur": _gaussian_blur,
    "motion_blur": _motion_blur,
    "gaussian_noise": _gaussian_noise,
    "brightness": _brightness,
    "contrast": _contrast,
    "gamma": _gamma,
    "grayscale": _grayscale,
    "crop": _crop,
    "rotate": _rotate,
    "occlude": _occlude,
}

# Operators whose output depends on a random draw. Everything else must be bit-identical across
# runs given the same input and parameters.
STOCHASTIC = {"gaussian_noise"}


@dataclass(frozen=True)
class TransformRecord:
    transform_id: str
    implementation: str
    parameters: dict[str, Any]
    seed: int | None
    deterministic: bool
    input_sha256: str
    output_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform_id": self.transform_id,
            "implementation": self.implementation,
            "parameters": self.parameters,
            "seed": self.seed,
            "deterministic": self.deterministic,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
        }


def _digest_image(image: Image.Image) -> str:
    """Hash the decoded pixels, not an encoded file.

    Encoders embed timestamps and vary by version, so two runs of the same transform could hash
    differently while being pixel-identical — which would make the preview/batch equality check
    fail for a reason that has nothing to do with the transform.
    """
    rgb = image.convert("RGB")
    return hashlib.sha256(rgb.tobytes() + repr(rgb.size).encode()).hexdigest()


def apply(
    operator: str, image: Image.Image, *, parameters: dict[str, Any] | None = None
) -> tuple[Image.Image, TransformRecord]:
    """THE transform entry point. Preview and batch both call this and nothing else."""
    if operator not in OPERATORS:
        raise ValueError(f"unknown operator: {operator}")
    parameters = dict(parameters or {})

    if operator in STOCHASTIC and "seed" not in parameters:
        raise ValueError(f"{operator} is stochastic and requires an explicit seed")

    input_digest = _digest_image(image)
    output = OPERATORS[operator](image, **parameters)
    record = TransformRecord(
        transform_id=operator,
        implementation=f"studio_transforms.operators.{OPERATORS[operator].__name__}",
        parameters=parameters,
        seed=parameters.get("seed"),
        deterministic=operator not in STOCHASTIC or "seed" in parameters,
        input_sha256=input_digest,
        output_sha256=_digest_image(output),
    )
    return output, record


def apply_chain(
    image: Image.Image, steps: list[tuple[str, dict[str, Any]]]
) -> tuple[Image.Image, list[TransformRecord]]:
    """Apply operators in order, recording each step's input and output hashes."""
    records: list[TransformRecord] = []
    current = image
    for operator, parameters in steps:
        current, record = apply(operator, current, parameters=parameters)
        records.append(record)
    return current, records


def sweep(
    image: Image.Image, operator: str, parameter: str, values: list[Any],
    *, fixed: dict[str, Any] | None = None,
) -> list[tuple[Any, Image.Image, TransformRecord]]:
    """One-dimensional parameter sweep, e.g. JPEG quality 100 -> 10.

    Each level is applied to the ORIGINAL image, not to the previous level's output — otherwise the
    sweep measures accumulated recompression rather than the parameter.
    """
    results = []
    for value in values:
        parameters = {**(fixed or {}), parameter: value}
        output, record = apply(operator, image, parameters=parameters)
        results.append((value, output, record))
    return results


def load(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGB")
