# Recorded equipment camera replay

The bundled feeds contain **12 observations / 24 real camera-recorded images** extracted from the original [InspecSafe-V1 dataset](https://huggingface.co/datasets/Tetrabot2026/InspecSafe-V1), revision f3cb7d3e7827c1afc1c5bfd0524257984bba46ab, test.tar.gz. Attribution: TetraBOT and the InspecSafe authors, [paper](https://arxiv.org/abs/2601.21173), CC BY 4.0. No synthetic equipment images are bundled.

These are recorded industrial inspection scenes replayed by an API. They are not real-time cameras, recordings of the configured station, or photographs of the demo asset IDs. Each dataset.json identifies the actual equipment type, original waypoint, original video members and hashes, extraction times, output hashes, license and timing limitations.

| Configured demo asset | Actual equipment | Status | URL path |
| --- | --- | --- | --- |
| Transformer T-01 | Current transformer, not a distribution transformer | 4 observations | /camera/datasets/transformer-t-01/pair |
| Main Switchgear SG-12 | Electrical distribution cabinet exterior | 4 observations | /camera/datasets/switchgear-sg-12/pair |
| Feeder Motor M-204 | Industrial motor | 4 observations | /camera/datasets/motor-m-204/pair |
| Cooling Pump P-07 | No verified matching recordings installed | Unavailable (503) | /camera/datasets/pump-p-07/pair |
| Generator G-03 | No verified matching recordings installed | Unavailable (503) | /camera/datasets/generator-g-03/pair |

Both modalities come from the same original waypoint's recording streams. Transformer/cabinet frames use matching relative video times. Motor infrared frames use +1 second to match the displayed clocks to the nearest second. **Hardware synchronization and exact simultaneous exposures are unverified.** These observations demonstrate acquisition and registration; they are not certified synchronized research ground truth. Fields of view differ, so registration is still required.

Thermal images are original colorized infrared frames with camera overlays, not radiometric temperature arrays. No visible image was generated from a thermal frame and no thermal image was generated from a visible photograph. Decoding and JPEG quality 95 are the only transformations. The existing baseline risk algorithm remains unvalidated; outputs are demonstrations, not calibrated temperatures or verified fault diagnoses. No new model training or accuracy validation was performed with these files.

Enable CAMERA_SIMULATION_ENABLED=true, set CAMERA_DATASETS_PATH=./dataset/cameras and CAMERA_PUBLIC_BASE_URL to the public HTTPS backend origin, then apply alembic upgrade head. Enter the same complete available asset URL in both existing RGB/thermal fields. GET /camera/datasets reports readiness, pair counts and provenance without advancing selections.

Every capture selects once, then fetches two pinned images for that pair. Dataset IDs, modality headers and hashes prevent cross-asset substitution. Database cursors cycle 001,002,003,004,001 independently for each source at the existing ten-minute interval; previews use separate cursors. Unavailable assets fail explicitly, without substituting synthetic or unrelated images.

Weather uses configured station coordinates and the replay inspection timestamp, not historical recording weather. Source, actual equipment type and synchronization limitations are preserved in inspection metadata. The frontend layout and both camera URL fields remain unchanged.

Add future genuine synchronized observations as RGB_<id>.jpg and Thermal_<id>.jpg in the same folder. Retain dataset.json attribution and per-observation timing evidence; remove availability_error only after installing verified data. Keep files immutable during captures. The legacy /camera/pair reads CAMERA_DATASET_PATH and has no default images.
