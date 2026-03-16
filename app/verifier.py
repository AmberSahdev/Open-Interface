from typing import Any, Optional

from PIL import Image, ImageChops


class StepVerifier:
    GLOBAL_CHANGE_PASS_RATIO = 0.0015
    GLOBAL_CHANGE_FAIL_RATIO = 0.00005
    LOCAL_CHANGE_PASS_RATIO = 0.0060
    LOCAL_CHANGE_FAIL_RATIO = 0.00040
    LOCAL_REGION_SIZE = 160

    def verify_step(
        self,
        step: dict[str, Any],
        executed_parameters: Optional[dict[str, Any]],
        before_image: Optional[Image.Image],
        after_image: Optional[Image.Image],
    ) -> dict[str, Any]:
        function_name = str(step.get('function') or '').strip()
        expected_outcome = str(step.get('expected_outcome') or '').strip()

        if function_name == 'sleep':
            return self._build_result(
                status='passed',
                reason='sleep_step',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=0.0,
                local_change_ratio=None,
            )

        if before_image is None or after_image is None:
            return self._build_result(
                status='uncertain',
                reason='missing_screenshot',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=0.0,
                local_change_ratio=None,
            )

        global_change_ratio = self._compute_change_ratio(before_image, after_image)
        local_change_ratio = self._compute_local_change_ratio(
            before_image,
            after_image,
            executed_parameters,
        )

        if function_name in {'move', 'moveTo', 'mouseDown', 'mouseUp'}:
            return self._build_result(
                status='passed',
                reason='movement_step',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if function_name == 'write':
            return self._classify_text_step(
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if function_name in {
            'click',
            'doubleClick',
            'tripleClick',
            'rightClick',
            'middleClick',
            'press',
            'hotkey',
            'scroll',
            'dragTo',
        }:
            return self._classify_visual_step(
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        return self._build_result(
            status='uncertain',
            reason='unsupported_step_type',
            function_name=function_name,
            expected_outcome=expected_outcome,
            global_change_ratio=global_change_ratio,
            local_change_ratio=local_change_ratio,
        )

    def _classify_text_step(
        self,
        *,
        function_name: str,
        expected_outcome: str,
        global_change_ratio: float,
        local_change_ratio: Optional[float],
    ) -> dict[str, Any]:
        if local_change_ratio is not None and local_change_ratio >= 0.0030:
            return self._build_result(
                status='passed',
                reason='text_region_changed',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if global_change_ratio >= self.GLOBAL_CHANGE_PASS_RATIO:
            return self._build_result(
                status='passed',
                reason='screen_changed',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if global_change_ratio <= self.GLOBAL_CHANGE_FAIL_RATIO:
            return self._build_result(
                status='failed',
                reason='no_visible_text_change',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        return self._build_result(
            status='uncertain',
            reason='small_text_change',
            function_name=function_name,
            expected_outcome=expected_outcome,
            global_change_ratio=global_change_ratio,
            local_change_ratio=local_change_ratio,
        )

    def _classify_visual_step(
        self,
        *,
        function_name: str,
        expected_outcome: str,
        global_change_ratio: float,
        local_change_ratio: Optional[float],
    ) -> dict[str, Any]:
        if function_name in {'doubleClick', 'tripleClick'}:
            return self._classify_multi_click_step(
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if local_change_ratio is not None and local_change_ratio >= self.LOCAL_CHANGE_PASS_RATIO:
            return self._build_result(
                status='passed',
                reason='target_region_changed',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if global_change_ratio >= self.GLOBAL_CHANGE_PASS_RATIO:
            return self._build_result(
                status='passed',
                reason='screen_changed',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if global_change_ratio <= self.GLOBAL_CHANGE_FAIL_RATIO:
            if local_change_ratio is None or local_change_ratio <= self.LOCAL_CHANGE_FAIL_RATIO:
                return self._build_result(
                    status='failed',
                    reason='no_visible_change',
                    function_name=function_name,
                    expected_outcome=expected_outcome,
                    global_change_ratio=global_change_ratio,
                    local_change_ratio=local_change_ratio,
                )

        return self._build_result(
            status='uncertain',
            reason='small_visual_change',
            function_name=function_name,
            expected_outcome=expected_outcome,
            global_change_ratio=global_change_ratio,
            local_change_ratio=local_change_ratio,
        )

    def _classify_multi_click_step(
        self,
        *,
        function_name: str,
        expected_outcome: str,
        global_change_ratio: float,
        local_change_ratio: Optional[float],
    ) -> dict[str, Any]:
        if global_change_ratio >= self.GLOBAL_CHANGE_PASS_RATIO:
            return self._build_result(
                status='passed',
                reason='screen_changed',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if local_change_ratio is not None and local_change_ratio >= self.LOCAL_CHANGE_PASS_RATIO:
            return self._build_result(
                status='uncertain',
                reason='selection_only_possible',
                function_name=function_name,
                expected_outcome=expected_outcome,
                global_change_ratio=global_change_ratio,
                local_change_ratio=local_change_ratio,
            )

        if global_change_ratio <= self.GLOBAL_CHANGE_FAIL_RATIO:
            if local_change_ratio is None or local_change_ratio <= self.LOCAL_CHANGE_FAIL_RATIO:
                return self._build_result(
                    status='failed',
                    reason='no_visible_change',
                    function_name=function_name,
                    expected_outcome=expected_outcome,
                    global_change_ratio=global_change_ratio,
                    local_change_ratio=local_change_ratio,
                )

        return self._build_result(
            status='uncertain',
            reason='small_visual_change',
            function_name=function_name,
            expected_outcome=expected_outcome,
            global_change_ratio=global_change_ratio,
            local_change_ratio=local_change_ratio,
        )

    def _compute_local_change_ratio(
        self,
        before_image: Image.Image,
        after_image: Image.Image,
        executed_parameters: Optional[dict[str, Any]],
    ) -> Optional[float]:
        if not isinstance(executed_parameters, dict):
            return None

        x_value = executed_parameters.get('x')
        y_value = executed_parameters.get('y')
        if x_value is None or y_value is None:
            return None

        try:
            center_x = int(float(x_value))
            center_y = int(float(y_value))
        except Exception:
            return None

        coordinate_resolution = executed_parameters.get('coordinate_resolution')
        if isinstance(coordinate_resolution, dict):
            logical_screen = coordinate_resolution.get('logical_screen')
            if isinstance(logical_screen, dict):
                logical_width = self._read_positive_int(logical_screen.get('width'))
                logical_height = self._read_positive_int(logical_screen.get('height'))
                if logical_width is not None and logical_height is not None:
                    center_x = int(center_x * (before_image.width / float(max(1, logical_width))))
                    center_y = int(center_y * (before_image.height / float(max(1, logical_height))))

        half = int(self.LOCAL_REGION_SIZE / 2)
        x1 = max(0, center_x - half)
        y1 = max(0, center_y - half)
        x2 = min(before_image.width, center_x + half)
        y2 = min(before_image.height, center_y + half)
        if x2 <= x1 or y2 <= y1:
            return None

        before_crop = before_image.crop((x1, y1, x2, y2))
        after_crop = after_image.crop((x1, y1, x2, y2))
        return self._compute_change_ratio(before_crop, after_crop)

    def _compute_change_ratio(self, before_image: Image.Image, after_image: Image.Image) -> float:
        before_gray = before_image.convert('L')
        after_gray = after_image.convert('L')
        diff_image = ImageChops.difference(before_gray, after_gray)
        histogram = diff_image.histogram()
        changed_pixels = 0
        for index, count in enumerate(histogram):
            if index <= 12:
                continue
            changed_pixels += count

        total_pixels = max(1, before_gray.width * before_gray.height)
        return round(changed_pixels / float(total_pixels), 6)

    def _read_positive_int(self, value: Any) -> Optional[int]:
        try:
            normalized = int(value)
        except Exception:
            return None
        if normalized <= 0:
            return None
        return normalized

    def _build_result(
        self,
        *,
        status: str,
        reason: str,
        function_name: str,
        expected_outcome: str,
        global_change_ratio: float,
        local_change_ratio: Optional[float],
    ) -> dict[str, Any]:
        result = {
            'status': status,
            'reason': reason,
            'function': function_name,
            'expected_outcome': expected_outcome,
            'global_change_ratio': round(global_change_ratio, 6),
        }
        if local_change_ratio is None:
            result['local_change_ratio'] = None
        else:
            result['local_change_ratio'] = round(local_change_ratio, 6)
        return result
