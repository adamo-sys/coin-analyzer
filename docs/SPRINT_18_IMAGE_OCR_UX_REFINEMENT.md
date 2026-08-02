# Sprint 18 — Image and OCR UX Refinement

## Purpose

This document records bounded presentation decisions for the locked Sprint 18
roadmap. It does not change, renumber, or extend that roadmap.

## Zoom and Contrast Controls

### Existing boundary

`OCRCandidatePreview` carries an already-created Tk-compatible `image` from an
injected preview resolver. The resolver owns pixel decoding, transformation,
Tk-image creation, and image lifecycle outside the candidate-review dialog.
The dialog must not decode files, import an image-processing library, or infer
subclass-specific Tk transformations.

### Approved callback contract

The preview contract gains one optional callback:

```python
AdjustedPreviewRenderer = Callable[[float, float], object]
```

`OCRCandidatePreview.adjusted_image_renderer` is either that callback or
`None`. Existing preview resolvers remain valid because the field defaults to
`None`.

The callback receives zoom and contrast multipliers in that order and returns
a Tk-compatible display image. It is invoked only with validated values inside
these closed ranges:

| Adjustment | Minimum | Default | Maximum | Step |
| --- | ---: | ---: | ---: | ---: |
| Zoom | 0.50× | 1.00× | 3.00× | 0.25× |
| Contrast | 0.50× | 1.00× | 2.00× | 0.10× |

### Ownership and lifecycle

- The dialog owns transient adjustment values keyed by exact current coin,
  image role, and preview reference.
- Obverse and reverse state is independent. Different references also receive
  independent state.
- Adjustment state and adjusted image references exist only for the dialog
  lifetime.
- The dialog retains original and currently displayed image references to
  prevent premature Tk image disposal.
- The resolver retains ownership of pixels and the rendering implementation.
- No transformed image, preference, or adjustment state is persisted.

### Rendering behavior

- A preview with no callback continues to display its original image, and all
  adjustment controls for that preview are visibly disabled.
- A preview with no original image has no adjustable visual state.
- The dialog validates and bounds every requested adjustment before invoking
  the callback.
- A successful callback result becomes the displayed image and commits the
  proposed transient values.
- A callback failure or `None` result leaves the prior valid values and display
  image unchanged and surfaces the existing bounded dialog error state. It
  does not create a new error hierarchy.
- Reset deterministically restores 1.00× zoom, 1.00× contrast, and the exact
  original `image` without invoking the callback.
- Candidate evidence, source reports, resolver-owned pixels, and review
  decisions are never mutated.

### Presentation and accessibility

Each available side presents focusable controls for zoom out, zoom in,
contrast down, contrast up, and reset. A focusable status label communicates
the current zoom and contrast values. Native button disabled state communicates
that legacy or unavailable previews cannot be adjusted. The existing
responsive side-by-side layout continues to stack panels at narrow widths.

### Exclusions

This unit adds no crop adjustment, candidate highlighting, workflow keyboard
shortcuts, batch review, OCR rerun, image normalization, persistence, global
preference, file decoding, Pillow dependency in the dialog, source mutation,
or collection-data change.

## Crop Adjustment

### Normalized crop contract

Crop adjustment uses an immutable normalized rectangle:

```python
@dataclass(frozen=True, slots=True)
class NormalizedCrop:
    left: float
    top: float
    right: float
    bottom: float
```

Every coordinate must be an exact finite `float` inside the closed interval
`0.0` through `1.0`. The rectangle must satisfy `left < right` and
`top < bottom`, with a minimum retained width and height of `0.20`. The default
is the complete image: `NormalizedCrop(0.0, 0.0, 1.0, 1.0)`.

User edge controls move in normalized `0.05` steps. They clamp at the image
boundary and at the minimum retained dimensions, so an invalid crop is never
submitted to a renderer. Direct reconstruction still rejects wrong types,
booleans, NaN, infinity, out-of-range coordinates, inverted rectangles, empty
rectangles, and undersized rectangles.

### Supplemental renderer contract

The existing two-argument renderer remains unchanged:

```python
AdjustedPreviewRenderer = Callable[[float, float], object]
```

Crop-capable previews may additionally provide:

```python
CropAdjustedPreviewRenderer = Callable[
    [float, float, NormalizedCrop],
    object,
]
```

`OCRCandidatePreview.crop_adjusted_image_renderer` defaults to `None`, so
legacy previews and zoom/contrast-only resolvers remain source-compatible.
When the crop-capable renderer is present, it receives validated zoom,
contrast, and crop values for every visual adjustment. This makes the crop
compose deterministically with zoom and contrast without overloading or
changing the existing callback.

Previews without the crop-capable renderer retain their existing zoom and
contrast behavior and show disabled crop controls. A crop-capable renderer may
also provide zoom and contrast rendering without the older callback.

### State, rendering, and reset

- Crop state is dialog-local and keyed by exact coin, image role, and preview
  reference alongside zoom and contrast state.
- Obverse, reverse, and distinct references remain independent.
- Pixel decoding, cropping, transformation, Tk-image construction, and source
  image lifecycle stay with the resolver.
- A successful callback commits all proposed presentation values and retains
  the returned image reference.
- A callback exception or `None` result keeps the prior crop, zoom, contrast,
  and displayed image unchanged.
- Reset restores the full-image crop, 1.00× zoom, 1.00× contrast, and the exact
  original image without invoking either callback.
- No crop values, adjusted images, or display preferences are persisted.
- Source images, OCR evidence, review candidates, and collection data are never
  mutated.

### Interaction and accessibility

Each crop-capable side exposes native focusable buttons to move the left, top,
right, and bottom edges inward or outward. A focusable value label communicates
all four normalized coordinates. The crop controls use native disabled state
when unsupported and use a compact two-column layout inside each responsive
side panel.

### Exclusions

This unit adds no drag canvas, automatic crop inference, destructive editing,
OCR rerun, image normalization, persistence, candidate highlighting, workflow
shortcut, batch review, or image-processing dependency inside the dialog.

## Candidate Highlighting

### Selection ownership

Candidate selection remains owned exclusively by
`OCRCandidateReviewModel.current_candidate`, which derives from the model's
existing navigation index. The dialog does not introduce a second selection
value, selectable image state, or persisted highlight state.

The candidate detail fields describe the current candidate. Its exact preview
reference is the selected visual unit. Other same-coin side previews may remain
visible as related image evidence, but they are not independently selectable.
When multiple candidate references exist for one image role, the existing
side-preview resolver continues to place the current candidate's reference in
that role's panel.

### Presentation behavior

- Exactly the preview panel representing the current candidate uses the
  selected-candidate style and the explicit text "Selected candidate
  reference."
- Other visible side panels use the text "Related image evidence (not
  selected)."
- Selection uses a stronger border, bold panel label, and explicit status text
  so it does not depend on color alone.
- Selection styling is persistent presentation state and is distinct from the
  native focus indication on focusable image, status, and adjustment widgets.
- Navigation rebuilds the visible panels from the new current candidate, so
  the highlight moves immediately without duplicating selection ownership.
- Empty review state exposes no selected candidate. An unavailable preview may
  still be identified as selected because selection describes the candidate,
  not image availability.
- Selection never implies approval, rejection, correction, deferral, ranking,
  or confidence. Human-review state remains communicated separately.

### Compatibility and ownership

Highlighting does not change preview resolution, crop, zoom, contrast, or
display-image retention. Existing presentation adjustments remain keyed by
exact coin, side, and preview reference and survive navigation as before.
Paired, single-side, legacy-preview, unavailable-preview, narrow-layout, and
empty-state behavior remains intact.

This unit adds no public API, candidate or preview contract, renderer callback,
pixel processing, persistence, candidate reranking, evidence mutation, review
decision change, source-model mutation, or collection-data change.

## Batch Review Queue and Progress

### Batch boundary and action unit

The batch is the complete deterministic candidate queue from the aggregated
`OCRMetadataReport`. The existing presenter order remains authoritative and
`source_coin_id` provides coin-aware grouping within that queue. The dialog
does not create, filter, reorder, or own a second queue.

One current OCR field candidate remains the only action unit. Its existing
identity, the `OCRCandidateReviewModel` navigation index, and the exact preview
reference selected for that candidate remain unchanged. Batch presentation
does not introduce multi-selection, candidate membership, or a coin-level
decision.

### Derived progress and decision state

Queue progress is derived from the authoritative candidate tuple and complete
review mapping. It reports total, reviewed, remaining, approved, corrected,
rejected, and deferred candidate counts, plus the current overall position and
the current candidate's position within its `source_coin_id` group. Replacing
a decision changes its category count without changing the reviewed count.
Navigation changes only current-position presentation.

Unresolved conflict count comes from the existing pure review-session
controller and consolidation behavior. Equal accepted values remain agreed;
different accepted values for the same coin and field remain an unresolved
conflict until the separate conflict-review workflow resolves them. The batch
presentation does not infer, suppress, or resolve conflicts itself.

Queue-reviewed and domain-complete are distinct states:

- **Queue reviewed** means every candidate has a review, including `DEFER`.
- **Domain complete** means the queue is reviewed, no review is deferred, and
  the existing session projection has no unresolved conflict.

An empty queue reports zero counts and no current coin. Reaching either state
does not navigate, close, persist, complete, abandon, or invoke another
workflow command.

### Presentation, accessibility, and compatibility

The dialog presents a compact focusable text summary with explicit counts and
readable queue/domain-state language. It remains wrapping and readable at
narrow widths, does not rely on color, and does not replace native focus or
current-candidate highlighting.

Approve, Correct, Reject, Defer, close-callback, and keyboard-shortcut paths
remain unchanged. Crop, zoom, and contrast state remains keyed by exact coin,
side, and preview reference. Paired, single-side, multiple-reference, legacy,
unavailable, and empty preview states remain compatible.

### Exclusions

This unit adds no bulk action, multi-selection, checkbox, select-all,
automatic advancement, automatic close, Finish/Cancel staging, baseline
snapshot, transaction, confirmation dialog, persistence integration,
collection mutation, conflict resolution, candidate filtering or reranking,
coin-level action, new shortcut, OCR rerun, source-image mutation, evidence
editing, confidence change, renderer contract, or pixel processing.

## Final OCR Candidate Review Accessibility Pass

### Focus ownership and lifecycle

Keyboard focus remains dialog-local presentation state and never becomes a
second candidate, preview, decision, confidence, or conflict selection. When a
candidate exists, the dialog schedules initial focus on Reason after idle
layout. An empty queue schedules initial focus on Close.

Previous and Next render the new current candidate and then focus Reason, so a
destroyed preview descendant cannot retain focus. A successful decision keeps
the current candidate and focuses its corresponding visible Approve, Correct,
Reject, or Defer button. A failed Correct action with a missing correction
focuses Correction; other decision-validation failures focus Reason. Image
adjustment operations do not rebuild their panel and retain the invoking
control's native focus.

The dialog remains transient and non-modal. It does not force focus to the
parent or application root, navigate after a decision, or add another current
selection owner.

### Traversal and shortcuts

Only enabled interactive controls participate in normal Tab and Shift+Tab
traversal. Passive summary, status, image, adjustment-value, crop-value,
validation, and shortcut-help labels remain visible readable text but are not
Tab stops. Disabled entries, decision controls, and preview-adjustment controls
are excluded from traversal. Native ttk focus styling remains authoritative;
the dialog adds no custom focus theme.

Shortcut help remains permanently visible passive text and has no popup
lifecycle. The existing shortcut mapping, availability checks, key-repeat
protection, and dialog-local binding lifetime remain unchanged. Workflow
shortcuts continue to yield to editable or natively adjustable widgets. Escape
is the narrow exception for the dialog's Correction and Reason entries and
ordinary buttons: it follows the existing Close path exactly once. A native
widget with its own meaningful Escape operation retains that operation.

### Readable capability and reset state

Every preview states whether zoom and contrast adjustments are available and
whether crop adjustment is available. Unsupported legacy or unavailable
previews include a readable explanation instead of relying only on disabled
button styling. Reset is labelled "Reset crop, zoom, and contrast" and retains
the established exact-original-image behavior.

Existing candidate, coin, field, reference, evidence, confidence, review,
queue, completion, deferment, conflict, crop, zoom, and contrast text remains
authoritative. The dialog does not claim live-region announcements or
guaranteed screen-reader narration.

### Scrollable and responsive layout

The existing dialog content is hosted in a dialog-local `Canvas` with a
keyboard-operable vertical `ttk.Scrollbar`, following the repository's current
desktop convention. No global mouse-wheel or application-wide event binding is
introduced. A private focus-visibility helper scrolls an off-screen focused
descendant into view.

Readable wrap widths derive deterministically from the current viewport. The
existing two-column preview presentation remains at normal widths and stacks
below 620 pixels. A reasonable minimum window size supplements, but does not
replace, vertical overflow access. Scrolling changes no widget ownership,
candidate order, focus order, preview rendering, or source state.

### Manual Windows verification boundary

Headless tests may verify focus-target selection, widget configuration,
bindings, readable labels, scroll helpers, and unchanged domain behavior. They
do not prove Windows Narrator announcements, Windows high-contrast rendering,
native focus-ring appearance, exact platform traversal, or high-DPI layout.
Those behaviors require later manual verification at 100% and 200% scaling in
normal and narrow or short layouts. Manual observations must not be described
as toolkit guarantees.

### Preserved boundaries

This pass changes no public API, callback, renderer contract, image pixels,
crop, zoom, contrast, preview-reference matching, OCR source model, candidate
ranking, review decision, conflict rule, persistence timing, collection data,
or application-wide event routing. It adds no bulk action, multi-selection,
automatic advancement, automatic close, save, completion, external
accessibility dependency, custom theme, or application-wide accessibility
framework.
