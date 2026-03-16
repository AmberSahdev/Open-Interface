import os
import tempfile
from typing import Any

from PIL import Image

try:
    import objc
    from Foundation import NSURL
    import Quartz
    import Vision
    VISION_RUNTIME_AVAILABLE = True
except Exception:
    objc = None
    NSURL = None
    Quartz = None
    Vision = None
    VISION_RUNTIME_AVAILABLE = False


DEFAULT_OCR_LANGUAGES = ['en-US', 'zh-Hans']
MAX_OCR_IMAGE_EDGE = 1920
MIN_TEXT_CONFIDENCE = 0.25
MAX_TEXT_BLOCKS = 48


class OCRBackend:
    backend_name = 'disabled'

    def is_available(self) -> bool:
        return False

    def extract_text_blocks(self, image: Image.Image) -> list[dict[str, Any]]:
        return []


class DisabledOCRBackend(OCRBackend):
    def __init__(self, backend_name: str = 'disabled'):
        self.backend_name = backend_name


class VisionOCRBackend(OCRBackend):
    backend_name = 'vision'

    def is_available(self) -> bool:
        if not VISION_RUNTIME_AVAILABLE or Vision is None:
            return False
        return hasattr(Vision, 'VNRecognizeTextRequest')

    def extract_text_blocks(self, image: Image.Image) -> list[dict[str, Any]]:
        if not self.is_available():
            return []

        prepared_image, scale_x, scale_y = self._prepare_image(image)
        image_path = self._write_temp_image(prepared_image)
        try:
            observations = self._recognize_text_observations(image_path)
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)

        text_blocks: list[dict[str, Any]] = []
        for observation in observations:
            candidate = self._read_top_candidate(observation)
            if candidate is None:
                continue

            bbox = self._read_bbox(observation, prepared_image.width, prepared_image.height)
            if bbox is None:
                continue

            x1, y1, x2, y2 = bbox
            normalized_box = {
                'x1': int(round(x1 * scale_x)),
                'y1': int(round(y1 * scale_y)),
                'x2': int(round(x2 * scale_x)),
                'y2': int(round(y2 * scale_y)),
            }
            text_blocks.append({
                'text': candidate['text'],
                'confidence': candidate['confidence'],
                'bbox': normalized_box,
            })

        return self._dedupe_text_blocks(text_blocks)

    def _prepare_image(self, image: Image.Image) -> tuple[Image.Image, float, float]:
        max_edge = max(image.width, image.height)
        if max_edge <= MAX_OCR_IMAGE_EDGE:
            return image.convert('RGB'), 1.0, 1.0

        scale = MAX_OCR_IMAGE_EDGE / float(max_edge)
        target_width = max(1, int(round(image.width * scale)))
        target_height = max(1, int(round(image.height * scale)))
        resized = image.convert('RGB').resize((target_width, target_height), Image.Resampling.LANCZOS)
        scale_x = image.width / float(max(1, target_width))
        scale_y = image.height / float(max(1, target_height))
        return resized, scale_x, scale_y

    def _write_temp_image(self, image: Image.Image) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            image.save(temp_file.name, format='PNG')
            return temp_file.name

    def _recognize_text_observations(self, image_path: str) -> list[Any]:
        if not self.is_available() or objc is None or NSURL is None or Quartz is None or Vision is None:
            return []

        with objc.autorelease_pool():
            image_url = NSURL.fileURLWithPath_(image_path)
            ci_image = Quartz.CIImage.imageWithContentsOfURL_(image_url)
            if ci_image is None:
                return []

            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
            request.setUsesLanguageCorrection_(True)

            if hasattr(request, 'setRecognitionLanguages_'):
                request.setRecognitionLanguages_(DEFAULT_OCR_LANGUAGES)

            if hasattr(request, 'setAutomaticallyDetectsLanguage_'):
                request.setAutomaticallyDetectsLanguage_(True)

            handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, {})
            perform_result = handler.performRequests_error_([request], None)
            if isinstance(perform_result, tuple):
                success = bool(perform_result[0])
                error = perform_result[1]
                if not success or error is not None:
                    return []
            elif not perform_result:
                return []

            return list(request.results() or [])

    def _read_top_candidate(self, observation: Any) -> dict[str, Any] | None:
        candidates = observation.topCandidates_(1)
        if candidates is None or len(candidates) == 0:
            return None

        top_candidate = candidates[0]
        text = str(top_candidate.string() or '').strip()
        if text == '':
            return None

        confidence = round(float(top_candidate.confidence()), 4)
        if confidence < MIN_TEXT_CONFIDENCE:
            return None

        return {
            'text': text,
            'confidence': confidence,
        }

    def _read_bbox(
        self,
        observation: Any,
        image_width: int,
        image_height: int,
    ) -> tuple[int, int, int, int] | None:
        bounding_box = observation.boundingBox()
        origin = getattr(bounding_box, 'origin', None)
        size = getattr(bounding_box, 'size', None)
        if origin is None or size is None:
            return None

        x1 = int(round(origin.x * image_width))
        y1 = int(round((1.0 - origin.y - size.height) * image_height))
        x2 = int(round((origin.x + size.width) * image_width))
        y2 = int(round((1.0 - origin.y) * image_height))

        x1 = max(0, min(image_width - 1, x1))
        y1 = max(0, min(image_height - 1, y1))
        x2 = max(x1 + 1, min(image_width, x2))
        y2 = max(y1 + 1, min(image_height, y2))
        return x1, y1, x2, y2

    def _dedupe_text_blocks(self, text_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        for block in sorted(text_blocks, key=lambda item: (item['bbox']['y1'], item['bbox']['x1'])):
            should_skip = False
            for existing in deduped:
                if block['text'] != existing['text']:
                    continue
                if self._boxes_overlap(block['bbox'], existing['bbox']):
                    should_skip = True
                    break

            if should_skip:
                continue

            deduped.append(block)
            if len(deduped) >= MAX_TEXT_BLOCKS:
                break

        return deduped

    def _boxes_overlap(self, box_a: dict[str, int], box_b: dict[str, int]) -> bool:
        inter_x1 = max(box_a['x1'], box_b['x1'])
        inter_y1 = max(box_a['y1'], box_b['y1'])
        inter_x2 = min(box_a['x2'], box_b['x2'])
        inter_y2 = min(box_a['y2'], box_b['y2'])

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return False

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = max(1, (box_a['x2'] - box_a['x1']) * (box_a['y2'] - box_a['y1']))
        area_b = max(1, (box_b['x2'] - box_b['x1']) * (box_b['y2'] - box_b['y1']))
        overlap_ratio = inter_area / float(min(area_a, area_b))
        return overlap_ratio >= 0.7


def create_ocr_backend(settings_dict: dict[str, Any] | None) -> OCRBackend:
    if not isinstance(settings_dict, dict):
        settings_dict = {}

    ocr_enabled = settings_dict.get('ocr_enabled', True)
    if not isinstance(ocr_enabled, bool) or not ocr_enabled:
        return DisabledOCRBackend('disabled')

    backend_name = str(settings_dict.get('ocr_backend') or 'auto').strip().lower()
    if backend_name in {'', 'auto', 'vision'}:
        backend = VisionOCRBackend()
        if backend.is_available():
            return backend
        return DisabledOCRBackend('vision_unavailable')

    return DisabledOCRBackend(f'unsupported:{backend_name}')
