import base64
import io
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from platform_support.screen_adapter import ScreenAdapter
from utils.settings import Settings


def create_ocr_backend(*args, **kwargs):
    raise RuntimeError(
        "OCR pipeline has been removed from the main screen prompt flow."
    )


class Screen:
    MAX_ANCHORS = 24
    MIN_ANCHORS = 8
    MAX_OCR_TEXT_BLOCKS = 24
    MAX_SUMMARY_TEXT_ITEMS = 12
    MAX_SUMMARY_REGION_ITEMS = 8
    EDGE_PROCESSING_MAX_WIDTH = 640
    EDGE_THRESHOLD = 28
    MIN_CLICKABLE_BOX_SIZE = 36
    TARGET_ICON_BOX_SIZE = 48
    MAX_PROMPT_IMAGE_WIDTH = 2560
    MAX_PROMPT_IMAGE_HEIGHT = 1440
    PROMPT_IMAGE_ARCHIVE_DIR_NAME = "prompt_images"
    GRID_MAJOR_TICK_PERCENT = 3
    GRID_MINOR_TICK_PERCENT = 3
    GRID_AXIS_MIN_PADDING = 24
    GRID_AXIS_BASE_PADDING_RATIO = 0.035
    GRID_MINOR_LINE_COLOR = (139, 0, 0, 120)
    GRID_MAJOR_LINE_COLOR = (139, 0, 0, 120)
    GRID_BORDER_COLOR = (139, 0, 0, 180)
    GRID_AXIS_BACKGROUND_COLOR = (250, 250, 252, 255)
    GRID_LABEL_COLOR = (220, 0, 0, 255)

    def __init__(self):
        self.screen_adapter = ScreenAdapter()

    def get_size(self) -> tuple[int, int]:
        return self.screen_adapter.get_size()

    def get_screenshot(self) -> Image.Image:
        return self.screen_adapter.get_screenshot()

    def get_screenshot_in_base64(self) -> str:
        return self.get_visual_prompt_payload()["annotated_image_base64"]

    def get_visual_prompt_payload(self) -> dict[str, Any]:
        prompt_image, frame_context = self._build_prompt_image_and_context()
        archived_image_path = self._maybe_archive_prompt_image(prompt_image)
        if archived_image_path is not None:
            frame_context["model_prompt_image_path"] = archived_image_path

        img_bytes = io.BytesIO()
        prompt_image.save(img_bytes, format="PNG", optimize=True)
        img_bytes.seek(0)

        return {
            "annotated_image_base64": base64.b64encode(img_bytes.read()).decode(
                "utf-8"
            ),
            "frame_context": frame_context,
        }

    def get_visual_prompt_file(self) -> tuple[str, dict[str, Any]]:
        prompt_image, frame_context = self._build_prompt_image_and_context()
        archived_image_path = self._maybe_archive_prompt_image(prompt_image)
        if archived_image_path is not None:
            frame_context["model_prompt_image_path"] = archived_image_path

        filename = "screenshot_annotated.png"
        filepath = os.path.join(Settings().get_settings_directory_path(), filename)
        prompt_image.save(filepath)
        return filepath, frame_context

    def get_screenshot_as_file_object(self):
        # In memory files don't work with OpenAI Assistants API because of missing filename attribute
        img_bytes = io.BytesIO()
        prompt_image, _ = self._build_prompt_image_and_context()
        prompt_image.save(
            img_bytes, format="PNG"
        )  # Save the screenshot to an in-memory file.
        img_bytes.seek(0)
        return img_bytes

    def _build_prompt_image_and_context(self) -> tuple[Image.Image, dict[str, Any]]:
        annotated_image, frame_context = self._build_annotated_frame()
        prompt_image = self._prepare_prompt_image(annotated_image)
        self._update_frame_context_for_prompt_image(
            frame_context,
            annotated_image.size,
            prompt_image.size,
        )
        return prompt_image, frame_context

    def _maybe_archive_prompt_image(self, prompt_image: Image.Image) -> str | None:
        settings_dict = Settings().get_dict()
        advanced_settings = settings_dict.get("advanced")
        save_model_prompt_images = False
        if isinstance(advanced_settings, dict):
            save_model_prompt_images = advanced_settings.get(
                "save_model_prompt_images", False
            )
        if (
            not isinstance(save_model_prompt_images, bool)
            or not save_model_prompt_images
        ):
            return None

        archive_directory = self._get_prompt_image_archive_directory()
        archive_directory.mkdir(parents=True, exist_ok=True)
        archive_path = self._build_prompt_image_archive_path(archive_directory)
        prompt_image.save(archive_path, format="PNG", optimize=True)
        return str(archive_path)

    def _get_prompt_image_archive_directory(self) -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / self.PROMPT_IMAGE_ARCHIVE_DIR_NAME

    def _build_prompt_image_archive_path(self, archive_directory: Path) -> Path:
        timestamp_text = datetime.now().strftime("%m月%d日_%H时%M分%S秒")
        candidate_path = archive_directory / f"{timestamp_text}.png"
        if not candidate_path.exists():
            return candidate_path

        suffix = 2
        while True:
            candidate_path = archive_directory / f"{timestamp_text}_{suffix}.png"
            if not candidate_path.exists():
                return candidate_path
            suffix += 1

    def get_temp_filename_for_current_screenshot(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
            prompt_image, _ = self._build_prompt_image_and_context()
            prompt_image.save(tmpfile.name)
            return tmpfile.name

    def get_screenshot_file(self):
        # Gonna always keep a screenshot.png in ~/.open-interface/ because file objects, temp files, every other way has an error
        filename = "screenshot.png"
        filepath = os.path.join(Settings().get_settings_directory_path(), filename)
        img, _ = self._build_prompt_image_and_context()
        img.save(filepath)
        return filepath

    def _build_annotated_frame(self) -> tuple[Image.Image, dict[str, Any]]:
        screenshot = self.get_screenshot()
        screen_width, screen_height = self.get_size()
        prompt_canvas, grid_reference = self._build_grid_prompt_image(screenshot)

        frame_context = {
            "logical_screen": {
                "width": screen_width,
                "height": screen_height,
            },
            "captured_screen": {
                "width": screenshot.width,
                "height": screenshot.height,
            },
            "grid_reference": grid_reference,
            "screen_state": self._build_screen_state(grid_reference),
        }

        return prompt_canvas, frame_context

    def _build_grid_prompt_image(
        self, screenshot: Image.Image
    ) -> tuple[Image.Image, dict[str, Any]]:
        font = ImageFont.load_default()
        measure_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_image)
        label_width, label_height = self._measure_text(measure_draw, "100", font)

        top_padding = max(
            self.GRID_AXIS_MIN_PADDING,
            label_height + 12,
            int(round(screenshot.height * self.GRID_AXIS_BASE_PADDING_RATIO)),
        )
        left_padding = max(
            self.GRID_AXIS_MIN_PADDING,
            label_width + 12,
            int(round(screenshot.width * self.GRID_AXIS_BASE_PADDING_RATIO)),
        )
        right_padding = max(8, int(round((label_width / 2) + 6)))
        bottom_padding = 8

        canvas_width = screenshot.width + left_padding + right_padding
        canvas_height = screenshot.height + top_padding + bottom_padding
        canvas = Image.new(
            "RGBA", (canvas_width, canvas_height), self.GRID_AXIS_BACKGROUND_COLOR
        )
        screenshot_rgba = screenshot.convert("RGBA")
        screenshot_origin = (left_padding, top_padding)
        canvas.paste(screenshot_rgba, screenshot_origin)

        draw = ImageDraw.Draw(canvas, "RGBA")
        origin_x = left_padding
        origin_y = top_padding
        content_right = origin_x + screenshot.width
        content_bottom = origin_y + screenshot.height

        draw.rectangle(
            (origin_x, origin_y, content_right, content_bottom),
            outline=self.GRID_BORDER_COLOR,
            width=1,
        )

        for percent in self._build_grid_tick_percents():
            x = origin_x + int(round(screenshot.width * (percent / 100.0)))
            y = origin_y + int(round(screenshot.height * (percent / 100.0)))
            line_color = (
                self.GRID_MAJOR_LINE_COLOR
                if percent == 100
                else self.GRID_MINOR_LINE_COLOR
            )

            draw.line((x, origin_y, x, content_bottom), fill=line_color, width=1)
            draw.line((origin_x, y, content_right, y), fill=line_color, width=1)

            self._draw_top_tick_label(draw, font, percent, x, top_padding, canvas_width)
            self._draw_left_tick_label(draw, font, percent, y, left_padding)

        grid_reference = {
            "major_tick_percent": self.GRID_MAJOR_TICK_PERCENT,
            "minor_tick_percent": self.GRID_MINOR_TICK_PERCENT,
            "coordinate_system": "percent",
            "axes": ["top", "left"],
            "origin": "top_left",
            "x_range": [0, 100],
            "y_range": [0, 100],
            "padding": {
                "top": top_padding,
                "left": left_padding,
                "right": right_padding,
                "bottom": bottom_padding,
            },
        }

        return canvas.convert("RGB"), grid_reference

    def _measure_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    ) -> tuple[int, int]:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return int(right - left), int(bottom - top)

    def _build_grid_tick_percents(self) -> list[int]:
        tick_percents = list(range(0, 101, self.GRID_MINOR_TICK_PERCENT))
        if len(tick_percents) == 0 or tick_percents[-1] != 100:
            tick_percents.append(100)
        return tick_percents

    def _draw_top_tick_label(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
        percent: int,
        x_position: int,
        top_padding: int,
        canvas_width: int,
    ) -> None:
        label = str(percent)
        label_width, label_height = self._measure_text(draw, label, font)
        text_x = int(round(x_position - (label_width / 2)))
        text_x = max(2, min(text_x, canvas_width - label_width - 2))
        text_y = max(2, int(round((top_padding - label_height) / 2)))
        draw.text((text_x, text_y), label, fill=self.GRID_LABEL_COLOR, font=font)

    def _draw_left_tick_label(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
        percent: int,
        y_position: int,
        left_padding: int,
    ) -> None:
        label = str(percent)
        label_width, label_height = self._measure_text(draw, label, font)
        text_x = max(2, left_padding - label_width - 6)
        text_y = int(round(y_position - (label_height / 2)))
        draw.text(
            (text_x, max(2, text_y)), label, fill=self.GRID_LABEL_COLOR, font=font
        )

    def _update_frame_context_for_prompt_image(
        self,
        frame_context: dict[str, Any],
        source_size: tuple[int, int],
        prompt_size: tuple[int, int],
    ) -> None:
        if not isinstance(frame_context, dict):
            return

        source_width, source_height = source_size
        prompt_width, prompt_height = prompt_size
        scale_x = prompt_width / float(max(1, source_width))
        scale_y = prompt_height / float(max(1, source_height))

        grid_reference = frame_context.get("grid_reference")
        if isinstance(grid_reference, dict):
            padding = grid_reference.get("padding")
            if isinstance(padding, dict):
                grid_reference["padding"] = {
                    "top": int(round(float(padding.get("top") or 0) * scale_y)),
                    "left": int(round(float(padding.get("left") or 0) * scale_x)),
                    "right": int(round(float(padding.get("right") or 0) * scale_x)),
                    "bottom": int(round(float(padding.get("bottom") or 0) * scale_y)),
                }
            grid_reference["prompt_image_size"] = {
                "width": prompt_width,
                "height": prompt_height,
            }

        screen_state = frame_context.get("screen_state")
        if isinstance(screen_state, dict):
            screen_state["prompt_mode"] = "pure_grid"
            screen_state["prompt_image_size"] = {
                "width": prompt_width,
                "height": prompt_height,
            }

    def _detect_anchor_boxes(
        self, image: Image.Image
    ) -> list[tuple[int, int, int, int]]:
        processed, scale_x, scale_y = self._get_processed_edge_image(image)
        width, height = processed.size
        edge_pixels = processed.load()
        if edge_pixels is None:
            return []
        assert edge_pixels is not None

        visited = [[False for _ in range(width)] for _ in range(height)]
        candidates: list[dict[str, Any]] = []
        min_component_size = max(24, int((width * height) * 0.00005))
        max_component_size = int((width * height) * 0.20)

        for y in range(height):
            for x in range(width):
                if visited[y][x] or edge_pixels[x, y] < self.EDGE_THRESHOLD:
                    continue

                stack = [(x, y)]
                visited[y][x] = True
                min_x = max_x = x
                min_y = max_y = y
                area = 0

                while len(stack) > 0:
                    cx, cy = stack.pop()
                    area += 1
                    if cx < min_x:
                        min_x = cx
                    if cx > max_x:
                        max_x = cx
                    if cy < min_y:
                        min_y = cy
                    if cy > max_y:
                        max_y = cy

                    for nx, ny in (
                        (cx - 1, cy),
                        (cx + 1, cy),
                        (cx, cy - 1),
                        (cx, cy + 1),
                    ):
                        if nx < 0 or ny < 0 or nx >= width or ny >= height:
                            continue
                        if visited[ny][nx]:
                            continue
                        visited[ny][nx] = True
                        if edge_pixels[nx, ny] < self.EDGE_THRESHOLD:
                            continue
                        stack.append((nx, ny))

                if area < min_component_size or area > max_component_size:
                    continue

                box_w = (max_x - min_x) + 1
                box_h = (max_y - min_y) + 1
                if box_w < 10 or box_h < 10:
                    continue
                if box_w > int(width * 0.7) or box_h > int(height * 0.7):
                    continue

                x1 = int(min_x * scale_x)
                y1 = int(min_y * scale_y)
                x2 = int((max_x + 1) * scale_x)
                y2 = int((max_y + 1) * scale_y)

                x1 = max(0, min(image.width - 1, x1))
                y1 = max(0, min(image.height - 1, y1))
                x2 = max(x1 + 1, min(image.width, x2))
                y2 = max(y1 + 1, min(image.height, y2))

                normalized_box = self._expand_anchor_box(
                    (x1, y1, x2, y2), image.width, image.height
                )
                candidates.append(
                    {
                        "box": normalized_box,
                        "score": area,
                        "priority": self._get_anchor_priority(normalized_box),
                    }
                )

        candidates.sort(key=lambda item: (item["priority"], -item["score"]))
        top_candidates = [item["box"] for item in candidates[: self.MAX_ANCHORS * 3]]

        deduped: list[tuple[int, int, int, int]] = []
        for candidate in top_candidates:
            if any(self._boxes_overlap(candidate, existing) for existing in deduped):
                continue
            deduped.append(candidate)

        deduped.sort(key=lambda box: (box[1], box[0]))
        return deduped[: self.MAX_ANCHORS]

    def _get_processed_edge_image(
        self, image: Image.Image
    ) -> tuple[Image.Image, float, float]:
        grayscale = image.convert("L")
        width, height = grayscale.size
        if width <= self.EDGE_PROCESSING_MAX_WIDTH:
            processed = grayscale.filter(ImageFilter.FIND_EDGES)
            return processed, 1.0, 1.0

        scaled_height = max(1, int((self.EDGE_PROCESSING_MAX_WIDTH / width) * height))
        resized = grayscale.resize(
            (self.EDGE_PROCESSING_MAX_WIDTH, scaled_height), Image.Resampling.BILINEAR
        )
        processed = resized.filter(ImageFilter.FIND_EDGES)

        scale_x = width / processed.width
        scale_y = height / processed.height
        return processed, scale_x, scale_y

    def _build_grid_anchor_boxes(
        self,
        width: int,
        height: int,
        cols: int,
        rows: int,
    ) -> list[tuple[int, int, int, int]]:
        boxes: list[tuple[int, int, int, int]] = []
        cell_w = max(1, width // cols)
        cell_h = max(1, height // rows)

        for row in range(rows):
            for col in range(cols):
                x1 = col * cell_w
                y1 = row * cell_h
                x2 = width if col == cols - 1 else (col + 1) * cell_w
                y2 = height if row == rows - 1 else (row + 1) * cell_h
                boxes.append((x1, y1, x2, y2))

        return boxes

    def _build_anchor_metadata(
        self,
        boxes: list[tuple[int, int, int, int]],
        image_width: int,
        image_height: int,
        sources: list[str],
    ) -> list[dict[str, Any]]:
        anchors: list[dict[str, Any]] = []

        for index, box in enumerate(boxes, start=1):
            x1, y1, x2, y2 = box
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            box_width = max(1, x2 - x1)
            box_height = max(1, y2 - y1)
            source = sources[index - 1] if index - 1 < len(sources) else "detected"

            anchors.append(
                {
                    "id": index,
                    "source": source,
                    "region_type": "unknown",
                    "x_percent": round(center_x / max(1, image_width), 4),
                    "y_percent": round(center_y / max(1, image_height), 4),
                    "width_percent": round(box_width / max(1, image_width), 4),
                    "height_percent": round(box_height / max(1, image_height), 4),
                    "interactable_score": self._estimate_interactable_score(
                        box_width,
                        box_height,
                        image_width,
                        image_height,
                        source,
                    ),
                    "bbox_percent": {
                        "x1": round(x1 / max(1, image_width), 4),
                        "y1": round(y1 / max(1, image_height), 4),
                        "x2": round(x2 / max(1, image_width), 4),
                        "y2": round(y2 / max(1, image_height), 4),
                    },
                    "text": "",
                    "semantic_role": None,
                    "semantic_confidence": 0.0,
                    "matched_text_block_ids": [],
                }
            )

        return anchors

    def _build_raw_visual_candidates(
        self, anchors: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        raw_visual_candidates: list[dict[str, Any]] = []

        for anchor in anchors:
            raw_visual_candidates.append(
                {
                    "id": f"raw_{anchor.get('id')}",
                    "anchor_id": anchor.get("id"),
                    "source": anchor.get("source"),
                    "region_type": "unknown",
                    "center_percent": {
                        "x": anchor.get("x_percent"),
                        "y": anchor.get("y_percent"),
                    },
                    "size_percent": {
                        "width": anchor.get("width_percent"),
                        "height": anchor.get("height_percent"),
                    },
                    "bbox_percent": dict(anchor.get("bbox_percent") or {}),
                    "interactable_score": anchor.get("interactable_score"),
                }
            )

        return raw_visual_candidates

    def _extract_ocr_context(self, screenshot: Image.Image) -> dict[str, Any]:
        settings_dict = Settings().get_dict()
        backend = create_ocr_backend(settings_dict)
        started_at = time.perf_counter()
        text_blocks = backend.extract_text_blocks(screenshot)
        latency_ms = int(round((time.perf_counter() - started_at) * 1000))

        normalized_blocks: list[dict[str, Any]] = []
        for index, block in enumerate(text_blocks[: self.MAX_OCR_TEXT_BLOCKS], start=1):
            bbox = block.get("bbox") or {}
            x1 = int(bbox.get("x1") or 0)
            y1 = int(bbox.get("y1") or 0)
            x2 = int(bbox.get("x2") or 0)
            y2 = int(bbox.get("y2") or 0)
            if x2 <= x1 or y2 <= y1:
                continue

            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            normalized_blocks.append(
                {
                    "id": f"text_{index}",
                    "text": str(block.get("text") or "").strip(),
                    "confidence": round(float(block.get("confidence") or 0.0), 4),
                    "center_percent": {
                        "x": round(center_x / max(1, screenshot.width), 4),
                        "y": round(center_y / max(1, screenshot.height), 4),
                    },
                    "bbox_percent": {
                        "x1": round(x1 / max(1, screenshot.width), 4),
                        "y1": round(y1 / max(1, screenshot.height), 4),
                        "x2": round(x2 / max(1, screenshot.width), 4),
                        "y2": round(y2 / max(1, screenshot.height), 4),
                    },
                }
            )

        return {
            "backend_used": backend.backend_name,
            "latency_ms": latency_ms,
            "text_blocks": normalized_blocks,
        }

    def _build_semantic_regions(
        self,
        anchors: list[dict[str, Any]],
        text_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        semantic_regions: list[dict[str, Any]] = []
        matched_text_ids: set[str] = set()

        for anchor in anchors:
            anchor_text_blocks = self._match_text_blocks_to_anchor(anchor, text_blocks)
            anchor_text = self._join_text_blocks(anchor_text_blocks)
            region_type = self._classify_anchor_region(anchor, anchor_text_blocks)
            semantic_role = self._classify_semantic_role(anchor, anchor_text)
            semantic_confidence = self._estimate_semantic_confidence(
                anchor, anchor_text_blocks, region_type, semantic_role
            )

            matched_text_block_ids: list[str] = []
            for block in anchor_text_blocks:
                block_id = str(block.get("id") or "")
                if block_id != "":
                    matched_text_ids.add(block_id)
                    matched_text_block_ids.append(block_id)

            anchor["region_type"] = region_type
            anchor["text"] = anchor_text
            anchor["semantic_role"] = semantic_role
            anchor["semantic_confidence"] = semantic_confidence
            anchor["matched_text_block_ids"] = matched_text_block_ids

            semantic_regions.append(
                {
                    "id": f"sem_anchor_{anchor.get('id')}",
                    "source": "fused" if len(anchor_text_blocks) > 0 else "visual_only",
                    "region_type": region_type,
                    "semantic_role": semantic_role,
                    "confidence": semantic_confidence,
                    "backing_anchor_id": anchor.get("id"),
                    "text": anchor_text,
                    "text_block_ids": matched_text_block_ids,
                    "center_percent": {
                        "x": anchor.get("x_percent"),
                        "y": anchor.get("y_percent"),
                    },
                    "size_percent": {
                        "width": anchor.get("width_percent"),
                        "height": anchor.get("height_percent"),
                    },
                    "bbox_percent": dict(anchor.get("bbox_percent") or {}),
                    "interactable_score": anchor.get("interactable_score"),
                }
            )

        for block in text_blocks:
            block_id = str(block.get("id") or "")
            if block_id in matched_text_ids:
                continue

            text = str(block.get("text") or "").strip()
            semantic_regions.append(
                {
                    "id": f"sem_{block_id}",
                    "source": "ocr_only",
                    "region_type": "text",
                    "semantic_role": self._classify_text_block_role(block),
                    "confidence": round(float(block.get("confidence") or 0.0), 4),
                    "backing_anchor_id": None,
                    "text": text,
                    "text_block_ids": [block_id],
                    "center_percent": dict(block.get("center_percent") or {}),
                    "size_percent": self._build_size_percent_from_bbox(
                        block.get("bbox_percent") or {}
                    ),
                    "bbox_percent": dict(block.get("bbox_percent") or {}),
                    "interactable_score": 0.0,
                }
            )

        semantic_regions.sort(
            key=lambda item: (
                (item.get("bbox_percent") or {}).get("y1", 0.0),
                (item.get("bbox_percent") or {}).get("x1", 0.0),
            )
        )
        return semantic_regions

    def _match_text_blocks_to_anchor(
        self,
        anchor: dict[str, Any],
        text_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        anchor_box = anchor.get("bbox_percent") or {}

        for block in text_blocks:
            block_box = block.get("bbox_percent") or {}
            overlap_ratio = self._compute_box_overlap_ratio(anchor_box, block_box)
            if overlap_ratio >= 0.2:
                matches.append(block)
                continue

            block_center = block.get("center_percent") or {}
            center_x = float(block_center.get("x") or 0.0)
            center_y = float(block_center.get("y") or 0.0)
            if self._point_in_box(center_x, center_y, anchor_box):
                matches.append(block)

        matches.sort(
            key=lambda item: (
                (item.get("bbox_percent") or {}).get("y1", 0.0),
                (item.get("bbox_percent") or {}).get("x1", 0.0),
            )
        )
        return matches

    def _join_text_blocks(self, text_blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        seen: set[str] = set()

        for block in text_blocks:
            text = str(block.get("text") or "").strip()
            if text == "":
                continue
            normalized = text.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            parts.append(text)

        joined = " ".join(parts).strip()
        if len(joined) > 96:
            return joined[:93] + "..."
        return joined

    def _classify_anchor_region(
        self,
        anchor: dict[str, Any],
        text_blocks: list[dict[str, Any]],
    ) -> str:
        width_ratio = float(anchor.get("width_percent") or 0.0)
        height_ratio = float(anchor.get("height_percent") or 0.0)
        if height_ratio <= 0.0:
            return "unknown"

        aspect_ratio = width_ratio / max(0.0001, height_ratio)
        area_ratio = width_ratio * height_ratio
        text = self._join_text_blocks(text_blocks)
        text_length = len(text)
        has_text = text != ""
        bbox = anchor.get("bbox_percent") or {}
        y1 = float(bbox.get("y1") or 0.0)

        if has_text and y1 <= 0.18 and width_ratio >= 0.18:
            return "text"

        if aspect_ratio >= 5.0 and 0.02 <= height_ratio <= 0.14:
            if not has_text:
                return "input_like"
            if text_length >= 10:
                return "input_like"

        if (
            has_text
            and 1.2 <= aspect_ratio <= 6.5
            and 0.02 <= height_ratio <= 0.12
            and text_length <= 32
        ):
            return "button_like"

        if has_text:
            return "text"

        if 0.75 <= aspect_ratio <= 1.35 and area_ratio <= 0.025:
            return "icon"

        if aspect_ratio >= 3.8 and 0.02 <= height_ratio <= 0.12:
            return "input_like"

        return "unknown"

    def _classify_semantic_role(self, anchor: dict[str, Any], text: str) -> str | None:
        if text == "":
            return None

        bbox = anchor.get("bbox_percent") or {}
        width_ratio = float(anchor.get("width_percent") or 0.0)
        y1 = float(bbox.get("y1") or 0.0)
        if y1 <= 0.18 and width_ratio >= 0.18:
            return "window_title"
        return None

    def _classify_text_block_role(self, text_block: dict[str, Any]) -> str | None:
        bbox = text_block.get("bbox_percent") or {}
        width_ratio = float(bbox.get("x2", 0.0)) - float(bbox.get("x1", 0.0))
        y1 = float(bbox.get("y1") or 0.0)
        if y1 <= 0.18 and width_ratio >= 0.18:
            return "window_title"
        return None

    def _estimate_semantic_confidence(
        self,
        anchor: dict[str, Any],
        text_blocks: list[dict[str, Any]],
        region_type: str,
        semantic_role: str | None,
    ) -> float:
        interactable_score = float(anchor.get("interactable_score") or 0.0)
        text_confidence = 0.0
        if len(text_blocks) > 0:
            total_confidence = 0.0
            for block in text_blocks:
                total_confidence += float(block.get("confidence") or 0.0)
            text_confidence = total_confidence / float(len(text_blocks))

        confidence = 0.35
        if region_type == "text":
            confidence = max(confidence, text_confidence)
        elif region_type in {"button_like", "input_like", "icon"}:
            confidence = max(
                confidence, interactable_score * 0.65 + text_confidence * 0.35
            )
        else:
            confidence = max(confidence, interactable_score * 0.75)

        if semantic_role == "window_title":
            confidence = max(confidence, 0.75)

        return round(min(1.0, confidence), 4)

    def _build_size_percent_from_bbox(self, bbox: dict[str, Any]) -> dict[str, float]:
        x1 = float(bbox.get("x1") or 0.0)
        y1 = float(bbox.get("y1") or 0.0)
        x2 = float(bbox.get("x2") or 0.0)
        y2 = float(bbox.get("y2") or 0.0)
        return {
            "width": round(max(0.0, x2 - x1), 4),
            "height": round(max(0.0, y2 - y1), 4),
        }

    def _build_screen_state(self, grid_reference: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompt_mode": "pure_grid",
            "coordinate_system": "percent",
            "major_tick_percent": grid_reference.get("major_tick_percent"),
            "minor_tick_percent": grid_reference.get("minor_tick_percent"),
            "axes": list(grid_reference.get("axes") or []),
        }

    def _annotate_image(
        self, image: Image.Image, anchors: list[dict[str, Any]]
    ) -> Image.Image:
        draw = ImageDraw.Draw(image)

        for anchor in anchors:
            bbox = anchor["bbox_percent"]
            x1 = int(bbox["x1"] * image.width)
            y1 = int(bbox["y1"] * image.height)
            x2 = int(bbox["x2"] * image.width)
            y2 = int(bbox["y2"] * image.height)

            draw.rectangle((x1, y1, x2, y2), outline="red", width=3)

            label = f"[{anchor['id']}]"
            label_x = x1 + 4
            label_y = max(0, y1 - 20)
            draw.rectangle(
                (label_x - 2, label_y - 2, label_x + (len(label) * 8), label_y + 14),
                fill="red",
            )
            draw.text((label_x, label_y), label, fill="white")

        return image

    def _prepare_prompt_image(self, image: Image.Image) -> Image.Image:
        width = image.width
        height = image.height
        if (
            width <= self.MAX_PROMPT_IMAGE_WIDTH
            and height <= self.MAX_PROMPT_IMAGE_HEIGHT
        ):
            return image

        width_scale = self.MAX_PROMPT_IMAGE_WIDTH / float(max(1, width))
        height_scale = self.MAX_PROMPT_IMAGE_HEIGHT / float(max(1, height))
        scale = min(width_scale, height_scale)
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    def _compute_box_overlap_ratio(
        self,
        box_a: dict[str, Any],
        box_b: dict[str, Any],
    ) -> float:
        ax1 = float(box_a.get("x1") or 0.0)
        ay1 = float(box_a.get("y1") or 0.0)
        ax2 = float(box_a.get("x2") or 0.0)
        ay2 = float(box_a.get("y2") or 0.0)
        bx1 = float(box_b.get("x1") or 0.0)
        by1 = float(box_b.get("y1") or 0.0)
        bx2 = float(box_b.get("x2") or 0.0)
        by2 = float(box_b.get("y2") or 0.0)

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = max(0.000001, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(0.000001, (bx2 - bx1) * (by2 - by1))
        return inter_area / float(min(area_a, area_b))

    def _point_in_box(
        self, x_value: float, y_value: float, box: dict[str, Any]
    ) -> bool:
        x1 = float(box.get("x1") or 0.0)
        y1 = float(box.get("y1") or 0.0)
        x2 = float(box.get("x2") or 0.0)
        y2 = float(box.get("y2") or 0.0)
        return x1 <= x_value <= x2 and y1 <= y_value <= y2

    def _boxes_overlap(
        self, box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]
    ) -> bool:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return False

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1, (bx2 - bx1) * (by2 - by1))
        overlap_ratio = inter_area / float(min(area_a, area_b))
        return overlap_ratio >= 0.7

    def _expand_anchor_box(
        self,
        box: tuple[int, int, int, int],
        image_width: int,
        image_height: int,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        box_width = max(1, x2 - x1)
        box_height = max(1, y2 - y1)
        target_width = max(self.MIN_CLICKABLE_BOX_SIZE, box_width)
        target_height = max(self.MIN_CLICKABLE_BOX_SIZE, box_height)

        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)
        half_width = int(target_width / 2)
        half_height = int(target_height / 2)

        expanded_x1 = max(0, center_x - half_width)
        expanded_y1 = max(0, center_y - half_height)
        expanded_x2 = min(image_width, expanded_x1 + target_width)
        expanded_y2 = min(image_height, expanded_y1 + target_height)

        if expanded_x2 - expanded_x1 < target_width:
            expanded_x1 = max(0, expanded_x2 - target_width)
        if expanded_y2 - expanded_y1 < target_height:
            expanded_y1 = max(0, expanded_y2 - target_height)

        return expanded_x1, expanded_y1, expanded_x2, expanded_y2

    def _get_anchor_priority(self, box: tuple[int, int, int, int]) -> int:
        x1, y1, x2, y2 = box
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        target_area = self.TARGET_ICON_BOX_SIZE * self.TARGET_ICON_BOX_SIZE
        aspect_penalty = abs(width - height) * self.TARGET_ICON_BOX_SIZE
        large_box_penalty = max(0, area - (target_area * 4))
        return abs(area - target_area) + aspect_penalty + large_box_penalty

    def _estimate_interactable_score(
        self,
        box_width: int,
        box_height: int,
        image_width: int,
        image_height: int,
        source: str,
    ) -> float:
        width_ratio = box_width / float(max(1, image_width))
        height_ratio = box_height / float(max(1, image_height))
        area_ratio = width_ratio * height_ratio

        size_score = 1.0 - min(1.0, abs(area_ratio - 0.0025) / 0.01)
        aspect_score = 1.0 - min(1.0, abs(width_ratio - height_ratio) * 4.0)
        source_bonus = 0.15 if source == "detected" else 0.0
        final_score = max(
            0.0, min(1.0, size_score * 0.65 + aspect_score * 0.20 + 0.15 + source_bonus)
        )
        return round(final_score, 4)
