# Per-asset camera datasets

These five datasets are original **synthetic simulation fixtures** created for this project. There are four paired observations per asset (20 pairs, 40 PNG files). RGB frames are procedural equipment illustrations; matching thermal frames are simulated grayscale intensity maps, not radiometric measurements. They share equipment geometry and pixel coordinates. They must not be used as evidence of real electrical faults, model accuracy, or real-world safety.

Enable `CAMERA_SIMULATION_ENABLED=true` and set `CAMERA_DATASETS_PATH=./dataset/cameras` from the backend working directory. Keep the existing database and apply `alembic upgrade head`; the cursor table is additive.

Select the corresponding equipment in the monitoring form and paste the same full backend URL into both fields:

| Asset | Pair URL suffix |
| --- | --- |
| Transformer T-01 | /camera/datasets/transformer-t-01/pair |
| Generator G-03 | /camera/datasets/generator-g-03/pair |
| Cooling Pump P-07 | /camera/datasets/pump-p-07/pair |
| Main Switchgear SG-12 | /camera/datasets/switchgear-sg-12/pair |
| Feeder Motor M-204 | /camera/datasets/motor-m-204/pair |

Every inspection fetches one JSON selection, then two pinned image URLs from that same dataset and pair. Each source cycles independently every ten minutes. The risk result is produced by the existing pipeline and active model, not a predefined label. Current weather uses the configured station coordinates and simulation inspection time. Previews use their own sequence and do not consume scheduled-source selections. Pair identity and file SHA-256 hashes are checked; failed acquisition does not substitute another image. A failed capture consumes its selection. Do not modify dataset files while captures are running.

`GET /camera/datasets` lists readiness, pair counts, data origin and generated pair URLs. Pair selection and pinned image routes are public only when simulation is enabled; do not place sensitive camera data behind these demonstration routes.

Each dataset has `dataset.json` with provenance and image hashes. The source generator `scripts/generate_camera_datasets.py` reproduces the datasets, refusing to overwrite existing directories. New custom assets can use a directory slug such as `transformer-t-02` and matching RGB/Thermal filenames. Pair IDs are unique within a dataset and may repeat across different assets. The old `/camera/pair` still reads the separate legacy `CAMERA_DATASET_PATH` directory.

Synthetic files are bundled in the deployment image and persist across redeploys. Selection cursors are stored in PostgreSQL. Inspection evidence still uses the configured storage system; the existing ephemeral-storage limitation applies on Railway unless durable storage is configured.
