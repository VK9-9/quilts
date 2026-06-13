"""CLIP image embedding for quilt visual preference learning.

Loads ViT-B/32 (OpenAI weights) once at module level and exposes
embed_image() for encoding PNG bytes to a 512-dim float32 vector.
"""

import io

import numpy as np
import open_clip
import torch
from PIL import Image

_model = None  # pylint: disable=invalid-name
_preprocess = None  # pylint: disable=invalid-name
_device = "cpu"  # pylint: disable=invalid-name


def _load():
    """Load CLIP model on first use."""
    global _model, _preprocess  # pylint: disable=global-statement
    if _model is None:
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
        _model.eval()
        _model.to(_device)


def embed_image(png_bytes):
    """Encode PNG bytes to a 512-dim float32 numpy vector.

    >>> import io, numpy as np
    >>> from PIL import Image
    >>> buf = io.BytesIO()
    >>> Image.new("RGB", (64, 64), color=(100, 150, 200)).save(buf, format="PNG")
    >>> v = embed_image(buf.getvalue())
    >>> v.shape
    (512,)
    >>> v.dtype
    dtype('float32')
    """
    _load()
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    tensor = _preprocess(img).unsqueeze(0).to(_device)
    with torch.no_grad():
        features = _model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features[0].cpu().numpy().astype(np.float32)


def embed_images(png_bytes_list):
    """Encode a list of PNG bytes to an (N, 512) float32 array.

    >>> v = embed_images([])
    >>> v.shape
    (0, 512)
    """
    if not png_bytes_list:
        return np.zeros((0, 512), dtype=np.float32)
    _load()
    tensors = []
    for png_bytes in png_bytes_list:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        tensors.append(_preprocess(img))
    batch = torch.stack(tensors).to(_device)
    with torch.no_grad():
        features = _model.encode_image(batch)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().astype(np.float32)
