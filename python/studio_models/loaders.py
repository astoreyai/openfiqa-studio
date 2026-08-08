"""Model loading and inspection (P08 M01–M07).

A loaded model reports what it actually is: its hash, its real input and output signatures, and
where it came from. Nothing is assumed from the filename.

The inspector reads the model's own graph rather than a sidecar description, because a description
can drift from the file it describes — and when it does, every downstream shape assumption is
wrong in a way that only shows up at inference time.
"""

from __future__ import annotations

import abc
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ModelLoadError(RuntimeError):
    """The model could not be loaded. Never substituted with an untrained stand-in."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class TensorSpec:
    name: str
    dtype: str
    shape: list[Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "dtype": self.dtype, "shape": self.shape}


@dataclass
class ModelInfo:
    """What inspection actually found. Fields it could not determine stay None."""

    model_id: str
    path: str
    sha256: str
    bytes: int
    framework: str
    inputs: list[TensorSpec] = field(default_factory=list)
    outputs: list[TensorSpec] = field(default_factory=list)
    parameter_count: int | None = None
    producer: str | None = None
    opset: int | None = None
    source_repository: str | None = None
    source_commit: str | None = None
    license: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "path": self.path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "framework": self.framework,
            "inputs": [t.to_dict() for t in self.inputs],
            "outputs": [t.to_dict() for t in self.outputs],
            "parameter_count": self.parameter_count,
            "producer": self.producer,
            "opset": self.opset,
            "source_repository": self.source_repository,
            "source_commit": self.source_commit,
            "license": self.license,
        }


class ModelLoader(abc.ABC):
    """Abstract, so an incomplete loader fails at construction rather than at inference."""

    framework: str

    @abc.abstractmethod
    def can_load(self, path: Path) -> bool:
        """True when this loader recognises the file."""

    @abc.abstractmethod
    def inspect(self, path: Path) -> ModelInfo:
        """Read the model's real signature from the file itself."""


class OnnxLoader(ModelLoader):
    framework = "onnx"

    def can_load(self, path: Path) -> bool:
        return Path(path).suffix.lower() == ".onnx"

    def inspect(self, path: Path) -> ModelInfo:
        path = Path(path)
        if not path.exists():
            raise ModelLoadError(f"model not found: {path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - environment problem, not logic
            raise ModelLoadError(f"onnxruntime is not installed: {exc}") from exc

        try:
            session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise ModelLoadError(f"onnxruntime could not load {path.name}: {exc}") from exc

        meta = session.get_modelmeta()
        return ModelInfo(
            model_id=path.stem,
            path=str(path),
            sha256=sha256_file(path),
            bytes=path.stat().st_size,
            framework="onnx",
            inputs=[
                TensorSpec(i.name, i.type, list(i.shape)) for i in session.get_inputs()
            ],
            outputs=[
                TensorSpec(o.name, o.type, list(o.shape)) for o in session.get_outputs()
            ],
            producer=meta.producer_name or None,
        )

    def session(self, path: Path):
        """An inference session for real forward passes."""
        import onnxruntime as ort

        return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


class TorchLoader(ModelLoader):
    framework = "pytorch"

    def can_load(self, path: Path) -> bool:
        return Path(path).suffix.lower() in {".pt", ".pth"}

    def inspect(self, path: Path) -> ModelInfo:
        path = Path(path)
        if not path.exists():
            raise ModelLoadError(f"model not found: {path}")
        try:
            import torch
        except ImportError as exc:
            raise ModelLoadError(f"torch is not installed: {exc}") from exc

        try:
            # weights_only=True refuses to execute pickled code. A checkpoint is data; loading one
            # should never be able to run arbitrary code from disk.
            obj = torch.load(str(path), map_location="cpu", weights_only=True)
        except Exception as exc:
            raise ModelLoadError(f"torch could not load {path.name}: {exc}") from exc

        state = obj.get("state_dict", obj) if isinstance(obj, dict) else obj
        parameter_count = None
        if isinstance(state, dict):
            parameter_count = sum(
                int(v.numel()) for v in state.values() if hasattr(v, "numel")
            )

        return ModelInfo(
            model_id=path.stem,
            path=str(path),
            sha256=sha256_file(path),
            bytes=path.stat().st_size,
            framework="pytorch",
            parameter_count=parameter_count,
        )


LOADERS: list[ModelLoader] = [OnnxLoader(), TorchLoader()]


def loader_for(path: str | Path) -> ModelLoader | None:
    path = Path(path)
    for loader in LOADERS:
        if loader.can_load(path):
            return loader
    return None


def inspect_model(path: str | Path, **provenance: Any) -> ModelInfo:
    """Inspect a model file, attaching provenance the caller knows and inspection cannot see."""
    path = Path(path)
    loader = loader_for(path)
    if loader is None:
        raise ModelLoadError(f"no loader recognises {path.suffix or path.name}")
    info = loader.inspect(path)
    for key, value in provenance.items():
        if hasattr(info, key):
            setattr(info, key, value)
    return info


def write_model_card(info: ModelInfo, destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(info.to_dict(), indent=2))
    return destination
