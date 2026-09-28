"""Device selection and runtime diagnostics for Phase 4.11 embedding generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from productiq.exceptions.base import SemanticRetrievalError


@dataclass(frozen=True)
class TorchRuntimeInfo:
    """Optional PyTorch/CUDA diagnostics (safe when torch is not installed)."""

    torch_version: str | None
    cuda_available: bool
    cuda_version: str | None
    gpu_name: str | None
    device_count: int


@dataclass(frozen=True)
class ResolvedEmbeddingDevice:
    """Result of resolving a user/device CLI request."""

    requested: str
    selected: str
    cuda_was_requested: bool
    fell_back_to_cpu: bool


def get_torch_runtime_info() -> TorchRuntimeInfo:
    try:
        import torch
    except ImportError:
        return TorchRuntimeInfo(
            torch_version=None,
            cuda_available=False,
            cuda_version=None,
            gpu_name=None,
            device_count=0,
        )
    cuda_available = bool(torch.cuda.is_available())
    cuda_version = torch.version.cuda if cuda_available else None
    gpu_name: str | None = None
    device_count = int(torch.cuda.device_count()) if cuda_available else 0
    if cuda_available and device_count > 0:
        gpu_name = str(torch.cuda.get_device_name(0))
    return TorchRuntimeInfo(
        torch_version=str(torch.__version__),
        cuda_available=cuda_available,
        cuda_version=cuda_version,
        gpu_name=gpu_name,
        device_count=device_count,
    )


def runtime_info_to_dict(info: TorchRuntimeInfo) -> dict[str, Any]:
    return {
        "torch_version": info.torch_version,
        "cuda_available": info.cuda_available,
        "cuda_version": info.cuda_version,
        "gpu_name": info.gpu_name,
        "cuda_device_count": info.device_count,
    }


def resolve_embedding_device(
    requested: str | None,
    *,
    allow_cpu_fallback: bool = False,
) -> ResolvedEmbeddingDevice:
    """Resolve ``cpu``, ``cuda``, or ``auto`` without silently ignoring explicit CUDA."""
    normalized = (requested or "cpu").strip().lower()
    if normalized in {"gpu", "cuda"}:
        info = get_torch_runtime_info()
        if not info.cuda_available:
            if allow_cpu_fallback:
                return ResolvedEmbeddingDevice(
                    requested=normalized,
                    selected="cpu",
                    cuda_was_requested=True,
                    fell_back_to_cpu=True,
                )
            msg = (
                "CUDA was requested (--device cuda) but PyTorch reports CUDA as unavailable. "
                "Install a CUDA-enabled PyTorch build or pass --allow-cpu-fallback to run on CPU."
            )
            raise SemanticRetrievalError(msg)
        return ResolvedEmbeddingDevice(
            requested=normalized,
            selected="cuda",
            cuda_was_requested=True,
            fell_back_to_cpu=False,
        )
    if normalized == "auto":
        info = get_torch_runtime_info()
        if info.cuda_available:
            return ResolvedEmbeddingDevice(
                requested="auto",
                selected="cuda",
                cuda_was_requested=False,
                fell_back_to_cpu=False,
            )
        return ResolvedEmbeddingDevice(
            requested="auto",
            selected="cpu",
            cuda_was_requested=False,
            fell_back_to_cpu=False,
        )
    if normalized == "cpu":
        return ResolvedEmbeddingDevice(
            requested="cpu",
            selected="cpu",
            cuda_was_requested=False,
            fell_back_to_cpu=False,
        )
    msg = f"unsupported embedding device {requested!r}; use cpu, cuda, or auto"
    raise SemanticRetrievalError(msg)


__all__ = [
    "ResolvedEmbeddingDevice",
    "TorchRuntimeInfo",
    "get_torch_runtime_info",
    "resolve_embedding_device",
    "runtime_info_to_dict",
]
