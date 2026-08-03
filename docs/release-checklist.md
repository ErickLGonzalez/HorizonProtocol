# Release Checklist

This is the ordered checklist the repository owner runs before tagging a
release. It is process documentation, not a protocol spec - it carries no
gates of its own, but see section "Registered falsifiers" below for the
two failure modes this checklist itself must never silently permit.

## Before tagging

1. `python3 scripts/run_all.py` - must print `ALL HORIZON GATES GREEN`.
2. `python3 scripts/validate_certificates.py` - must exit 0.
3. CI (`.github/workflows/gates.yml`) green on `main`, across the full
   Python 3.9 / 3.11 / 3.12 matrix.
4. `git tag -a v0.1.0 -m "H1-H5 complete; all gates green; preregistration freeze"`
5. `git push origin v0.1.0`

## The tag is the preregistration freeze

Once `v0.1.0` is pushed, every threshold, gate, and registered falsifier
in `docs/h1-spec.md` through `docs/h5-spec.md` is **frozen as of that
commit**. This is a preregistration discipline, not a suggestion:

- A later change to a frozen parameter, gate, or falsifier requires a
  **new tag** (e.g. `v0.2.0`) and an **erratum note** filed in `docs/`
  explaining what changed and why.
- Silently editing a frozen spec or certificate after the tag - without a
  new tag and an erratum - is itself a process defect (see FA3 below).
- "Additive only" continues to apply after the tag exactly as it did
  before it: new sprints add new modules and certificates; they do not
  rewrite the frozen ones.

## Known schema asymmetry (not a defect)

`certificates/h1_certificate.json` predates the `seeds[]` field
introduced starting with H2. Under the additive-only discipline governing
this repository, `scripts/run_h1.py` is not retrofitted to add a field it
never had, so `scripts/validate_certificates.py` does not list `seeds` as
a mandatory schema-family field - it validates it when present (H2-H5)
but does not require it (H1). This is a recorded asymmetry between H1 and
later sprints, not something the validator silently overlooks: it is
documented here precisely so it cannot be mistaken for validator drift.

## License choice

Apache-2.0 was chosen (patent grant + permissive) over MIT for a
spec/protocol project where downstream implementers benefit from an
explicit patent grant. This choice is swappable: if the repository owner
prefers MIT, replacing `LICENSE` and this note is the entire change - no
protocol code depends on the license text.

## Registered falsifiers

- FA1: CI passes while `python3 scripts/run_all.py` fails locally on the
  same commit → CI is misconfigured; fix before any tag.
- FA2: `scripts/validate_certificates.py` passes while a file under
  `horizon/` differs from the hash a certificate claims for it → validator
  defect; the validator's entire purpose is to catch exactly this.
- FA3: a frozen spec, gate, or certificate is edited after a tag without
  a new tag and an erratum note in `docs/` → process defect, not a code
  defect; the next release must correct the record.
