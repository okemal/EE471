# Model choice and decision policy

## Why these checkpoints

The [Cog getting-started example](https://github.com/replicate/cog/blob/main/docs/getting-started.md)
illustrates a generic pretrained classifier. ImageNet ResNet50 has a fixed
1,000-class vocabulary: several domestic-cat breed labels map to the same
species, only some wild cats have labels, and some labels are broader than a
single species. It cannot directly rank a complete Felidae species catalogue.

The assignment configuration nevertheless runs **that exact tutorial baseline**
for every upload: TorchVision `ResNet50_Weights.IMAGENET1K_V1`, its standard
preprocessing, frozen ResNet50, and top-three softmax classes. The website shows
these separately and the Cog API exposes `output.baseline.predicted_class`.
The BioCLIP/OpenCLIP pipeline below provides the additional species-level result;
ResNet50 does not override its abstention rules. For example, an ImageNet
“tiger cat” prediction is a domestic-cat appearance label, not *Panthera tigris*,
and “lynx” alone does not resolve one of the four catalogue lynx species.

The official file is `resnet50-0676ba61.pth`, SHA-256
`0676ba61b6795bbe1773cffd859882e5e297624d384b6993f7c9e683e722fb8a`.
`resnet.py` checks that digest before restricted `weights_only=True` loading,
including when the file was already cached. Offline startup fails if it is
missing or altered. Only this fixed official checkpoint is accepted.

[BioCLIP 2.5 Huge](https://huggingface.co/imageomics/bioclip-2.5-vith14) is a
biodiversity-trained ViT-H/14 model. It supports zero-shot comparison with
scientific, vernacular, and taxonomic descriptions and reports improvements
on biological recognition benchmarks. This is a better fit for this task's
vocabulary; it is not evidence of a validated accuracy rate for this application.
The model is a research output, and its long-tailed training distribution can
favour well-represented taxa.

A biodiversity-only ranker will always choose something from a cat-only list.
Therefore the application first uses general-domain
[OpenCLIP ViT-B/32](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K)
to compare felids with 70 other animal/object labels and 10 non-photographic or
unclear-image descriptions. This reduces forced cat classifications but does
not constitute a general out-of-distribution detector.

Exact revisions:

- BioCLIP 2.5 Huge: `6e3d04e3d6522012c88181085c5ae666e14c45cd`.
- OpenCLIP ViT-B/32: `1a25a446712ba5ee05982a381eed697ef9b435cf`.

`model.py` is the source of truth for the architecture, labels, prompt ensemble,
and revisions. The downloaded configuration is checked against the selected
OpenCLIP architecture. Standard model preprocessing is used, including its
normalization and bicubic resize. Both models are frozen and run in inference
mode; the app does not train or fine-tune them.

## Embeddings

For the cat gate, each species uses two common-name prompts; a generic cat
prompt group is also included. Non-cat alternatives include dogs, foxes,
hyenas, civets, other animals, people, plants, objects, blanks, drawings,
paintings, toys, and unclear photos. Each prompt is embedded and normalized;
embeddings in a group are averaged and normalized again.

Species ranking uses three prompts per catalogue entry: common plus scientific
name, scientific name alone, and the taxonomic lineage plus common name.
Embeddings are computed once at startup. No geolocation, GPS, user identity,
filename, or inferred habitat is used as a classification prior.

Each photograph is encoded in two views: the model's ordinary center crop and a
square-padded full-frame view. Their normalized embeddings are averaged and
normalized. This helps retain animals near image edges without adding an object
detector. It still does not reliably handle multiple animals or tiny subjects.

## Acceptance and abstention

Let `cat` be the highest cosine similarity among cat gate descriptions and
`other` the highest among its alternatives. Let `s1` and `s2` be BioCLIP's two
highest species similarities. The policy in `decision.py` is:

```text
if any supplied score is non-finite:
    fail inference safely
elif cat < 0.23 or cat - other < 0.015:
    no_match; return no species candidates
elif s1 < 0.20 or s1 - s2 < 0.015:
    uncertain; present alternatives without confirming a species
else:
    matched; present the closest visual match with caveats
```

The gate uses maxima rather than summing all cat scores, which would favour a
family simply because it has many candidate descriptions. Species ranking is
run only after the first gate passes. The API exposes the gate and species
margins for inspection, while the main interface explains the outcome in plain
language.

These are fixed, transparent **heuristics**, chosen conservatively for the
exercise, not calibrated thresholds from an independent validation set. They
were not adjusted to make the smoke-test examples pass. Raw cosine similarity
is not a probability; a high within-catalogue rank is not proof of identity.
The interface deliberately avoids a confidence percentage.

## Known limitations

The catalogue follows IUCN CCTF 2017. Taxonomic splits, hybrids, extinct cats,
non-catalogue species, and domestic breeds are not separately recognized. The
model is not a diagnostic tool and cannot establish an individual's ancestry.
Some accepted taxonomic distinctions require geographic or genetic evidence
that a single photograph does not contain.

A cat-shaped toy or unfamiliar non-cat can still pass the gate. A real cat can
be rejected when it is small, obscured, blurred, oddly lit, or outside typical
training images. The gate's alternatives are finite. Multiple cats or species
can be merged into one whole-image embedding. Source photos may have appeared
in training, and the supplied demonstration set is too small to quantify these
failure rates.

In the recorded smoke check, a caracal photograph placed the African golden
cat slightly ahead of the caracal. The narrow margin correctly produced
`uncertain`. A Pallas's cat photograph also stayed uncertain despite having the
expected species first. These are useful demonstrations of abstention, not
failures to hide by lowering thresholds. See [testing.md](testing.md).

For stronger scientific claims, build a separate labelled evaluation set
covering all catalogue species, hard lookalikes, camera domains, difficult
negatives, and out-of-scope taxa. Report accepted prediction accuracy, coverage,
non-cat false acceptance, per-species confusion, and uncertainty behaviour.
Fit any thresholds on a validation split and report results on an untouched
test split. Record source overlap and taxonomy versions.
