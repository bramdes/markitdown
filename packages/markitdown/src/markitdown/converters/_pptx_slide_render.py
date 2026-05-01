"""Render PowerPoint slides to PNG via the PowerPoint COM automation API.

Windows-only. Requires `pywin32` and a local installation of Microsoft PowerPoint.
The renderer is invoked lazily — only when a slide contains visual shapes that
the structural extractor cannot represent in text.
"""

import os
import tempfile
from typing import Iterable, Mapping


def render_slides(pptx_path: str, slide_indices: Iterable[int]) -> Mapping[int, bytes]:
    """Export the requested slides as PNG bytes.

    Args:
        pptx_path: Absolute path to the .pptx file on disk.
        slide_indices: 1-based slide numbers to render.

    Returns:
        Mapping of slide index -> PNG bytes. Slides that fail to render are
        omitted rather than raising.
    """
    indices = sorted({int(i) for i in slide_indices})
    if not indices:
        return {}

    import pythoncom  # type: ignore[import-not-found]
    import win32com.client  # type: ignore[import-not-found]

    pythoncom.CoInitialize()
    ppt = None
    presentation = None
    results: dict[int, bytes] = {}
    try:
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        # PowerPoint refuses to export with WithWindow=False on some versions
        # unless the app itself is allowed to show. Hide it where possible.
        try:
            ppt.WindowState = 2  # ppWindowMinimized
        except Exception:
            pass

        presentation = ppt.Presentations.Open(
            os.path.abspath(pptx_path),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )

        with tempfile.TemporaryDirectory() as tmp:
            for idx in indices:
                try:
                    out_path = os.path.join(tmp, f"slide_{idx}.png")
                    presentation.Slides(idx).Export(out_path, "PNG")
                    with open(out_path, "rb") as f:
                        results[idx] = f.read()
                except Exception:
                    continue
        return results
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if ppt is not None:
            try:
                ppt.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
