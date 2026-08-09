# Source testimony and interpretation

Petrucci keeps written source facts separate from editorial interpretation.
`petrucci.core.source.build_source_document()` currently projects imported FT3
mensuration and proportion signs into renderer-independent records with stable
IDs, source order, bar, staff, and voice coordinates.

`DiplomaticSign.written_value` records what the source says. The corresponding
`EditorialDecision` records the effective mensuration or proportion without
mutating that testimony. Rebuilding with the same `document_id` is deterministic.

This is deliberately a supported subset, not a general mensural claim.
Coloration, ligatures, dot meaning, ficta, interpreted onset/duration, and
alternative scholarly decisions remain explicit backlog items. Terminal and
LilyPond renderers continue to consume the established notation model; no SVG
or second publication geometry backend is introduced.
