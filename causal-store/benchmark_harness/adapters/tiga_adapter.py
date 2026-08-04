"""Adapter: neutral trace -> Tiga.  [documented stub - not buildable in
this environment]

Tiga (2025) is the nearest conceptual competitor - also clock-based - but
is a research prototype with no stable public client library or
packaged release. Per the design doc's own instruction ("If Tiga is not
cleanly buildable/deployable, report that and proceed with the others
rather than reporting a half-configured competitor"), this adapter
always reports itself unavailable rather than fabricating a build.

If a future live run has Tiga's source built and reachable, replace
`setup()` below with a real client and remove this docstring's
disclaimer - do not leave this stub silently in place once a real
integration exists (a stale "unavailable" would then be a false
negative, the mirror image of the false-positive risk this file exists
to prevent).
"""
from .base import Adapter, AdapterUnavailable


class TigaAdapter(Adapter):
    name = "tiga"

    def setup(self, regions):
        raise AdapterUnavailable(
            "tiga: no stable public client library or packaged release; "
            "building requires cloning and compiling the research "
            "prototype from source, which this harness does not automate. "
            "See docs/benchmark-harness-spec.md's Tiga section for the "
            "design doc's own guidance: report this gap and proceed with "
            "the other competitors rather than half-configuring Tiga.")
