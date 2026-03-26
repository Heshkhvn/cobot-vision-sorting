"""
Vision System Module — OpenCV Part Detection & Classification

Processes images (or webcam frames) to detect parts on a conveyor surface,
classify them by shape and color, and return pick coordinates for the cobot.

Author: Hesham Asim Khan
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class DetectedPart:
    """Represents a single part detected by the vision system."""
    part_id: int
    shape: str          # "circle", "square", "triangle", "unknown"
    color: str          # "red", "blue", "green", "yellow", "unknown"
    center_x: int       # pixel x-coordinate of part centroid
    center_y: int       # pixel y-coordinate of part centroid
    width: int          # bounding box width in pixels
    height: int         # bounding box height in pixels
    area: float         # contour area in pixels
    angle: float        # rotation angle in degrees
    confidence: float   # classification confidence 0.0 - 1.0
    accepted: bool      # True = pick, False = reject


# HSV color ranges for part classification
COLOR_RANGES = {
    "red_low":  {"lower": np.array([0, 100, 100]),   "upper": np.array([10, 255, 255])},
    "red_high": {"lower": np.array([160, 100, 100]), "upper": np.array([180, 255, 255])},
    "blue":     {"lower": np.array([100, 100, 100]), "upper": np.array([130, 255, 255])},
    "green":    {"lower": np.array([40, 80, 80]),    "upper": np.array([80, 255, 255])},
    "yellow":   {"lower": np.array([20, 100, 100]),  "upper": np.array([35, 255, 255])},
}

# Sorting rules: which shape+color combos are accepted vs rejected
SORT_RULES = {
    ("circle", "red"): True,
    ("circle", "blue"): True,
    ("circle", "green"): True,
    ("square", "red"): True,
    ("square", "blue"): True,
    ("square", "green"): False,    # reject green squares
    ("triangle", "red"): False,    # reject red triangles
    ("triangle", "blue"): True,
    ("triangle", "green"): True,
}


class VisionSystem:
    """
    Processes images to detect and classify parts on a conveyor surface.
    
    Pipeline:
    1. Convert to HSV color space
    2. Apply color masks to isolate each color
    3. Find contours in each mask
    4. Classify shape by contour approximation
    5. Compute centroid, bounding box, and rotation angle
    6. Apply sorting rules to determine accept/reject
    """

    def __init__(self, min_area: int = 500, max_area: int = 50000):
        self.min_area = min_area
        self.max_area = max_area
        self._part_counter = 0

    def process_frame(self, frame: np.ndarray) -> List[DetectedPart]:
        """
        Process a single frame and return all detected parts.
        
        Args:
            frame: BGR image (numpy array) from camera or file
            
        Returns:
            List of DetectedPart objects with classification results
        """
        if frame is None:
            return []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blurred = cv2.GaussianBlur(hsv, (5, 5), 0)

        detected_parts = []

        for color_name in ["red", "blue", "green", "yellow"]:
            mask = self._create_color_mask(blurred, color_name)
            contours = self._find_contours(mask)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.min_area or area > self.max_area:
                    continue

                shape, confidence = self._classify_shape(contour)
                cx, cy = self._get_centroid(contour)
                x, y, w, h = cv2.boundingRect(contour)
                angle = self._get_rotation_angle(contour)

                accepted = SORT_RULES.get((shape, color_name), False)

                self._part_counter += 1
                part = DetectedPart(
                    part_id=self._part_counter,
                    shape=shape,
                    color=color_name,
                    center_x=cx,
                    center_y=cy,
                    width=w,
                    height=h,
                    area=area,
                    angle=angle,
                    confidence=confidence,
                    accepted=accepted,
                )
                detected_parts.append(part)

        return detected_parts

    def _create_color_mask(self, hsv: np.ndarray, color: str) -> np.ndarray:
        """Create a binary mask for the given color."""
        if color == "red":
            mask_low = cv2.inRange(hsv, COLOR_RANGES["red_low"]["lower"], COLOR_RANGES["red_low"]["upper"])
            mask_high = cv2.inRange(hsv, COLOR_RANGES["red_high"]["lower"], COLOR_RANGES["red_high"]["upper"])
            mask = cv2.bitwise_or(mask_low, mask_high)
        else:
            r = COLOR_RANGES[color]
            mask = cv2.inRange(hsv, r["lower"], r["upper"])

        # Clean up noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return mask

    def _find_contours(self, mask: np.ndarray) -> list:
        """Find external contours in a binary mask."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    def _classify_shape(self, contour) -> Tuple[str, float]:
        """
        Classify contour shape by polygon approximation.
        
        Returns: (shape_name, confidence)
        """
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            return "unknown", 0.0

        approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
        vertices = len(approx)

        area = cv2.contourArea(contour)
        circularity = (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0

        if vertices == 3:
            return "triangle", min(0.95, 0.7 + circularity)
        elif vertices == 4:
            # Check if it's roughly square vs rectangle
            x, y, w, h = cv2.boundingRect(approx)
            aspect = float(w) / h if h > 0 else 0
            if 0.75 <= aspect <= 1.35:
                return "square", min(0.95, 0.6 + aspect * 0.3)
            return "square", min(0.85, 0.5 + aspect * 0.2)
        elif vertices > 6 and circularity > 0.7:
            return "circle", min(0.98, circularity)
        else:
            return "unknown", 0.3

    def _get_centroid(self, contour) -> Tuple[int, int]:
        """Compute contour centroid using image moments."""
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return 0, 0
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return cx, cy

    def _get_rotation_angle(self, contour) -> float:
        """Get rotation angle from minimum area rectangle."""
        if len(contour) < 5:
            return 0.0
        _, _, angle = cv2.minAreaRect(contour)
        return round(angle, 1)

    def draw_detections(self, frame: np.ndarray, parts: List[DetectedPart]) -> np.ndarray:
        """
        Draw bounding boxes and labels on the frame for visualization.
        
        Green boxes = accepted, Red boxes = rejected.
        """
        output = frame.copy()

        for part in parts:
            color = (0, 200, 0) if part.accepted else (0, 0, 200)
            label_bg = (0, 160, 0) if part.accepted else (0, 0, 160)
            status = "PICK" if part.accepted else "REJECT"

            # Bounding box
            x = part.center_x - part.width // 2
            y = part.center_y - part.height // 2
            cv2.rectangle(output, (x, y), (x + part.width, y + part.height), color, 2)

            # Centroid crosshair
            cv2.drawMarker(output, (part.center_x, part.center_y), color,
                           cv2.MARKER_CROSS, 15, 2)

            # Label background
            label = f"#{part.part_id} {part.color} {part.shape} [{status}]"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(output, (x, y - th - 10), (x + tw + 4, y - 2), label_bg, -1)
            cv2.putText(output, label, (x + 2, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Confidence
            conf_label = f"{part.confidence:.0%}"
            cv2.putText(output, conf_label, (x, y + part.height + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        return output

    def reset_counter(self):
        """Reset the part ID counter."""
        self._part_counter = 0
