# Week 6 assignment and recording guide

Checked against **Week-6-InClass-Exercise.pdf**, EE 471, 2 November 2026,
provided locally by the student. This guide covers the software requirements
and prepares the recordings; it is not evidence that a student has recorded or
submitted the videos or completed the preliminary reading.

## Requirements and implementation

- **Dockerize Speech Studio and the voice calculator:** the existing sibling
  project, [speech_docker](../../speech_docker/README.md), contains both Dockerfiles,
  Compose configuration, setup instructions, and verification records.
- **Follow Cog's getting-started workflow:** this project's `cog.yaml` builds an
  inference image with Cog; `run.py:Runner` loads models once in `setup()` and
  classifies each upload in `run()`. See the
  [official tutorial](https://github.com/replicate/cog/blob/main/docs/getting-started.md).
- **Upload a cat image and classify with a button:** the website's file picker
  and **Identify this cat** button send the image to the web service, which calls
  the running Cog container in the assignment configuration.
- **Use the tutorial's pretrained model:** every Cog prediction runs TorchVision
  `ResNet50_Weights.IMAGENET1K_V1` and returns its top three ImageNet classes.
  The predicted class is visible on the result page and at
  `output.baseline.predicted_class` in the Cog response. The additional BioCLIP
  species classifier preserves the broader Felidae field guide requested for
  this project. Its suggestions and scores are clearly separate from ResNet50.
- **Clean source, Dockerfile, Cog YAML, setup instructions in GitHub:** `Dockerfile`
  builds the website; `cog.yaml` lets Cog generate the model's Docker image;
  `compose.cog.yaml` connects them. This directory belongs in the existing
  [EE471 repository](https://github.com/okemal/EE471/tree/main/Week%206/cat_id).
- **Live prediction logs from inside the running container:** use the `exec`
  command below; logs contain outcomes, classes, a random request ID, and timing.
  They exclude image data, filenames, and metadata.
- **Postman POST to Cog with an uploaded image:** use the included collection
  and local-image preparation command below. This targets Cog itself on port
  5002, not the website's `/api/identify` route.
- **Three named AVI videos:** recording steps follow. The recordings and the
  student's spoken explanation are still submission work; automated tests are
  not substitutes for those videos.

## Build and run the assignment stack

From the repository root, with Docker Desktop and Cog running/installed:

```bash
cd "Week 6/cat_id"
uv sync --frozen
uv run --frozen python scripts/download_models.py
uv run --frozen python scripts/download_resnet.py
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
# Stop an earlier direct-inference demo before loading the Cog models.
docker compose stop web
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 240
docker compose -f compose.cog.yaml ps
```

Open **http://127.0.0.1:8000**. Cog's HTTP API is at
**http://127.0.0.1:5002**; port 5000 is already used by Speech Studio. Allocate
at least 10 GiB of Docker Desktop VM memory and leave headroom for the web and
speech services. This configuration uses CPU inference because the local Docker
Desktop engine does not expose the NVIDIA GPU. Cog 0.23.1 and Python 3.11 are
used here. The build flag avoids unused packages in Cog's prebuilt base; the
clean Python base passes dependency consistency checks. Initial downloads/builds
need internet; inference runs with cached
weights and offline species profiles.

The host script and original `compose.yaml` remain useful for direct inference,
but **use `compose.cog.yaml` for the assignment recording**. It is a standalone
Compose file, not an override to merge with `compose.yaml`. The shared project
name replaces the web service rather than loading duplicate large models.

```bash
# Real HTTP checks, including the exact Cog prediction endpoint:
uv run --frozen python scripts/verify_cog.py

# Stop this stack after the demonstration:
docker compose -f compose.cog.yaml down
```

## Task-2-demo.avi

Record the actual desktop with your screen recorder. Keep the terminal and
browser readable, and show these steps in sequence:

1. Show `cog.yaml`, then run `cog build --use-cog-base-image=false` and the website build/start commands
   above. Cached builds are valid builds; leave the commands and success visible.
2. Show both containers running and the website at port 8000. Upload a local cat
   image, click **Identify this cat**, and show the species information and
   **ResNet50 · ImageNet classification** section. Try the tiger and non-cat
   examples, explaining that no-match is a normal result.
3. In a second terminal, access the actual running inference container and follow
   its prediction log. Generate another website prediction while this is visible:

   ```bash
   docker compose -f compose.cog.yaml exec cog sh
   id
   tail -F /tmp/felis-predictions.jsonl
   # Ctrl+C stops tail; exit leaves the container shell.
   ```

   This meets the request to inspect logs **inside** the container. An external
   `docker compose logs -f cog` is also useful, but show `exec` in the video.
   The file rotates at 1 MB and lives in `/tmp` tmpfs, so it is not permanent
   storage and disappears when the container is removed/recreated.
4. Prepare a genuine local image for the Cog JSON upload:

   ```bash
   uv run --frozen python scripts/prepare_postman.py frontend/assets/domestic-cat.jpg
   ```

   In **Postman Desktop**, import `docs/postman/Felis.postman_collection.json`
   and `artifacts/postman/local.postman_environment.json`. Select **Felis local
   image upload** as the environment. Send **Cog readiness**, then **Classify
   uploaded image**. Show the POST URL, JSON body, HTTP 200, `status: succeeded`,
   and `output.baseline.predicted_class` with the returned top classes. The
   collection's assertions appear in Postman's test results.
5. Explain the transport: the data URI contains the uploaded photo bytes. It is
   not a filename or a link to an image elsewhere. Cog expects a JSON `input`
   envelope, so do not select multipart form-data. The preparation script strips
   metadata and validates the image. Choose another file by rerunning that command
   and reimporting the local environment. Keep personal images and generated
   environment files out of cloud workspaces and Git.

For terminal troubleshooting only, the same prepared body can be sent with:

```bash
curl --fail-with-body http://127.0.0.1:5002/predictions \
  -H 'Content-Type: application/json' \
  --data-binary @artifacts/postman/request.json
```

The curl/automated check does **not** replace showing Postman in the recording.
Cog's standard response can echo the input data URI; expand `output` to make
the class response readable. Save the recording as **Task-2-demo.avi** using a
real AVI export/container, rather than only renaming another video extension.

## Task-1-demo.avi

Use the [speech applications' setup guide](../../speech_docker/README.md) to
record building and running both services. Show Speech Studio at port 5000 and
the voice calculator at port 5001, use the microphone, and demonstrate a spoken
calculation. Keep Azure credentials and secret files out of the recording. This
cat project does not replace that separate Task 1 demonstration.

## Tasks-code-explained.avi

Record your screen **with your own spoken explanation**. Cover each relevant
containerization block, describing its purpose rather than just reading it:

- `Dockerfile`: pinned Python/uv stages, CPU/CUDA dependency choice, cached and
  hash-checked installs, explicit source copies, non-root runtime, environment,
  health check, and the one-worker startup command.
- `cog.yaml`: CPU selection, Python/SDK versions, dependency file, Runner entry
  point, and image name. Cog generates the model image and HTTP prediction API.
- `run.py`: once-only model setup, exact tutorial weights, image validation,
  ResNet50 and species inference, structured output, and bounded live logging.
- `compose.cog.yaml`: two services, internal `http://cog:5000` address, loopback
  host ports, read-only weight mount/root, RAM-backed temporary files, resource
  limits, and readiness dependency. Explain why web does not load its own models.
- `backend/app/cog_client.py`: validated request transfer, readiness, busy/error
  handling, and no silent fallback. `resnet.py` verifies the checkpoint hash and
  uses restricted `weights_only=True` loading.
- `.dockerignore` and `.gitignore`: keep weights, virtual environments, artifacts,
  personal configuration, and generated image-upload data out of source/images.
- The relevant Dockerfiles, Compose configuration, secret-loading helper, and
  startup/health blocks in the separate `speech_docker` project, as Task 1 also
  belongs to this assignment.

Finally, verify all three AVI files play with readable text and that the code
explanation has audible narration. Upload them through the course's submission
channel; the PDF does not specify where to host videos. Do not commit large
recordings or generated upload bodies as application source.
