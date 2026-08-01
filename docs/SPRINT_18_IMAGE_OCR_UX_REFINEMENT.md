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
