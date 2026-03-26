"""
Test Image Generator — Creates Conveyor Belt Images with Colored Parts

Generates test images with random colored shapes (circles, squares, triangles)
placed on a gray conveyor belt background for vision system testing.

Author: Hesham Asim Khan
"""

import cv2
import numpy as np
import os
import random


def draw_circle(img, cx, cy, color_bgr, size):
    """Draw a filled circle."""
    cv2.circle(img, (cx, cy), size, color_bgr, -1)
    cv2.circle(img, (cx, cy), size, (80, 80, 80), 2)


def draw_square(img, cx, cy, color_bgr, size):
    """Draw a filled square, optionally rotated."""
    angle = random.uniform(-15, 15)
    half = size
    pts = np.array([
        [-half, -half], [half, -half], [half, half], [-half, half]
    ], dtype=np.float32)
    
    rad = np.radians(angle)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    pts = pts @ rot.T
    pts = pts + np.array([cx, cy])
    pts = pts.astype(np.int32)
    
    cv2.fillPoly(img, [pts], color_bgr)
    cv2.polylines(img, [pts], True, (80, 80, 80), 2)


def draw_triangle(img, cx, cy, color_bgr, size):
    """Draw a filled equilateral triangle."""
    angle = random.uniform(0, 360)
    pts = []
    for i in range(3):
        a = np.radians(angle + i * 120)
        px = int(cx + size * np.cos(a))
        py = int(cy + size * np.sin(a))
        pts.append([px, py])
    pts = np.array(pts, dtype=np.int32)
    
    cv2.fillPoly(img, [pts], color_bgr)
    cv2.polylines(img, [pts], True, (80, 80, 80), 2)


# BGR colors for parts
COLORS = {
    "red":    (0, 0, 220),
    "blue":   (220, 50, 0),
    "green":  (0, 180, 0),
    "yellow": (0, 220, 220),
}

SHAPES = {
    "circle": draw_circle,
    "square": draw_square,
    "triangle": draw_triangle,
}


def generate_conveyor_image(width=800, height=500, num_parts=6, seed=None):
    """
    Generate a single conveyor belt image with random parts.
    
    Args:
        width: image width in pixels
        height: image height in pixels
        num_parts: number of parts to place
        seed: random seed for reproducibility
        
    Returns:
        tuple of (image, list of placed part info dicts)
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Create conveyor belt background (dark gray with subtle texture)
    img = np.full((height, width, 3), (60, 60, 60), dtype=np.uint8)
    
    # Add conveyor belt lines
    for y in range(0, height, 40):
        cv2.line(img, (0, y), (width, y), (70, 70, 70), 1)
    
    # Add slight noise for realism
    noise = np.random.randint(-5, 5, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # Add conveyor edges
    cv2.line(img, (0, 20), (width, 20), (100, 100, 100), 2)
    cv2.line(img, (0, height - 20), (width, height - 20), (100, 100, 100), 2)

    parts_info = []
    placed_positions = []

    for i in range(num_parts):
        shape_name = random.choice(list(SHAPES.keys()))
        color_name = random.choice(list(COLORS.keys()))
        size = random.randint(25, 45)

        # Find a non-overlapping position
        for _ in range(50):
            cx = random.randint(80, width - 80)
            cy = random.randint(60, height - 60)
            
            overlap = False
            for px, py in placed_positions:
                if abs(cx - px) < 100 and abs(cy - py) < 100:
                    overlap = True
                    break
            if not overlap:
                break

        draw_fn = SHAPES[shape_name]
        color_bgr = COLORS[color_name]
        draw_fn(img, cx, cy, color_bgr, size)
        placed_positions.append((cx, cy))

        parts_info.append({
            "shape": shape_name,
            "color": color_name,
            "cx": cx,
            "cy": cy,
            "size": size,
        })

    return img, parts_info


def generate_test_set(output_dir="test_images", num_images=5):
    """Generate a set of test conveyor images."""
    os.makedirs(output_dir, exist_ok=True)

    for i in range(num_images):
        num_parts = random.randint(3, 8)
        img, parts = generate_conveyor_image(num_parts=num_parts, seed=42 + i)
        
        filename = f"conveyor_{i+1:02d}.png"
        filepath = os.path.join(output_dir, filename)
        cv2.imwrite(filepath, img)
        
        print(f"Generated {filename}: {len(parts)} parts")
        for p in parts:
            print(f"  - {p['color']} {p['shape']} at ({p['cx']}, {p['cy']})")

    print(f"\nDone. {num_images} test images saved to {output_dir}/")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(project_dir, "test_images")
    generate_test_set(output_dir=output_dir)
