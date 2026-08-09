# Romance Generation Ontology (RGO)

RGO is a creative-control ontology for prompting and evaluation. It is not a
replacement for a bookstore or library taxonomy.

- `romance_generation_ontology.v1.json` is the authoritative v1 catalog.
- Stable semantic IDs are permanent within a major version.
- Parents create a polyhierarchy; prompt and evaluation semantics inherit from
  all ancestors.
- Heat, consent, and darkness are intentionally separate facets.
- Thema and BISAC mappings are release metadata and never supply generation
  semantics.

External mapping versions:

- [Thema 1.6](https://ns.editeur.org/thema/en)
- [BISAC 2025 Fiction](https://www.bisg.org/fiction)

Only the small set of codes needed by this project is recorded. The complete
BISAC subject list is not copied into this repository.

Profiles resolve in this order:

```text
ontology defaults
→ inherited preset
→ story overlay
→ permitted scene overrides
```

The resolver emits one canonical `ResolvedCreativeProfile` with an ontology
hash and profile hash. Generation, judging, editing, and internal reporting use
that exact hash as the compatibility boundary.
