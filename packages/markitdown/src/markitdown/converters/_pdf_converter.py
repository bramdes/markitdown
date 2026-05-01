import sys
import io

from typing import BinaryIO, Any


from ._llm_caption import llm_caption
from .._base_converter import DocumentConverter, DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE


_dependency_exc_info = None
try:
    import fitz  # PyMuPDF
except ImportError:
    _dependency_exc_info = sys.exc_info()


ACCEPTED_MIME_TYPE_PREFIXES = [
    "application/pdf",
    "application/x-pdf",
]

ACCEPTED_FILE_EXTENSIONS = [".pdf"]

# DPI for page renders sent to the vision model. 150 balances detail vs token cost.
RENDER_DPI = 150


class PdfConverter(DocumentConverter):
    """
    Converts PDFs to Markdown using PyMuPDF for layout-aware text extraction.

    When a vision-capable LLM client is supplied (llm_client / llm_model), pages
    that contain non-text content (drawings, embedded images) are also rendered
    to PNG and transcribed via the LLM, with the result appended after the
    page's extracted text.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        if _dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".pdf",
                    feature="pdf",
                )
            ) from _dependency_exc_info[1].with_traceback(  # type: ignore[union-attr]
                _dependency_exc_info[2]
            )

        assert isinstance(file_stream, io.IOBase)
        pdf_bytes = file_stream.read()

        llm_client = kwargs.get("llm_client")
        llm_model = kwargs.get("llm_model")
        llm_prompt = kwargs.get("llm_prompt")
        vision_enabled = llm_client is not None and llm_model is not None

        parts: list[str] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page_index, page in enumerate(doc, start=1):
                parts.append(f"\n\n## Page {page_index}\n")

                page_text = page.get_text("text").strip()
                if page_text:
                    parts.append(page_text)

                if vision_enabled and self._page_has_visuals(page):
                    transcription = self._transcribe_page(
                        page,
                        client=llm_client,
                        model=llm_model,
                        prompt=llm_prompt,
                    )
                    if transcription:
                        parts.append("\n" + transcription.strip())

        return DocumentConverterResult(markdown="\n".join(parts).strip())

    @staticmethod
    def _page_has_visuals(page) -> bool:
        try:
            if page.get_images(full=False):
                return True
        except Exception:
            pass
        try:
            if page.get_drawings():
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _transcribe_page(page, *, client, model, prompt) -> str:
        try:
            pix = page.get_pixmap(dpi=RENDER_DPI, alpha=False)
            png_bytes = pix.tobytes("png")
        except Exception:
            return ""

        stream_info = StreamInfo(mimetype="image/png", extension=".png")
        try:
            result = llm_caption(
                io.BytesIO(png_bytes),
                stream_info,
                client=client,
                model=model,
                prompt=prompt,
            )
        except Exception:
            return ""
        return result or ""
