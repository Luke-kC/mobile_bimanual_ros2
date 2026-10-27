"""Packed-image crop utilities independent of ROS."""


BYTES_PER_PIXEL = {
    "rgb8": 3,
    "bgr8": 3,
    "rgba8": 4,
    "bgra8": 4,
    "mono8": 1,
}


def left_half_packed(data, *, width: int, height: int, step: int, encoding: str):
    """Return (cropped_width, cropped_step, bytes), removing source row padding.

    Crops the left half without conversion. Only packed, byte-aligned image
    encodings are supported. Reject unsupported layouts instead of corrupting
    image data silently.
    """
    if encoding not in BYTES_PER_PIXEL:
        raise ValueError(f"Unsupported image encoding: {encoding!r}")
    if width <= 0 or width % 2 or height <= 0:
        raise ValueError("Expected positive, even image width and positive height")
    bpp = BYTES_PER_PIXEL[encoding]
    if step < width * bpp:
        raise ValueError("Image row step is smaller than packed pixel data")
    if len(data) != step * height:
        raise ValueError("Image payload size does not match step * height")

    crop_width = width // 2
    crop_step = crop_width * bpp
    src = memoryview(data)
    result = bytearray(crop_step * height)
    for row in range(height):
        offset = row * step
        result[row * crop_step:(row + 1) * crop_step] = src[offset:offset + crop_step]
    return crop_width, crop_step, bytes(result)
