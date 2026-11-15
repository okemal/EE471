# API Specification · Atelier Garment Classifier

## FastAPI Web Endpoints (`http://127.0.0.1:8000`)

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Engine readiness, compute device, class count, and baseline/optimized accuracies. |
| `GET` | `/api/ready` | Returns `200 {"status": "ready"}` when loaded, `503` otherwise. |
| `GET` | `/api/garments` | Lists all 10 FashionMNIST garment categories with per-class test accuracies. |
| `GET` | `/api/garments/{garment_id}` | Detailed category clues, common confusions, and accuracy breakdown. |
| `GET` | `/api/benchmarks` | Complete 6-trial hyperparameter optimization sweep and epoch curves. |
| `POST` | `/api/identify` | Accepts raw `image/jpeg`, `image/png`, or `image/webp` bytes; returns side-by-side `Identification`. |

### `POST /api/identify` Response Contract (`Identification`)

- `status`: `"matched" | "uncertain" | "no_match"`
- `baseline`: `ModelPrediction` from `QuickstartMLP` (`predicted_class`, `confidence`, `top_classes`, `hyperparameters`, `test_accuracy`, `elapsed_ms`)
- `optimized`: `ModelPrediction` from `GarmentConvNet`
- `comparison`: `{ agreement, confidence_delta, test_accuracy_delta, winner, summary }`
- `candidates`: Top 3 garment classes pairing optimized and baseline probabilities.
- `diagnostics`: Preprocessing metadata (`input_width`, `input_height`, `border_mean`, `polarity_inverted`, `preprocessing`).

## Cog Inference Endpoint (`http://127.0.0.1:5002`)

### `GET /health-check`
Returns `{"status": "READY"}` once `Runner.setup()` finishes loading and verifying both checkpoints.

### `POST /predictions`

Request body:

```json
{
  "input": {
    "image": "data:image/png;base64,..."
  }
}
```

Response (`200 OK`):

```json
{
  "status": "succeeded",
  "output": {
    "status": "matched",
    "baseline": { "predicted_class": "Sneaker", "confidence": 0.612, "..." : "..." },
    "optimized": { "predicted_class": "Sneaker", "confidence": 0.985, "..." : "..." },
    "comparison": { "agreement": true, "..." : "..." }
  }
}
```

Invalid or URL inputs return `"status": "failed"` with `"Supply a base64 JPEG, PNG, or WebP data URI; URLs are not accepted."` without issuing outbound HTTP requests.
