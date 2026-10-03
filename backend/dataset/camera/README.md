# Paired transformer camera simulation

Put synchronized image pairs for **one equipment/scene** in this directory (or set `CAMERA_DATASET_PATH` to a mounted dataset directory). No demonstration photographs are included or invented.

```
camera/
  Pair 001/
    RGB_001.jpg
    Thermal_001.jpg
  Pair 002/
    RGB_002.jpg
    Thermal_002.jpg
```

Flat folders are also supported. Use `RGB_<id>` and `Thermal_<id>` with JPEG/JPG/PNG extensions; each ID must be unique across the dataset, and both files must reside in the same directory. Filenames declare correspondence: an operator must verify that each pair actually depicts the same asset, scene, and observation. Incomplete or duplicate pairs fail with a clear error.

From `backend/`, configure:

```dotenv
CAMERA_SIMULATION_ENABLED=true
CAMERA_DATASET_PATH=./dataset/camera
```

Run `alembic upgrade head`. Restart the backend after changing environment settings. In both existing URL fields, enter `https://<backend-host>/camera/pair`. This is the **backend** host, not a frontend-only Vercel host. Local testing uses `http://localhost:8000/camera/pair` in both fields.

`GET /camera/pair` returns one JSON descriptor containing a pair ID, selection time, and the two immutable image URLs/checksums. The monitoring service calls it **once per inspection**, then fetches `/camera/pairs/<id>/rgb` and `/camera/pairs/<id>/thermal`. Both checksums and image identity headers must match before either modality reaches analysis. Image URLs return JPEG/PNG; reading them never advances selection. Every response uses `Cache-Control: no-store`.

Selection is sequential in numeric ID order, wrapping at the end. A database cursor per monitoring source (the `X-EvoThermGuard-Stream` header) persists across process restarts and coordinates concurrent workers. Direct preview calls have a separate cursor. With at least two pairs, successive selections for the same source differ until wraparound. Selection consumes a pair even if subsequent acquisition, weather retrieval, or analysis fails. Keep the dataset files immutable while the simulation runs; checksums reject changes between selection and fetch. Changing the catalog/path starts a new cursor.

The existing ten-minute scheduler, capture-now action, pipeline, risk labels, dashboard, alerts, and separate real-camera URLs continue to work. Weather is fetched independently from configured station coordinates and stored with the inspection. It represents conditions at **simulation time**, not historical weather when dataset images were recorded. Image metadata, environmental notes, and prediction evidence explicitly identify dataset-backed camera-feed simulation.

For deployment, mount/copy the real paired dataset into the backend container and set its absolute `CAMERA_DATASET_PATH` (for example `/data/transformer-t01`). Keep the dataset and evidence on persistent storage. The feature is disabled by default; enabling it exposes this demonstration dataset through unauthenticated replay/image endpoints so the backend can fetch it. Use only a dataset intended for this access. This is a simulated feed, not a live power-station camera connection or a newly trained/validated risk model.
