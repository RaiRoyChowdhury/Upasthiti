"""
Image preprocessing: decoding incoming frames into OpenCV/numpy arrays.

The frontend sends frames as base64-encoded JPEG (data URLs from a canvas
snapshot of the webcam feed). Nothing else in the CV layer should know or
care about that wire format — it all works in numpy arrays (BGR, as OpenCV
expects) from here on.
"""

import base64
import binascii

import cv2
import numpy as np

from utils.exceptions import ValidationAppError

MAX_IMAGE_BYTES = 6 * 1024 * 1024  # 6MB safety cap on a single frame


def decode_base64_image(data: str) -> np.ndarray:
    """
    Accepts either a raw base64 string or a data URL
    ("data:image/jpeg;base64,...."). Returns a BGR numpy array.
    """
    if not data:
        raise ValidationAppError("No image data provided.", code="EMPTY_IMAGE")

    if "," in data and data.strip().startswith("data:"):
        data = data.split(",", 1)[1]

    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ValidationAppError("Image data is not valid base64.", code="INVALID_IMAGE_ENCODING")

    if len(raw) == 0:
        raise ValidationAppError("Decoded image is empty.", code="EMPTY_IMAGE")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValidationAppError("Image is too large.", code="IMAGE_TOO_LARGE")

    np_arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValidationAppError("Could not decode image. Unsupported or corrupt format.", code="UNDECODABLE_IMAGE")

    return frame


def resize_for_detection(frame: np.ndarray, max_dimension: int = 960) -> np.ndarray:
    """
    Downscales oversized frames before running detection — the detector's
    own det_size handles the model input, this just avoids wasting time
    decoding/copying huge frames the browser occasionally sends.
    """
    height, width = frame.shape[:2]
    largest = max(height, width)
    if largest <= max_dimension:
        return frame

    scale = max_dimension / largest
    new_size = (int(width * scale), int(height * scale))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
