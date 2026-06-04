# Ant 3D Workbench Architecture Notes

> Working name: **Ant 3D Workbench**
>
> Tagline:
> Open-source 3D annotation for ant morphology: STL surface labeling, TIF volume segmentation, and model-assisted curation for AntScan-style micro-CT datasets.

## Purpose

This folder is the working design space for the Ant 3D Workbench rearchitecture.

The current TaxaMask codebase grew from a 2D taxonomy-image annotation workflow with PDF literature extraction, project image masks, SAM/Blink-assisted annotation, training, and dataset export. The new direction is broader and more data-centered: use high-quality STL and TIF micro-CT datasets, especially AntScan-style datasets, as the main foundation for morphology annotation, model training, and automated curation.

These notes are intentionally separate from the root README, changelog, and LLM context. They are for early-stage architectural discussion, design decisions, and implementation checklists before the product direction is stable enough to become public-facing documentation.

## Current Design Status

The first requirements-alignment pass has moved into an initial implementation landing. This folder still remains the design and implementation-planning space, while the root `README.md`, `TaxaMask使用手册.md`, `CHANGELOG_zh.md`, and `LLM_CONTEXT_DETAILED.md` now describe the current user-facing and handoff state.

Current landed state as of 2026-06-04:

- The visible product name remains `TaxaMask`; `AntSleap` remains the internal Python package name.
- Startup now opens the TaxaMask Agent Center, with vendored Ant-Code embedded in the main area and stacked 2D/STL + TIF workflow cards on the right.
- 2D/STL and TIF are separate workflows and project systems.
- STL currently means rendered 2D views imported into the existing Labeling Workbench, not direct 3D mesh painting.
- TIF uses independent material-ID volume labels, sidecars, train-ready checks, and a separate TIF backend contract.
- TIF 3D preview now defaults to offscreen GPU rendering into a normal Qt display widget, with legacy embedded `QOpenGLWidget` kept out of the default path to reduce Ant-Code WebEngine / Qt Quick composition conflicts.
- 2D/STL VLM first-mile preannotation now uses grid-free VLM input images and current-input-image pixel boxes, which is the preferred route for MIMO/domestic multimodal batch drafting.
- 2D/STL daily annotation uses the Labeling Workbench with parent-part annotation, child-part annotation, Locator/SAM, Blink route experts, and PDF-derived literature trait lookup.
- PDF is evidence/provenance and Agent/headless workflow, not the primary visual workbench. It now separates accepted figures from needs-review figures, structures PDF text into `taxon -> part -> description`, and defaults local run artifacts to `TaxaMask_outputs/`.
- Locator/SAM no longer load at startup or when entering TIF; they preload when entering 2D/STL and remain alive when returning to the Agent Center.
- `ANTCODE.md` provides the highest-priority always-on TaxaMask Agent protocol. `.lab-agent/memory.md` and `.lab-agent/skills/taxamask-workflows/SKILL.md` provide short memory and an expandable workflow card so routine tasks do not require loading this entire design folder.

Primary Chinese design documents:

- `需求对齐_zh.md`: confirmed product positioning, STL/TIF split, AMIRA compatibility boundary, TIF storage direction, backend boundary, and PDF module repositioning.
- `TIF项目结构实施设计_zh.md`: first implementation design for the independent TIF project schema, sidecar layout, specimen records, material map, review status, and train-ready checks.
- `AMIRA导入适配实施设计_zh.md`: first implementation design for read-only AMIRA import based on the provided `.hx + .resampled + .labels + raw .tif` sample structure.
- `TIF后端契约_v1_实施设计_zh.md`: first implementation design for the independent TIF external backend contract covering `prepare_dataset`, `train`, `predict`, model manifests, prediction outputs, and safety rules.
- `TaxaMask_Agent侧栏与PDF_Skill设计_zh.md`: startup-center Ant-Code Agent design, using the main start-center area for the embedded Ant-Code Dashboard and a right rail for 2D/STL and TIF workflow shortcuts.
- `TaxaMask_AntCode项目记忆与对接手册_zh.md`: detailed operating handbook for the embedded Ant-Code agent, paired with `.lab-agent/memory.md` so common TaxaMask tasks do not require rediscovering the codebase from scratch.
- `VLM第一公里预标注方案_zh.md` and `VLM第一公里预标注实施记录_zh.md`: current 2D/STL VLM preannotation behavior, including the 2026-06-04 grid-free pixel-coordinate route.
- `TIF_GPU体预览实施记录_zh.md`: current TIF 3D preview behavior, including offscreen GPU rendering, render modes, ROI high-detail viewing, and remaining volume-standardization limits.

## Product Direction

Ant 3D Workbench should become a local, open-source research workbench for biological morphology datasets, starting with ant morphology.

Core positioning anchor:

> Ant 3D Workbench turns AntScan-style STL/TIF micro-CT morphology data into structured research assets that can be annotated, reviewed, exported for training, and iteratively improved through model-assisted pre-annotation.

The main workflow remains an annotation iteration loop:

```text
manual annotation
-> human review
-> train a rough auto-annotation model
-> model-assisted pre-annotation on more data
-> human correction and review
-> retrain
-> repeat until the model becomes practically useful
```

For ant morphology, the first surface-annotation layer should stay aligned with the existing workbench philosophy: the main workbench handles large, stable regions first, while small parts and fine local structures should be handled by specialized refinement workflows such as Blink, route-appointed experts, or future surface/volume expert tools.

The main users are expected to include:

- researchers working with AntScan-style ant STL and TIF micro-CT data;
- researchers annotating external and internal morphology from 3D scans;
- users who need STL surface labels, TIF/volume label fields, AMIRA-style material IDs, and nnU-Net/MONAI-style training exports;
- taxonomy and morphology researchers who want model-assisted annotation and auditable data curation rather than only manual mesh or slice labeling.

The project may still preserve the older TaxaMask 2D/PDF capabilities, but they should no longer define the primary product flow.

## Core Modes

Confirmed design principle:

- STL and TIF should be presented as two switchable primary interfaces.
- Keep the current open-project style rather than forcing a new monolithic workspace model in the first rearchitecture stage.
- STL and TIF should be separate project/workspace types, not two heavy data domains stored inside one large project JSON.
- The two project types may refer to the same biological specimen names or source datasets, but they serve different research systems: external morphology for STL-derived views and internal structure/volume segmentation for TIF stacks.
- Separating them prevents the project JSON from becoming large, ambiguous, and operationally fragile.
- STL Surface Mode should reuse and evolve the existing annotation workbench plus Blink/expert workflow for large-structure and small-part annotation.
- STL Mode should work on already-rendered multi-view 2D images generated from STL/mesh assets, not require direct 3D mesh surface painting as the first implementation target.
- These rendered STL-derived views can be extremely high resolution, up to 64K, so the interface and training path must treat them as high-value 2D morphology assets.
- STL project import should group rendered views into specimens by filename naming rules. Rendered view files include a stable specimen number, such as a project/specimen ID, plus a fixed exported view name.
- STL rendered view types are fixed by the batch export workflow. The first design target can assume a fixed set of exported views, such as the 10-view batch generated from STL assets.
- STL training can keep image-level random train/validation/test splitting for the normal workflow. Specimen-level holdout is not mandatory for the first implementation because independent new-specimen validation can be performed by importing a separate specimen when needed.
- The existing STL-derived 2D training framework should not be heavily reworked; it is already a partially validated route. The rearchitecture should preserve the current Labeling Workbench, Blink, Locator/SAM, route-appointed expert, and model-iteration logic where possible.
- TIF Volume Mode is a different annotation mode and should not force the existing polygon-mask workbench onto volume data.
- TIF Mode should annotate one slice at a time in the interface, while treating a fully labeled specimen volume as the effective training unit.
- TIF Mode should be built as a new AMIRA-style annotation workbench. It does not need Blink-style small-part assistance in the first design target.
- TIF label categories must be independent from STL label categories because STL projects target external morphology and TIF projects target internal structures.
- TIF training should not inherit the STL/TaxaMask three-main-part locator setup. The TIF workflow should use its own material/label map and volume-segmentation training logic.
- TIF input should first target a single complete TIF file that contains the full stack, not a folder of many slice files.
- TIF Mode should not be hardcoded to micro-CT only. It must be able to represent slice-TIF datasets from different imaging modalities, including confocal and micro-CT.
- Existing AMIRA-annotated confocal brain-region datasets are an important source dataset and must be treated as a required compatibility target.
- The observed AMIRA sample contains a raw multi-page `.tif`, an Amira project `.hx`, a binary AmiraMesh `.labels` file, a `.MaterialStatistics` file, a `.surf` surface file, and a `.resampled` volume. The first AMIRA adapter should treat `.labels` material/label-field import as a priority and use `.hx`/statistics files as metadata sources where useful.
- First-stage AMIRA compatibility should be designed around the provided sample structure. In that sample, the `.hx` project connects the `.labels` label field to the `.resampled` image volume, so `.resampled + .labels` is the annotation-aligned pair.
- The original raw `.tif` should be preserved as source/provenance when present, but existing AMIRA labels should be overlaid on the AMIRA-connected `.resampled` volume rather than blindly overlaid on the raw `.tif`.
- AMIRA-derived label volumes may not have the same dimensions as the original raw TIF because of resampling. TIF project import must explicitly validate original volume shape, label volume shape, slice count, and alignment assumptions instead of silently assuming they match.
- The first TIF annotation interaction should prioritize fast brush painting and erasing over polygon-mask editing. Holding a modifier such as Ctrl for erase should be considered a core speed feature.
- TIF auto-annotation should use an external backend interface that can host multiple model families. nnU-Net v2 may be one candidate, but the architecture must not lock the workflow to nnU-Net.
- Model predictions must never overwrite human-reviewed labels by default. Prediction import should create draft/candidate label volumes for unlabeled or explicitly selected targets, and any promotion to training truth must require human review or an explicit accept action.
- Existing AMIRA-labeled source datasets only need read compatibility in the first implementation. The project does not need to modify or write back to the original AMIRA files.
- Edited TIF labels should avoid AMIRA-native write-back in the first implementation. The preferred open-community sidecar target is OME-Zarr/OME-NGFF because it is designed for large bioimaging volumes and supports associated label images. Simpler array files may still be used only as temporary implementation artifacts if needed.
- TIF model backends must be separate from the current STL/2D external backend and prediction schema. STL and TIF are independent systems and should not share the same backend contract.
- The old PDF Processing panel should be removed from the primary interface; PDF capabilities can remain as agentic/headless literature-evidence workflows.
- A new dedicated TIF module is needed for AMIRA-style label fields and 3D-reconstructable volume annotations.

### 1. STL-Derived Surface View Mode

STL-Derived Surface View Mode is for surface-structure annotation on rendered multi-view 2D images generated from STL/mesh assets.

Main responsibilities:

- load or register STL-derived rendered views for a specimen;
- label external morphology regions on high-resolution rendered surface views;
- support large, stable ant structures first, such as head, mesosoma, and gaster;
- leave small parts and fine local structures to specialized expert/refinement workflows rather than making them the first surface-mode requirement;
- connect surface labels to specimen metadata and taxon information;
- reuse the current workbench and Blink-style expert workflow where possible;
- optionally preserve links back to the source STL/mesh asset when those links are available.

### 2. TIF Volume Mode

TIF Volume Mode is for continuous slice stacks and voxel/pixel label fields.

Main responsibilities:

- provide a dedicated volume-annotation interface rather than using the existing 2D polygon canvas as the core editor;
- load a complete TIF/TIFF stack file as a specimen volume;
- when importing existing AMIRA projects, distinguish the original source volume from the annotation-aligned working volume, such as `.resampled`;
- present and edit the volume slice by slice;
- treat a fully annotated volume, such as a fully labeled ant brain, as the meaningful training sample for volume segmentation;
- support AMIRA-style label-field semantics, where each pixel/voxel stores a material ID;
- import/export or otherwise interoperate with AMIRA-derived annotation datasets and material/label definitions;
- preserve material mappings, colors, label names, voxel spacing, slice order, and orientation metadata;
- validate raw-image and label-volume dimensions and warn when AMIRA resampling or shape mismatch is detected;
- support internal structures such as brain regions, muscles, glands, internal skeletal parts, and other volume-visible structures;
- keep TIF material labels independent from STL taxonomy/locator-scope labels;
- support brush-based painting and fast erase interaction as the primary manual correction tools;
- support brush-size adjustment, material/color selection, undo/redo shortcuts such as Ctrl+Z, brightness/contrast controls, and overlay transparency controls;
- keep review status simple in the first implementation, such as not started, in progress, fully annotated, reviewed, and train-ready;
- export volume labels for AMIRA/Avizo-style review and multiple model-training backends;
- import model predictions back as reviewable label volumes.

### TIF Project Storage Direction

Confirmed storage direction:

- Keep the TIF project JSON lightweight. It should store specimen IDs, file paths, material maps, review/training status, model records, and provenance.
- Store large image and label volumes as sidecar files rather than embedding them in JSON.
- Preserve original AMIRA files as read-only source data when importing existing labeled datasets.
- For manual edits or reviewed predictions, prefer an OME-Zarr sidecar as the long-term project storage format instead of requiring AMIRA-native write-back in the first implementation.
- Export adapters can additionally write OME-TIFF, NIfTI, NRRD, or backend-specific formats when needed for external tools or training frameworks.
- Keep separate layers for:
  - `manual_truth`: human-confirmed labels suitable for training;
  - `model_draft`: model-generated rough labels that are not training truth;
  - `working_edit`: the current editable copy during human correction.
- A TIF volume can be considered train-ready when its status says train-ready, the working image volume exists, a label volume exists, the material map exists, and the image/label shapes match.

Example project layout:

```text
tif_project/
├─ project.json
├─ specimens/
│  └─ 01-0101-02/
│     ├─ source/
│     │  └─ raw.tif
│     ├─ working/
│     │  ├─ brain.resampled
│     │  └─ working_volume.ome.zarr/
│     ├─ labels/
│     │  ├─ manual_truth.ome.zarr/
│     │  ├─ model_draft.ome.zarr/
│     │  └─ working_edit.ome.zarr/
│     └─ material_map.json
├─ models/
├─ exports/
└─ logs/
```

### TIF Model-Iteration Route

The TIF route should explicitly support modality adaptation rather than assume all TIF stacks look alike.

Confirmed research route:

```text
existing AMIRA-annotated confocal brain dataset
-> train an initial brain-region segmentation model
-> run that model on selected micro-CT TIF volumes
-> manually review and correct rough predictions
-> create the first reviewed micro-CT brain-region dataset
-> retrain or adapt models on reviewed micro-CT data
-> repeat until the micro-CT auto-annotation model becomes useful
```

The biological brain-region layout can be treated as a stable target concept, but the image appearance can differ strongly between confocal and micro-CT data. The model-adaptation layer must therefore account for grayscale range, saturation, edge clarity, contrast, and other modality-specific appearance differences.

### 3. Derived 2D / Review Mode

The existing 2D annotation workbench, SAM/Blink workflow, and image-mask exports can remain useful, but they should be repositioned as derived-image review and model-curation tools.

Likely use cases:

- inspect rendered STL views;
- review selected TIF slices or projection images;
- train or audit local expert models for visually separable substructures;
- maintain compatibility with existing TaxaMask projects during migration.

## Shared Specimen Registry

The new architecture should use specimen-centered organization inside each project type rather than only an image-list project.

Confirmed design principle:

- The user opens an STL project or a TIF project, and the main asset browser in that project should organize data by specimen.
- A specimen-centered browser keeps STL, TIF, derived images, annotations, predictions, and review state attached to the same biological individual.
- This is especially important for provenance: users should be able to quickly answer which ant a view, slice, label, description, model prediction, or review decision came from.
- Dataset-level training still uses many specimens at once. Specimen-centered organization is for asset clarity and traceability, not for limiting training to one specimen at a time.
- The specimen browser should be mode-aware rather than showing every STL and TIF asset at once. In TIF Mode, each specimen entry should expose its TIF stack/slices and volume-label state. In STL Mode, each specimen entry should expose its STL assets, derived views, and surface-label state.
- Import workflows can rely on matching naming conventions to group assets belonging to the same specimen, with later validation and manual correction.
- A specimen is identified by a stable project/specimen number, not by a long taxon name. Species or taxon details should be resolved through a separate master metadata table when needed.
- STL-derived view training should not use the specimen's species identity as a model input. The model learns where the target morphology parts are and how to segment them, not which ant species the specimen belongs to.
- Multiple rendered views from the same specimen can be grouped under one specimen entry for clarity. Training datasets may include many specimens or only a few specimens, but the label target remains morphology parts rather than specimen identity.
- For STL projects, grouping should primarily be automatic from filename conventions. The stable specimen number and fixed view name in each rendered image filename are enough to group views under the correct specimen in normal imports.

Each specimen record should eventually be able to connect:

- specimen ID;
- optional taxon name and rank resolved through a master metadata table;
- AntScan or other source metadata when available;
- STL/mesh asset paths;
- TIF stack or volume paths;
- voxel spacing, physical scale, orientation, and transforms;
- surface annotations;
- volume annotations;
- derived images and renderings;
- model predictions and review state;
- provenance, license, and citation information.

Within each project type, specimen-centered organization is what keeps assets, training exports, and literature evidence traceable to the same biological specimen. Cross-project linkage between an STL project and a TIF project should be optional and lightweight, based on shared specimen identifiers or import naming conventions rather than one combined project file.

## PDF / Literature Layer

The PDF module should not remain a primary visual workbench in the new architecture.

Rationale:

- PDF figure extraction was valuable when the project focused on taxonomy literature images.
- Extracted PDF figures are often compressed and low-resolution, making them weak training material for high-quality automated annotation.
- The new primary users working with STL/TIF micro-CT datasets likely do not need a large PDF-processing panel.
- PDF screening and figure extraction are batch workflows and are better suited to agentic tools or skills.

Recommended direction:

- move PDF screening/extraction into an optional agent skill or headless workflow;
- keep PDF results as literature evidence and provenance artifacts;
- keep only a lightweight GUI entry for reviewing imported evidence, source PDFs, captions, page numbers, and candidate provenance when needed.
- In the current implementation landing, PDF Processing is no longer part of the primary mode tabs. It remains available on demand through evidence/headless/Agent routes, with `File -> Open PDF Evidence Tools` as the GUI fallback.

## Early Architecture Sketch

```text
Ant 3D Workbench
├─ STL Project Type
│  ├─ specimen-centered browser
│  ├─ STL-derived rendered views
│  ├─ existing annotation workbench
│  ├─ Blink/expert refinement
│  └─ surface-view training exports
├─ TIF Volume Mode
│  ├─ specimen-centered browser
│  ├─ stack/slice viewer
│  ├─ AMIRA-style label field
│  ├─ material mapping
│  ├─ volume export/import
│  └─ independent TIF model backend adapters
├─ Optional Cross-Project Links
│  ├─ shared specimen identifiers
│  ├─ source dataset metadata
│  └─ provenance records
├─ Derived 2D Review Mode
│  ├─ existing polygon/mask review
│  ├─ rendered views
│  ├─ selected slices
│  └─ Blink/local expert review
├─ Training Backends
│  ├─ existing built-in Locator/SAM/Blink where still useful
│  ├─ existing STL/2D backend contract where still useful
│  ├─ independent TIF backend contract
│  └─ future nnU-Net, MONAI, or other volume-model adapters
└─ Literature Evidence Skill
   ├─ PDF screening
   ├─ figure/caption extraction
   ├─ multimodal review
   └─ provenance import
```

## Design Questions To Resolve

- What should the first specimen registry schema look like?
- What is the minimal shared specimen identifier scheme for linking separate STL and TIF projects when needed?
- What should the STL project schema look like?
- What should the TIF project schema look like?
- Which mesh format support is needed first: STL only, or also OBJ/PLY?
- Should TIF stack input support a multi-page TIF first, a folder of slice TIFs first, or both?
- How should AMIRA material mappings be represented locally?
- Which internal label-volume sidecar format should the TIF project use first?
- What should the independent TIF backend contract contain for training and prediction?
- How should STL surface labels be converted into TIF pseudo-label volumes, and what quality checks are mandatory?
- How much of the current 2D TaxaMask workbench should be retained unchanged during the first migration?
- What GUI layout best expresses the new product: mode switcher, project dashboard, or specimen-centered navigator?
- How should old PDF workflows be exposed after they move to an agent skill?

## Initial Execution Checklist

- [x] Define the first independent TIF project/specimen schema.
- [x] Decide the current top-level GUI structure: Agent Center start page, 2D/STL workflow, TIF Volume workflow, PDF evidence on demand.
- [x] Move PDF Processing out of the primary tab layout while preserving headless/evidence tools.
- [x] Register STL-derived rendered views into the existing 2D Labeling Workbench as the first STL route.
- [x] Implement TIF stack registration and AMIRA-style label-field storage.
- [x] Implement material mapping schema for volume labels.
- [x] Implement independent TIF external-backend/export/import contracts for multiple model families.
- [ ] Design STL-to-volume pseudo-label bridge and QC report.
- [x] Preserve existing TaxaMask 2D projects and route STL rendered-view registries into the Labeling Workbench.
- [x] Update public README, user manual, changelog, LLM context, and embedded Agent rules after the test branch result was accepted.
