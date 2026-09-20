"""Canonical application build provenance metadata.

`APPLICATION_VERSION` identifies the application build that creates durable
runtime provenance. Going forward, published releases use their exact public
semantic-version tag; unreleased main-line development uses the latest public
release plus ``+dev``. Historical internal v8.x/v9.x milestone labels are not
current runtime provenance identifiers.
"""

APPLICATION_VERSION = "v1.3.0-rc1"
