"""
Standalone Demo — Cobot Vision Sorting Simulator

Runs the full vision + cobot pipeline on test images without requiring
MQTT or Streamlit. Outputs annotated images and prints sorting results.

Usage:
    python demo.py

Author: Hesham Asim Khan
"""

import os
import sys
import time
import cv2

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vision import VisionSystem, DetectedPart
from generate_test_images import generate_conveyor_image


def run_demo():
    """Run the full vision + sorting pipeline on generated test images."""

    print("=" * 65)
    print("  COBOT VISION SORTING SIMULATOR — STANDALONE DEMO")
    print("=" * 65)
    print()

    vision = VisionSystem(min_area=400, max_area=50000)

    # Setup output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(project_dir, "test_images", "output")
    os.makedirs(output_dir, exist_ok=True)

    total_sorted = 0
    total_accepted = 0
    total_rejected = 0
    all_cycle_times = []

    num_frames = 5
    print(f"Processing {num_frames} conveyor frames...\n")

    for i in range(num_frames):
        print(f"--- Frame {i+1}/{num_frames} ---")

        # Generate a test conveyor image
        frame, ground_truth = generate_conveyor_image(
            num_parts=6, seed=100 + i
        )

        # Run vision detection
        t0 = time.time()
        parts = vision.process_frame(frame)
        detect_time = (time.time() - t0) * 1000

        print(f"  Vision: detected {len(parts)} parts in {detect_time:.1f}ms")

        # Process each detected part (simulate cobot sorting)
        for part in parts:
            cycle_start = time.time()

            status = "ACCEPT" if part.accepted else "REJECT"
            bin_name = "accept_bin" if part.accepted else "reject_bin"

            # Simulate cobot motion time (proportional to distance)
            import math
            bin_x = 700 if part.accepted else 700
            bin_y = 100 if part.accepted else 400
            dist = math.sqrt((bin_x - part.center_x)**2 + (bin_y - part.center_y)**2)
            sim_time = dist / 500  # 500 mm/s simulated speed

            cycle_ms = sim_time * 1000
            all_cycle_times.append(cycle_ms)

            total_sorted += 1
            if part.accepted:
                total_accepted += 1
            else:
                total_rejected += 1

            print(
                f"    Part #{part.part_id:3d}: {part.color:6s} {part.shape:8s} "
                f"→ {status:6s} | pick=({part.center_x:3d},{part.center_y:3d}) "
                f"→ {bin_name} | conf={part.confidence:.0%} | cycle={cycle_ms:.0f}ms"
            )

        # Save annotated image
        annotated = vision.draw_detections(frame, parts)
        out_path = os.path.join(output_dir, f"result_{i+1:02d}.png")
        cv2.imwrite(out_path, annotated)
        print(f"  Saved: {out_path}\n")

    # Print summary
    avg_cycle = sum(all_cycle_times) / len(all_cycle_times) if all_cycle_times else 0
    reject_rate = (total_rejected / total_sorted * 100) if total_sorted > 0 else 0

    print("=" * 65)
    print("  SORTING SUMMARY")
    print("=" * 65)
    print(f"  Total parts sorted:    {total_sorted}")
    print(f"  Accepted:              {total_accepted}")
    print(f"  Rejected:              {total_rejected}")
    print(f"  Reject rate:           {reject_rate:.1f}%")
    print(f"  Avg cycle time:        {avg_cycle:.0f}ms")
    print(f"  Min cycle time:        {min(all_cycle_times):.0f}ms")
    print(f"  Max cycle time:        {max(all_cycle_times):.0f}ms")
    print("=" * 65)
    print(f"\n  Annotated images saved to: {output_dir}/")
    print("  Green boxes = ACCEPTED | Red boxes = REJECTED")
    print()


if __name__ == "__main__":
    run_demo()
