"""Reproduce original synthetic simulation fixtures; never measured field data.
Run from backend: python scripts/generate_camera_datasets.py
Only writes to dataset/cameras; refuses to replace existing dataset directories.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ASSETS = {
    "transformer-t-01": ("Transformer T-01", "Distribution Transformer"),
    "generator-g-03": ("Generator G-03", "Generator"),
    "pump-p-07": ("Cooling Pump P-07", "Industrial Pump"),
    "switchgear-sg-12": ("Main Switchgear SG-12", "Electrical Switchgear"),
    "motor-m-204": ("Feeder Motor M-204", "Motor"),
}
ROOT = Path(__file__).resolve().parents[1] / "dataset" / "cameras"
SIZE = (640, 480)


def scene(asset_id):
    rgb = Image.new("RGB", SIZE, (182, 200, 211))
    mask = Image.new("L", SIZE, 0)
    draw, thermal = ImageDraw.Draw(rgb), ImageDraw.Draw(mask)
    draw.rectangle((0, 370, 640, 480), fill=(106, 112, 112))
    draw.rectangle((90, 360, 550, 404), fill=(75, 81, 84))
    thermal.rectangle((90, 360, 550, 404), fill=20)

    def rect(box, color=(92, 124, 131), intensity=65):
        draw.rectangle(box, fill=color, outline=(31, 42, 48), width=3)
        thermal.rectangle(box, fill=intensity, outline=38, width=3)

    def ellipse(box, color=(112, 137, 145), intensity=70):
        draw.ellipse(box, fill=color, outline=(31, 42, 48), width=3)
        thermal.ellipse(box, fill=intensity, outline=38, width=3)

    if asset_id.startswith("transformer"):
        rect((175, 185, 465, 360))
        for x in range(190, 455, 18):
            rect((x, 205, x + 7, 347), (60, 90, 100), 53)
        rect((175, 178, 465, 202), (111, 141, 150), 70)
        for x in (225, 315, 405):
            rect((x, 109, x + 22, 178), (113, 89, 72), 73)
            for y in range(115, 170, 12):
                rect((x - 7, y, x + 29, y + 6), (146, 111, 83), 80)
        hotspot = (326, 147)
    elif asset_id.startswith("switchgear"):
        rect((150, 95, 490, 363), (114, 139, 148), 59)
        for x in (165, 270, 375):
            rect((x, 110, x + 97, 345), (128, 150, 159), 62)
            rect((x + 23, 132, x + 72, 168), (31, 47, 54), 36)
            rect((x + 72, 218, x + 78, 267), (51, 58, 62), 75)
            for y in range(295, 334, 9):
                rect((x + 17, y, x + 75, y + 3), (68, 86, 94), 50)
        hotspot = (342, 242)
    elif asset_id.startswith("pump"):
        rect((145, 315, 480, 360), (58, 84, 92), 45)
        ellipse((155, 205, 315, 350), (61, 129, 140), 68)
        rect((215, 148, 257, 215), (70, 125, 133), 60)
        rect((215, 148, 360, 181), (71, 122, 130), 60)
        rect((300, 237, 425, 320), (74, 112, 120), 65)
        ellipse((375, 220, 462, 337), (81, 115, 124), 70)
        hotspot = (303, 278)
    else:
        rect((165, 329, 474, 363), (59, 84, 92), 46)
        rect((175, 197, 432, 332), (90, 123, 132), 62)
        ellipse((390, 194, 481, 335), (102, 137, 146), 67)
        for x in range(195, 390, 16):
            rect((x, 212, x + 5, 319), (50, 86, 96), 52)
        rect((275, 154, 354, 197), (103, 126, 131), 74)
        rect((130, 249, 175, 280), (124, 130, 132), 58)
        if asset_id.startswith("generator"):
            rect((104, 223, 164, 307), (133, 120, 84), 66)
            ellipse((104, 236, 146, 291), (108, 103, 78), 57)
        hotspot = (404, 266)
    # Identical geometry and coordinate system in both modalities.
    return rgb, np.asarray(mask, dtype=np.float32), hotspot


def generate():
    for asset_id, (name, category) in ASSETS.items():
        folder = ROOT / asset_id
        if folder.exists():
            raise FileExistsError(f"Refusing to overwrite existing dataset: {folder}")
        folder.mkdir(parents=True)
        rgb, mask, (hx, hy) = scene(asset_id)
        yy, xx = np.mgrid[0:480, 0:640]
        entries = []
        for index, (amplitude, radius) in enumerate(((5, 14), (80, 22), (155, 32), (205, 43)), 1):
            pair_id = f"{index:03}"
            observation = folder / f"Pair {pair_id}"
            observation.mkdir()
            # Grayscale thermal intensity is illustrative, NOT degrees Celsius.
            heat = amplitude * np.exp(-((xx-hx)**2 + (yy-hy)**2) / (2 * radius**2))
            thermal = Image.fromarray(np.uint8(np.clip(22 + mask + heat * (mask > 0), 0, 255)))
            rgb_frame = rgb.copy()
            ImageDraw.Draw(rgb_frame).text((18, 18), f"SYNTHETIC SIMULATION | {name} | Pair {pair_id}", fill=(20, 28, 34))
            ImageDraw.Draw(thermal).text((18, 18), f"SYNTHETIC | {name} | Pair {pair_id} | NOT RADIOMETRIC", fill=95)
            paths = {"rgb": observation / f"RGB_{pair_id}.png", "thermal": observation / f"Thermal_{pair_id}.png"}
            rgb_frame.save(paths["rgb"])
            thermal.save(paths["thermal"])
            entries.append({"pair_id": pair_id, "synthetic_hotspot_amplitude": amplitude,
                            "images": {k: {"path": str(p.relative_to(folder)).replace('\\', '/'),
                                           "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in paths.items()}})
        manifest = {"dataset_id": asset_id, "asset_name": name, "equipment_type": category,
                    "data_origin": "synthetic", "generator": "scripts/generate_camera_datasets.py",
                    "description": "Original procedural equipment illustrations and matching synthetic grayscale thermal intensity maps. Simulation only; not field photographs, measured temperatures, risk labels, or model training/validation data.",
                    "alignment": "Shared scene geometry, 640x480 pixel coordinates; no sensor calibration claimed.",
                    "pair_count": len(entries), "pairs": entries}
        (folder / "dataset.json").write_text(json.dumps(manifest, indent=2) + '\n', encoding="utf-8")
        print(f"{asset_id}: {len(entries)} synthetic pairs")


if __name__ == "__main__":
    generate()
