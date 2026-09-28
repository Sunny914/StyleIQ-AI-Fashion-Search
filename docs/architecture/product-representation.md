# ProductIQ — Product Attribute Ontology

**Phase:** 3 — Product Representation & Product Understanding  
**Step:** 3.2 — Product Attribute Ontology  
**Status:** Specification artifact  
**Version:** 1.0.0  
**Upstream:** Phase 2 — Data Engineering / Product Data Foundation  
**Downstream:** Phase 3.3 — Structured Product Representation

---

## 1. Purpose

The ProductIQ Product Attribute Ontology defines the controlled concepts used to describe fashion products after the Phase 2 data-engineering pipeline.

Its purpose is to establish a shared vocabulary and consistent semantics for product attributes before those attributes are used by structured product representations, lexical/BM25 retrieval, semantic product representations, structured filtering, ranking, and recommendations.

This ontology is a **representation contract**, not a machine-learning model and not an inference engine.

The ontology must represent information supported by the catalog. It must not invent product properties that are not present or reliably derivable from the source data.

---

## 2. Scope

This artifact covers:

1. `category_gender`
2. `product_type`
3. `color`
4. `pattern`
5. `material`
6. `fit`
7. `sleeve`
8. `neckline`
9. `product_features`
10. `style_attributes`

It also defines controlled attributes, open-text fields, normalized values, multi-valued attributes, coded colors, missing values, filtering, lexical representation, and semantic representation.

---

## 3. Upstream Data Contract

The ontology consumes the trusted output of Phase 2.

Phase 2 produced a canonical product catalog with engineered attributes. The attribute-engineering stage extracted controlled concepts from product descriptions/titles using a controlled vocabulary.

The ontology does **not** replace Phase 2 extraction logic. It formalizes the concepts for downstream representation.

```text
Phase 2 Data Engineering
          │
          ▼
Canonical Product Catalog
          │
          ├── canonical fields
          └── engineered attributes
                    │
                    ▼
            Phase 3.2 Ontology
                    │
                    ▼
         Structured Representation
```

---

## 4. Ontology Design Principles

### 4.1 Controlled vocabulary

Attributes such as product type, material, fit, pattern, and neckline use controlled concepts.

Example:

```text
product_type = shirt
```

rather than an arbitrary free-text category.

### 4.2 Preserve source truth

The ontology must not manufacture unsupported attributes.

If the catalog does not establish:

```text
occasion = office
season = summer
style = formal
```

these must not be added merely because they seem plausible.

Future AI/query-understanding inference must remain distinct from catalog ground truth.

### 4.3 Preserve useful granularity

Normalization should reduce meaningless variation without destroying useful fashion distinctions.

For example:

```text
navy_blue
light_blue
dark_blue
sky_blue
```

should not automatically collapse into `blue`.

### 4.4 Separate semantic meaning from metadata

Not every field should become semantic text or an embedding input.

```text
                    Product
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      Structured    Lexical      Semantic
      Attributes    Document     Document
          │            │            │
          ▼            ▼            ▼
       Filters       BM25       Embeddings
```

### 4.5 Missing does not mean unknown or none

A missing value means the current catalog representation does not provide that attribute.

```text
material = NULL
```

does not automatically mean:

```text
material = unknown
```

### 4.6 Multi-value attributes remain multi-valued

Where an attribute contains several verified concepts, all should be preserved.

Example:

```text
material = cotton|polyester
```

represents two material concepts.

---

# 5. Attribute Families

```text
Fashion Product
│
├── Classification
│   ├── category_gender
│   └── product_type
│
├── Appearance
│   ├── color
│   └── pattern
│
├── Garment Properties
│   ├── material
│   ├── fit
│   ├── sleeve
│   └── neckline
│
├── Features
│   └── product_features
│
└── Style
    └── style_attributes
```

---

# 6. Attribute Contract

Each ontology attribute is defined using:

| Property | Meaning |
|---|---|
| Name | Canonical attribute identifier |
| Family | Ontological category |
| Description | Meaning of the attribute |
| Type | Controlled categorical or other representation |
| Cardinality | Single or multi-valued |
| Vocabulary | Allowed/known concepts |
| Filterable | Whether structured filtering may use it |
| Lexical | Whether it may contribute to lexical search |
| Semantic | Whether it may contribute to semantic representation |
| Source | Where the value originates |
| Normalization | Rules required before downstream use |

---

# 7. Classification Attributes

## 7.1 `category_gender`

**Meaning:** Catalog-level gender classification supplied by the source dataset.

**Current values:**

```text
men
women
```

**Cardinality:** Single-valued.

**Uses:**

- Structured filtering: Yes
- Lexical representation: Yes
- Semantic representation: Yes
- Ranking features: Potentially

**Rule:** This is a catalog classification, not an inferred user preference.

---

## 7.2 `product_type`

**Meaning:** Canonical category describing the primary type of fashion product.

**Current vocabulary:**

```text
t_shirt
sweatshirt
track_pants
cargo_pants
night_suit
co_ord
kurta
saree
dress
jeans
trousers
shorts
skirt
jacket
hoodie
top
blouse
camisole
tunic
leggings
joggers
blazer
sweater
cardigan
palazzo
kurti
shirt
```

**Cardinality:** Currently single-valued in the Phase 2 extraction contract.

**Uses:** Structured filtering, lexical representation, semantic representation, and ranking.

A candidate higher-level hierarchy may eventually include:

```text
Topwear
├── shirt
├── t_shirt
├── blouse
├── top
├── camisole
└── tunic

Bottomwear
├── jeans
├── trousers
├── shorts
├── skirt
├── leggings
├── joggers
├── track_pants
├── cargo_pants
└── palazzo

Outerwear
├── jacket
├── blazer
└── cardigan

Traditional
├── kurta
├── kurti
└── saree
```

This hierarchy is a candidate structure and must be validated against the catalog before becoming a hard schema constraint.

---

# 8. Appearance Attributes

## 8.1 `color`

**Meaning:** Product color concept(s), using the Phase 2 raw and normalized color fields.

**Related fields:**

```text
color_raw
color_normalized
color_is_coded
```

**Cardinality:** Potentially multi-valued.

**Uses:** Filtering, lexical representation, semantic representation, ranking.

### Normalization rule

Retain useful fashion-specific distinctions:

```text
navy_blue
light_blue
dark_blue
sky_blue
```

should not automatically become `blue`.

### Coded colors

If:

```text
color_is_coded = true
```

the value must not be interpreted as a human-readable color unless a verified mapping exists.

---

## 8.2 `pattern`

**Meaning:** Controlled description of visible/design pattern characteristics.

**Current vocabulary:**

```text
floral
printed
striped
graphic
solid
checked
typographic
embroidered
textured
geometric
abstract
polka
colourblocked
self_design
camouflage
paisley
tie_dye
```

**Cardinality:** Multi-valued where multiple verified pattern concepts are present.

**Uses:** Filtering, lexical representation, semantic representation, and potentially ranking.

Example:

```text
pattern = floral|embroidered
```

must retain both concepts.

---

# 9. Garment Property Attributes

## 9.1 `material`

**Meaning:** Material/fabric concepts extracted from product information.

**Current vocabulary:**

```text
cotton
silk
georgette
denim
linen
chiffon
satin
crepe
wool
fleece
viscose
rayon
polyester
nylon
leather
velvet
spandex
lycra
```

**Cardinality:** Multi-valued.

**Uses:** Filtering, lexical representation, semantic representation, and potentially ranking.

---

## 9.2 `fit`

**Meaning:** Garment fit/silhouette characteristic explicitly represented by the catalog extraction.

**Current vocabulary:**

```text
slim
regular
relaxed
skinny
straight
tailored
tapered
loose
comfort
boxy
oversized
```

**Cardinality:** Potentially multi-valued.

Concepts such as `oversized`, `boxy`, and `loose` should not automatically be treated as synonyms.

---

## 9.3 `sleeve`

**Meaning:** Sleeve-length/style characteristics extracted from product information.

**Current vocabulary:**

```text
full
short
sleeveless
half
long
three_quarter
cap
```

**Cardinality:** Potentially multi-valued according to the extraction contract.

Terminology such as `short` and `half` may overlap in ordinary fashion language and should remain distinct until a validated normalization rule is established.

---

## 9.4 `neckline`

**Meaning:** Neckline/collar construction identified in product information.

**Current vocabulary:**

```text
spread
mandarin
band
v
round
hooded
henley
boat
high
square
collared
polo
```

**Cardinality:** Potentially multi-valued according to the extraction contract.

Distinct concepts such as `v`, `round`, `square`, `boat`, and `mandarin` remain distinct.

---

# 10. Product Features

## 10.1 `product_features`

**Meaning:** Functional or design features associated with the product.

**Current vocabulary:**

```text
patch
kangaroo
side
chest pocket
pocket
zip
lace
drawstring
button
waistband
embroidery
belt
applique
ruffles
hood
```

**Cardinality:** Multi-valued.

**Important distinction:**

```text
product_type = hoodie
```

is different from:

```text
product_features = hood
```

---

# 11. Style Attributes

## 11.1 `style_attributes`

**Meaning:** Style, silhouette, construction, rise, and related fashion-design concepts.

**Current vocabulary:**

```text
a_line
mid_rise
high_rise
low_rise
flat_front
ribbed
panelled
distressed
bodycon
cropped
pleated
oversized
ruched
```

**Cardinality:** Multi-valued.

A candidate refinement is:

```text
Style Attributes
│
├── Silhouette
│   ├── a_line
│   └── bodycon
│
├── Rise
│   ├── low_rise
│   ├── mid_rise
│   └── high_rise
│
├── Construction
│   ├── ribbed
│   ├── pleated
│   └── panelled
│
└── Style / Length
    ├── cropped
    ├── distressed
    └── ruched
```

This remains a candidate structure until validated.

---

# 12. Controlled Vocabulary vs Open Text

## Controlled attributes

```text
category_gender
product_type
color
pattern
material
fit
sleeve
neckline
product_features
style_attributes
```

## Open text

```text
description
brand
```

Open text should not be forced into the controlled ontology.

Downstream representations will combine:

```text
Controlled attributes
+
Free-form product description
```

where appropriate.

---

# 13. Multi-Value Semantics

The following attributes are treated as multi-valued or potentially multi-valued:

```text
color
pattern
material
fit
sleeve
neckline
product_features
style_attributes
```

`product_type` and `category_gender` are currently treated as single-valued.

All verified concepts should be preserved rather than selecting an arbitrary single value.

---

# 14. Missing-Value Policy

A missing attribute means:

> The current catalog representation does not provide that attribute.

It does not mean:

```text
none
unknown
not applicable
```

unless such a value is explicitly established by the source.

Generated semantic/lexical text should normally omit missing attributes rather than introduce phrases such as `material unknown`.

---

# 15. Raw vs Normalized Values

Where both raw and normalized representations exist, both should remain available when useful.

For color:

```text
color_raw
color_normalized
color_is_coded
```

The normalized value is preferred for downstream matching/filtering when valid.

The raw value provides source provenance.

Normalization must not unnecessarily destroy information.

---

# 16. Ontology Usage Matrix

| Attribute | Structured | Filter | Lexical | Semantic |
|---|---:|---:|---:|---:|
| `category_gender` | Yes | Yes | Yes | Yes |
| `product_type` | Yes | Yes | Yes | Yes |
| `color` | Yes | Yes | Yes | Yes |
| `pattern` | Yes | Yes | Yes | Yes |
| `material` | Yes | Yes | Yes | Yes |
| `fit` | Yes | Yes | Yes | Yes |
| `sleeve` | Yes | Yes | Yes | Yes |
| `neckline` | Yes | Yes | Yes | Yes |
| `product_features` | Yes | Yes | Yes | Yes |
| `style_attributes` | Yes | Yes | Yes | Yes |

This defines intended downstream availability. It does not yet define exact text formatting or embedding strategy.

---

# 17. What the Ontology Does Not Define

This artifact does not decide:

- embedding model
- embedding dimensionality
- vector index configuration
- BM25 implementation
- query parsing
- hybrid retrieval
- ranking algorithms
- recommendation algorithms
- LLM-based attribute inference
- image understanding
- personalization

These are downstream concerns.

---

# 18. Relationship to Phase 3

```text
3.1 Representation Requirements
              │
              ▼
3.2 Product Attribute Ontology
              │
              ▼
3.3 Structured Product Representation
              │
              ▼
3.4 Product Text Representation
              │
              ▼
3.5 Lexical Representation
              │
              ▼
3.6 Semantic Representation
              │
              ▼
3.7 Metadata & Filtering Representation
              │
              ▼
3.8 Query–Product Contract
              │
              ▼
3.9 Representation Pipeline
              │
              ▼
3.10 Quality Validation
              │
              ▼
3.11 Representation Dataset
              │
              ▼
3.12 Production Integration
              │
              ▼
Phase 4 — Embeddings
```

---

# 19. Implementation Boundary

This ontology is currently a specification artifact.

The production implementation should later expose it through a typed, testable interface, likely under:

```text
src/productiq/representation/
```

A future implementation may contain:

```text
representation/
├── ontology/
│   ├── schema.py
│   ├── vocabulary.py
│   └── definitions.py
├── schema.py
├── builder.py
└── validation.py
```

The exact implementation structure will be finalized during Phase 3.3.

---

# 20. Validation Requirements

Before treating the ontology as production-ready, validate it against representative Phase 2 products including:

- men's products
- women's products
- multiple product types
- products with many attributes
- products with few attributes
- coded colors
- multi-valued attributes
- missing attributes
- unusual descriptions
- long descriptions
- short descriptions

The purpose is to ensure the ontology describes the actual catalog rather than an abstract fashion taxonomy disconnected from the data.

---

# 21. Definition of Done

- [x] Every Phase 2 engineered attribute has a formal definition.
- [x] Attribute families are defined.
- [x] Controlled vs open-text fields are defined.
- [x] Cardinality is defined.
- [x] Multi-value behavior is defined.
- [x] Color semantics are defined.
- [x] Coded colors are explicitly protected.
- [x] Missing-value semantics are defined.
- [x] Filterability is defined.
- [x] Lexical usage is defined.
- [x] Semantic usage is defined.
- [x] Unsupported inferred catalog attributes are explicitly excluded.
- [x] Candidate product-type and style hierarchies are documented without prematurely enforcing them.
- [ ] Representative real-product validation remains to be performed during implementation review.

---

# 22. Decision Summary

The ProductIQ ontology will:

1. Use controlled vocabularies for explicit fashion attributes.
2. Preserve useful color granularity.
3. Preserve multi-valued attributes.
4. Keep raw and normalized values where provenance matters.
5. Keep coded colors explicitly marked.
6. Treat missing values as missing rather than inventing semantics.
7. Separate structured filtering information from free-form text.
8. Preserve catalog ground truth separately from future AI-inferred intent.
9. Support structured, lexical, and semantic product views.
10. Serve as the contract for Phase 3.3.

---

# 23. Next Step

## Phase 3.3 — Structured Product Representation

The next step transforms this ontology into an actual product-level schema:

```text
Phase 2 Product Catalog
          │
          ▼
Product Attribute Ontology
          │
          ▼
Structured Product Representation
```

The objective is to define exactly what a single `ProductRepresentation` contains, its types, cardinalities, validation rules, serialization format, and production interface.

---

# Part B — Phase 3.3 Structured Product Representation

**Step:** 3.3 — Structured Product Representation  
**Status:** Implemented  
**Version:** 1.0.0  
**Upstream:** Phase 2 processed catalog (`product_catalog.parquet`) and Phase 3.2 ontology  
**Downstream:** Phase 3.4 Product Text Representation, lexical/semantic/filtering views

## B.1 Purpose

Phase 3.3 defines the reusable **AI-ready structured product object** (`ProductRepresentation`): a typed, validated, JSON-serializable domain model built from the Phase 2 canonical catalog. It establishes the contract between catalog ground truth and future search, filtering, ranking, and embedding pipelines.

This step does **not** generate embeddings, BM25 indexes, vector indexes, query understanding, ranking, recommendations, or LLM inference.

## B.2 Input contract

Source: Phase 2 processed artifact `resources/processed/product_catalog.parquet` (and equivalent PostgreSQL `products` rows).

22 columns unchanged from Phase 2. The builder reads only the subset required for structured representation; other canonical fields (e.g. `color_raw`, prices, URLs) remain in the catalog and are not discarded at the source.

## B.3 Output contract — `ProductRepresentation`

| Field | Cardinality | Notes |
|---|---|---|
| `product_id` | required scalar | |
| `brand` | nullable scalar | |
| `brand_normalized` | nullable scalar | |
| `category_gender` | required scalar | Validated against ontology (`men` / `women`, case-insensitive) |
| `product_type` | nullable scalar | |
| `color` | nullable multi-valued | From `color_normalized` |
| `pattern` | nullable multi-valued | |
| `material` | nullable multi-valued | |
| `fit` | nullable multi-valued | |
| `sleeve` | nullable multi-valued | |
| `neckline` | nullable multi-valued | |
| `product_features` | nullable multi-valued | |
| `style_attributes` | nullable multi-valued | |

Implementation: Pydantic v2 model (`src/productiq/representation/schema.py`), frozen, `extra=forbid`.

## B.4 Source → representation mapping

| Phase 2 column | Representation field |
|---|---|
| `product_id` | `product_id` |
| `brand` | `brand` |
| `brand_normalized` | `brand_normalized` |
| `category_gender` | `category_gender` |
| `product_type` | `product_type` |
| `color_normalized` | `color` |
| `pattern` | `pattern` |
| `material` | `material` |
| `fit` | `fit` |
| `sleeve` | `sleeve` |
| `neckline` | `neckline` |
| `product_features` | `product_features` |
| `style_attributes` | `style_attributes` |

No inference. No LLM fill-in. `color_raw` stays in the catalog only.

## B.5 Multi-value semantics

Phase 2 stores multi-value attributes as pipe-delimited strings (`MULTI_VALUE_DELIMITER = "|"`).

Deterministic parsing (`parse_pipe_delimited_multivalue`):

- `None`, `NaN`, or blank string → `null` in the representation (not `[]`, not `"unknown"`)
- Single token → one-element list
- Multiple tokens → ordered list with duplicates removed (first occurrence wins)
- Whitespace trimmed per token; empty tokens from repeated/trailing delimiters ignored

## B.6 Missing-value semantics

Missing means the catalog does not provide the attribute: field is `null`. The builder does not substitute `unknown`, `none`, or empty lists.

## B.7 Validation

- Pydantic type and shape validation on `ProductRepresentation`
- Required non-empty `product_id` and `category_gender`
- `category_gender` checked against centralized ontology constants (case-insensitive)
- Multi-value lists: no empty strings, no duplicate entries, no empty lists (use `null` instead)
- Controlled vocabulary for attributes other than `category_gender` is **not** hard-rejected so evolving Phase 2 data remains valid

Failures raise `ProductRepresentationError` (subclass of `ValidationError`).

## B.8 Serialization

- `representation_to_dict` — stable field order, JSON-compatible values
- `representation_to_json` — deterministic JSON (`sort_keys=True` for nested structures)

## B.9 Implementation layout

```text
src/productiq/representation/
├── __init__.py
├── ontology.py      # shared Phase 3.2 constants (category_gender)
├── schema.py        # ProductRepresentation
├── builder.py       # canonical record → ProductRepresentation
├── validators.py    # parsing + contract validation
└── serializers.py   # dict / JSON export
```

Notebook: `notebooks/data_engineering/11_structured_product_representation.ipynb`

## B.10 Downstream consumers

Structured representation feeds (later phases):

- Lexical / BM25 document construction
- Semantic / embedding inputs (with text and metadata views)
- Structured filtering and facet metadata
- Ranking feature extraction

## B.11 Non-goals (Phase 3.3)

Embeddings, Sentence Transformers, FAISS, pgvector search, BM25, Elasticsearch, hybrid search, query understanding, LLM inference, recommendations, ranking, FastAPI endpoints, Redis, frontend.

## B.12 Definition of Done

- [x] `ProductRepresentation` Pydantic schema with documented fields and cardinalities
- [x] Builder from Phase 2 canonical record with exact field mapping
- [x] Pipe-delimited multi-value parsing boundary
- [x] Validation and `ProductRepresentationError`
- [x] Dict/JSON serializers with stable field names
- [x] Unit tests and representative real-parquet validation
- [x] Demonstration notebook on processed catalog sample
- [x] No change to Phase 2 catalog contract or processed artifact

## B.13 Next step

**Phase 3.4 — Product Text Representation**: compose controlled attributes and catalog text into lexical/semantic-ready product text views without implementing retrieval or embeddings yet.

---

# Part C — Phase 3.4 Product Text Representation

**Step:** 3.4 — Product Text Representation  
**Status:** Implemented  
**Version:** 1.0.0  
**Upstream:** `ProductRepresentation` (Phase 3.3)  
**Downstream:** Phase 3.5 Lexical Representation, Phase 3.6 Semantic Representation, Phase 4 Embeddings

## C.1 Purpose

Produce a **deterministic, human-readable product text** string derived only from structured `ProductRepresentation` fields. This text is the shared natural-language surface for later lexical (BM25) and semantic (embedding) pipelines without implementing those systems in Phase 3.4.

## C.2 Input

- **Type:** `ProductRepresentation` (`src/productiq/representation/schema.py`)
- **Source of instances:** Built upstream via `build_product_representation` from Phase 2 catalog records (Parquet/DB). The text builder does **not** read Parquet, PostgreSQL, or pandas directly.

## C.2.1 Description (canonical free text)

Phase 3.3 intentionally excludes `description` from `ProductRepresentation`. Phase 3.4 therefore renders **structured attributes only**. Canonical product `description` will be merged at a later lexical/text pipeline boundary (Phase 3.5+) without changing the Phase 3.3 schema.

## C.3 Output

- **Type:** `str` (product text document)
- **API:** `build_product_text(representation) -> str`
- **Optional:** stateless `ProductTextBuilder.build(representation)`

Implementation: `src/productiq/representation/text.py`

## C.4 Field inclusion and order

Included when present (fixed order):

1. Brand (`brand`, else `brand_normalized` for display only)
2. Category (`category_gender`)
3. Product Type
4. Color
5. Pattern
6. Material
7. Fit
8. Sleeve
9. Neckline
10. Features (`product_features`)
11. Style (`style_attributes`)

`product_id` is not emitted in product text (identity remains on the structured object).

## C.5 Text format (stable)

Segments use the pattern `Label: value`, joined by `. ` (period + space). The full string ends with a final `.`.

Example:

```text
Brand: Nike. Category: Men. Product Type: Shirt. Color: Navy Blue. Pattern: Striped. Material: Cotton, Polyester. Fit: Slim. Sleeve: Full. Neckline: Collared. Features: Button, Chest Pocket. Style: Mid Rise.
```

## C.6 Missing-value behavior

If an attribute is `null` or renders empty after trimming, its **label is omitted entirely**. No placeholders such as `unknown`, `none`, or `no pattern`.

## C.7 Multi-value rendering

Multi-valued fields keep **source order** from `ProductRepresentation`. Values are rendered individually, then joined with `, ` (comma + space) within the segment.

## C.8 Readable token rendering

Machine tokens are rendered for display only; **`ProductRepresentation` values are never mutated**.

- Default: split on `_`, capitalize each part (`navy_blue` → `Navy Blue`, `three_quarter` → `Three Quarter`)
- Overrides for special tokens (e.g. `t_shirt` → `T-Shirt`, `co_ord` → `Co-Ord`)
- Scalars without underscores use title case (`nike` → `Nike`)

Helpers: `render_machine_token`, `render_scalar_value`, `render_multivalue` (testable, reusable).

## C.9 Determinism

Same `ProductRepresentation` → same text. No randomness, LLMs, external APIs, or model inference.

## C.10 Downstream relationship

```text
ProductRepresentation
        │
        ▼
build_product_text  (Phase 3.4)
        │
        ├──► Phase 3.5 Lexical Representation (BM25-oriented views)
        └──► Phase 3.6 Semantic Representation (embedding-oriented views)
```

## C.11 Non-goals (Phase 3.4)

Embeddings, Sentence Transformers, Hugging Face, BM25, vector/pgvector search, query understanding, ranking, recommendations, LLM generation, FastAPI endpoints.

## C.12 Definition of Done

- [x] Deterministic `build_product_text` from `ProductRepresentation`
- [x] Stable labeled segment format
- [x] Missing attributes omitted
- [x] Multi-value order preserved
- [x] Readable token rendering without mutating structured values
- [x] Unit tests (`tests/representation/test_text.py`)
- [x] Notebook `12_product_text_representation.ipynb`
- [x] No change to Phase 3.3 schema or Phase 2 artifacts

## C.13 Next step

**Phase 3.5 — Lexical Representation**: define BM25-oriented product text views (may incorporate canonical `description` alongside Phase 3.4 output).

---

# Part D — Phase 3.5 Lexical / Search Representation

**Step:** 3.5 — Lexical / Search Representation  
**Status:** Implemented  
**Version:** 1.0.0  
**Upstream:** `ProductRepresentation` (Phase 3.3), canonical `description` (Phase 2 open text)  
**Downstream:** Future BM25 indexing (not implemented in Phase 3.5)

## D.1 Purpose

Produce a **deterministic lexical document string** intended for future BM25 / lexical retrieval. This is search-oriented plain text, distinct from Phase 3.4 labeled product text and from future semantic embedding text.

## D.2 Included fields

Structured (fixed order, space-separated rendered terms):

1. Brand terms (`brand`, then `brand_normalized` when it adds distinct searchable text)
2. Category (`category_gender`)
3. Product type
4. Color
5. Pattern
6. Material
7. Fit
8. Sleeve
9. Neckline
10. Product features
11. Style attributes

Open text:

- `description` (passed separately; not stored on `ProductRepresentation`)

Structured and description segments are joined with a single space when both are present.

## D.3 Excluded fields

Not emitted as lexical content:

- `product_id`, `product_url`, `image_url`, `source`
- `discount_price_inr`, `original_price_inr`, `price_anomaly`
- `color_is_coded`, `color_raw` (structured layer uses normalized color only)

## D.4 Description handling

- Missing or blank → omitted (no placeholder)
- Mechanical normalization only: strip and collapse internal whitespace
- No LLM rewrite, summarization, or enrichment

## D.5 Relationship to Phase 3.4

| Aspect | Phase 3.4 `build_product_text` | Phase 3.5 `build_lexical_text` |
|---|---|---|
| Structured input | `ProductRepresentation` | `ProductRepresentation` |
| Format | Labeled clauses (`Brand: …`) | Plain searchable terms |
| Description | Excluded | Included when provided |
| Token rendering | Shared helpers in `text.py` | Reuses `text.py` render helpers |

## D.6 Public API

- `build_structured_lexical_text(representation) -> str`
- `build_lexical_text(representation, *, description=None) -> str`
- `build_lexical_text_from_canonical(representation, canonical_record) -> str`
- `LexicalRepresentationBuilder.build(...)`

Implementation: `src/productiq/representation/lexical.py`

## D.7 Non-goals

BM25, Elasticsearch, embeddings, vector search, query understanding, ranking, recommendations, LLMs.

## D.8 Definition of Done

- [x] Deterministic lexical builder with explicit field order
- [x] Description at canonical boundary without changing `ProductRepresentation`
- [x] Metadata/price/URL exclusion
- [x] Tests (`tests/representation/test_lexical.py`)
- [x] Notebook `13_lexical_search_representation.ipynb`

## D.9 Next step

**Phase 3.6 — Semantic Representation** (embedding-oriented views; no embeddings in Phase 3.6 spec execution unless defined there).

---

# Part E — Phase 3.6 Semantic Representation

**Step:** 3.6 — Semantic Representation  
**Status:** Implemented  
**Version:** 1.0.0  
**Upstream:** `ProductRepresentation` (Phase 3.3), canonical `description` (Phase 2)  
**Downstream:** Phase 4 embedding generation (not implemented here)

## E.1 Purpose

Produce a **deterministic, model-agnostic semantic document** (plain text) that preserves product meaning for future embedding models. Phase 3.6 does **not** compute embeddings, vectors, or similarity.

## E.2 Semantic vs lexical

| | Phase 3.5 Lexical | Phase 3.6 Semantic |
|---|---|---|
| Goal | BM25 / keyword search | Embedding model input |
| Structured format | Plain space-separated terms | Labeled clauses (`Brand: …`) |
| Description | Appended as normalized prose | `Description: …` labeled clause |
| Context | Minimal labels | Explicit field context |

Semantic text is **not** a rename of lexical text; regression tests assert they differ when labels and description formatting apply.

## E.3 Field order

Structured clauses follow Phase 3.4 order via `build_product_text`:

1. Brand  
2. Category  
3. Product Type  
4. Color  
5. Pattern  
6. Material  
7. Fit  
8. Sleeve  
9. Neckline  
10. Features  
11. Style  

Optional final clause:

12. Description

Missing fields are omitted (no `unknown` / `none` placeholders).

## E.4 Included / excluded fields

**Included:** structured attributes listed above + canonical `description` when provided.

**Excluded:** `product_id`, URLs, `source`, prices, `price_anomaly`, `color_is_coded`, `color_raw`.

## E.5 Description handling

- Passed separately (`description=` or canonical record helper)
- Reuses `normalize_lexical_description` (strip, collapse whitespace)
- No LLM rewrite, summarization, or enrichment

## E.6 Public API

- `build_semantic_text(representation, *, description=None) -> str`
- `build_semantic_text_from_canonical(representation, canonical_record) -> str`
- `SemanticRepresentationBuilder.build(...)`

Implementation: `src/productiq/representation/semantic.py`

## E.7 Relationship to Phase 4

Phase 4 will consume `build_semantic_text(...)` output as embedding input. Dimensions, models, indexes, and retrieval remain out of scope for Phase 3.6.

## E.8 Definition of Done

- [x] Deterministic labeled semantic document builder
- [x] Description at canonical boundary without changing `ProductRepresentation`
- [x] Distinct from lexical representation
- [x] Tests (`tests/representation/test_semantic.py`)
- [x] Notebook `14_semantic_product_representation.ipynb`

## E.9 Next step

**Phase 3.7 — Metadata & Filtering Representation** (implemented in Part F).

---

# Part F — Phase 3.7 Metadata & Filtering Representation

**Step:** 3.7 — Metadata & Filtering Representation  
**Status:** Implemented  
**Version:** 1.0.0  
**Upstream:** `ProductRepresentation` + Phase 2 commercial/provenance/color fields  
**Downstream:** Phase 3.8 Query–Product Contract, future hard filtering (not query parsing here)

## F.1 Purpose

Provide a **typed, storage-independent** product-side contract for deterministic metadata filtering. This is structured data—not lexical text, not embeddings, not SQL, not query understanding.

## F.2 Model: `FilteringRepresentation`

Frozen Pydantic model (`src/productiq/representation/filtering.py`), `extra=forbid`.

## F.3 Field types

| Field | Type | Required |
|---|---|---|
| `product_id` | `str` | yes |
| `source` | `str` | yes |
| `brand` | `str \| null` | no |
| `brand_normalized` | `str \| null` | no |
| `category_gender` | `str` | yes |
| `product_type` | `str \| null` | no |
| `color_raw` | `str` | yes (catalog provenance) |
| `color_is_coded` | `bool` | yes |
| `color` | `list[str] \| null` | no (normalized filter tokens) |
| `pattern` | `list[str] \| null` | no |
| `material` | `list[str] \| null` | no |
| `fit` | `list[str] \| null` | no |
| `sleeve` | `list[str] \| null` | no |
| `neckline` | `list[str] \| null` | no |
| `product_features` | `list[str] \| null` | no |
| `style_attributes` | `list[str] \| null` | no |
| `discount_price_inr` | `int` (≥ 0) | yes |
| `original_price_inr` | `int` (≥ 0) | yes |
| `price_anomaly` | `bool` | yes |

Excluded from filtering representation: `product_url`, `image_url`, `description` (not filter facets in this contract).

## F.4 Missing-value semantics

`None` means absent—not `unknown`, not `false`, not `0`, not `[]`. Multi-value fields use the same validation as `ProductRepresentation` (no empty lists, no duplicate tokens).

## F.5 Price handling

Prices remain **integers** in INR. No string conversion. `price_anomaly=True` is preserved when discount exceeds original (Phase 2 anomalies retained).

## F.6 Color handling

- `color_raw` + `color_is_coded` from canonical catalog (coded colors not interpreted as human-readable names)
- `color` carries normalized token list from `ProductRepresentation` (via `color_normalized` parsing)
- No merging or overwriting of raw vs normalized

## F.7 Public API

- `build_filtering_representation(representation, *, source, color_raw, color_is_coded, discount_price_inr, original_price_inr, price_anomaly)`
- `build_filtering_representation_from_canonical(record)`
- `filtering_representation_to_dict(filtering)`
- `FilteringRepresentationBuilder`

## F.8 Future consumers

- **Query understanding (later):** maps natural language to filter constraints
- **Hard filtering (later):** translates `FilteringRepresentation`-compatible constraints against product metadata in PostgreSQL or other stores

## F.9 Definition of Done

- [x] Typed `FilteringRepresentation` without SQL/query logic
- [x] Commercial and color provenance fields without changing `ProductRepresentation`
- [x] Tests (`tests/representation/test_filtering.py`)
- [x] Notebook `15_metadata_filtering_representation.ipynb`

## F.10 Next step

**Phase 3.8 — Query–Product Representation Contract** (implemented in Part G).

---

# Part G — Phase 3.8 Query–Product Representation Contract

**Step:** 3.8 — Query–Product Representation Contract  
**Status:** Implemented  
**Version:** 1.0.0  
**Upstream:** User query text (+ optional explicit constraints supplied by future query understanding)  
**Downstream:** Hard filtering, BM25, embeddings (not implemented here)

## G.1 Purpose

Define the **typed query-side contract** (`QueryRepresentation`) that separates:

1. **Constraints** — `QueryFilterConstraints` aligned with `FilteringRepresentation` facets  
2. **Lexical intent** — `QueryLexicalIntent.text` for future BM25  
3. **Semantic intent** — `QuerySemanticIntent.text` for future embeddings  

This phase does **not** parse natural language, retrieve candidates, rank, or embed.

## G.2 Models

| Model | Role |
|---|---|
| `QueryRepresentation` | Root query contract |
| `QueryFilterConstraints` | Optional hard-filter fields + price bounds |
| `QueryLexicalIntent` | Lexical path text |
| `QuerySemanticIntent` | Semantic path text |

All models: Pydantic v2, `frozen=True`, `extra="forbid"`.

## G.3 Constraint fields (all optional)

`brand`, `brand_normalized`, `category_gender`, `product_type`, multi-value facets (`color`, `pattern`, `material`, `fit`, `sleeve`, `neckline`, `product_features`, `style_attributes`), `min_discount_price_inr`, `max_discount_price_inr`.

Excluded from query constraints: `product_id`, URLs, `source`, `color_raw`, `color_is_coded`, `price_anomaly` (product-side metadata only).

## G.4 Query–product field alignment (contract mapping only)

Phase 3.8 documents which query constraint fields correspond to product filtering metadata. It does **not** evaluate whether a product satisfies constraints—that belongs in a future search/filter layer.

| Constant | Purpose |
|---|---|
| `QUERY_TO_FILTERING_FACET_FIELDS` | Facet fields shared between `QueryFilterConstraints` and `FilteringRepresentation` |
| `QUERY_TO_FILTERING_PRICE_BOUND_FIELDS` | `min_discount_price_inr`, `max_discount_price_inr` on the query side vs `discount_price_inr` on the product side |
| `QUERY_CONSTRAINT_EXCLUDED_PRODUCT_FIELDS` | Product-only fields never exposed as query constraints |

Future query understanding populates constraints; retrieval engines implement matching and execution.

## G.5 Public API

- `normalize_query_text(query_text) -> str`
- `build_query_representation(query_text, *, constraints=None, lexical_text=None, semantic_text=None)`
- `query_representation_to_dict(query)`
- `QUERY_TO_FILTERING_FACET_FIELDS`, `QUERY_TO_FILTERING_PRICE_BOUND_FIELDS`, `QUERY_CONSTRAINT_EXCLUDED_PRODUCT_FIELDS`
- `QueryRepresentationBuilder.build(...)`

Implementation: `src/productiq/representation/query_contract.py`

## G.6 Non-goals

NL parsing, LLMs, BM25, embeddings, vector search, SQL, ranking, recommendations.

## G.7 Definition of Done

- [x] Typed query contract with three paths  
- [x] Constraint model aligned with filtering metadata  
- [x] Documented query–product field alignment (no runtime filter evaluation)  
- [x] Tests (`tests/representation/test_query_contract.py`)  
- [x] Notebook `16_query_product_representation_contract.ipynb`

## G.8 Next step

Phase 3.9 Representation Generation Pipeline (see Part H).

---

# Part H — Phase 3.9 Representation Generation Pipeline

**Upstream:** Phase 2 canonical catalog record; Phases 3.3–3.7 builders; Phase 3.8 query contract (unchanged)  
**Downstream:** Future indexing, retrieval, and serving layers (not implemented here)

## H.1 Purpose

Provide a **deterministic orchestration layer** that produces all approved product-side representations from one canonical record, so callers do not duplicate builder call sequences across notebooks, jobs, and services.

## H.2 Builder vs pipeline

| Layer | Responsibility |
|---|---|
| **Builder** (Phases 3.3–3.7) | Constructs **one** representation from its defined inputs |
| **Pipeline** (Phase 3.9) | **Orchestrates** multiple existing builders; does not redefine their internal logic |

```text
Canonical Product Record (Phase 2)
        ↓
ProductRepresentationPipeline / build_product_representation_bundle
        ↓
ProductRepresentationBundle
├── product      (structured)
├── text         (Phase 3.4)
├── lexical      (Phase 3.5)
├── semantic     (Phase 3.6)
└── filtering    (Phase 3.7)
```

## H.3 Canonical input boundary

- Input: `Mapping[str, Any]` — the existing Phase 2 catalog record shape used by `build_product_representation` and `build_filtering_representation_from_canonical`.
- No file I/O, database access, or network calls inside the pipeline.
- Input mappings are **not mutated**.

## H.4 Dependency order

1. `build_product_representation(record)` → `ProductRepresentation`
2. `build_product_text(product)` → product text
3. `build_lexical_text_from_canonical(product, record)` → lexical document (description from canonical `description`)
4. `build_semantic_text_from_canonical(product, record)` → semantic document (description from canonical `description`)
5. `build_filtering_representation_from_canonical(record)` → `FilteringRepresentation` (structured facets + commercial/provenance/color fields from canonical record)

Description remains on the canonical record; it is **not** added to `ProductRepresentation`.

## H.5 Bundle model

`ProductRepresentationBundle` — frozen Pydantic model, `extra="forbid"`, fields:

- `product: ProductRepresentation`
- `text: str`
- `lexical: str`
- `semantic: str`
- `filtering: FilteringRepresentation`

The bundle groups builder outputs; it does not duplicate canonical columns beyond what each representation already carries.

## H.6 Error behavior

Failures propagate from the underlying builders (`ProductRepresentationError`, `FilteringRepresentationError`, etc.). The pipeline does not swallow or broadly re-wrap exceptions.

## H.7 Determinism and immutability

Same canonical input → identical bundle. No randomness, timestamps, or environment-dependent values.

## H.8 Serialization

`product_representation_bundle_to_dict(bundle)` composes existing serializers:

- `representation_to_dict` for structured product
- `filtering_representation_to_dict` for filtering
- plain strings for text / lexical / semantic

No new JSON transformation system.

## H.9 Query side (Phase 3.8)

Phase 3.9 does **not** add query parsing or a separate query pipeline. Callers continue to use `build_query_representation(...)` when structured query inputs are already available.

## H.10 Public API

- `build_product_representation_bundle(record) -> ProductRepresentationBundle`
- `ProductRepresentationPipeline.build(record) -> ProductRepresentationBundle`
- `product_representation_bundle_to_dict(bundle) -> dict`

Implementation: `src/productiq/representation/pipeline.py`

## H.11 Non-goals

BM25, embeddings, vector search, PostgreSQL/SQL filtering, query parsing, NLP/LLM query understanding, ranking, recommendations, FastAPI, Redis, model inference, ETL, database loading.

## H.12 Definition of Done

- [x] Typed `ProductRepresentationBundle`
- [x] Product orchestration pipeline delegating to existing builders
- [x] Bundle serializer wrapping existing serializers
- [x] Tests (`tests/representation/test_pipeline.py`)
- [x] Notebook `17_representation_generation_pipeline.ipynb`

## H.13 Next step

Phase 3.10 Representation Quality Validation (see Part I).

---

# Part I — Phase 3.10 Representation Quality Validation

**Upstream:** Phase 3.9 `ProductRepresentationBundle` / pipeline  
**Downstream:** Future representation dataset materialization and retrieval stacks (not implemented here)

## I.1 Purpose

Answer whether generated representations are **structurally valid, internally consistent, deterministic, sufficiently complete, and free from obvious degenerate outputs**—without evaluating retrieval relevance, semantic correctness, or search quality.

## I.2 Builder vs validator

| Layer | Responsibility |
|---|---|
| **Builders / pipeline (3.3–3.9)** | Construct representations |
| **Quality validator (3.10)** | Observe and report quality; does **not** change generation semantics |

## I.3 Validation scope

Per-bundle checks:

- Structural typing and multi-value token shape
- Cross-view consistency (`ProductRepresentation` ↔ text ↔ lexical ↔ semantic ↔ `FilteringRepresentation`)
- Field preservation where Phase 3 contracts require overlap
- Description presence in lexical/semantic when canonical description exists
- Price and color metadata preservation vs canonical record
- Degenerate text detection (empty, duplicate labels, literal `None` labels)
- Deterministic pipeline reproduction when a canonical record is supplied

Out of scope: BM25, embeddings, vector search, retrieval, ranking, recommendation, query understanding, LLM evaluation, precision/recall/MRR/NDCG, SQL/PostgreSQL search.

## I.4 Coverage vs accuracy

Catalog metrics such as `field_coverage["product_type"] = 0.819` mean **81.9% of records have a populated `product_type` in the structured representation**. They do **not** mean 81.9% semantic accuracy or search relevance.

No arbitrary pass/fail thresholds (for example “coverage must exceed 90%”) are applied.

## I.5 Missing-value semantics

`None` means missing. Empty lists, `"unknown"`, and sentinel strings are **not** treated as missing. Optional attributes are not required to be present.

## I.6 Public API

- `validate_product_representation_bundle(bundle, *, record=None) -> RepresentationQualityReport`
- `validate_canonical_record_representation_quality(record) -> RepresentationQualityReport`
- `validate_canonical_records_representation_quality(records) -> CatalogRepresentationQualityReport` (incremental; does not retain all bundles/reports)
- `summarize_representation_quality_reports(reports, *, bundles=None) -> CatalogRepresentationQualityReport`

Implementation: `src/productiq/representation/quality.py`

## I.7 Result types

- `RepresentationQualityIssue` — category, code, message, optional field
- `RepresentationQualityReport` — `valid`, issues, per-category counts
- `CatalogRepresentationQualityReport` — totals, field/representation coverage fractions, aggregated issue counts

## I.8 Non-goals

Retrieval evaluation, BM25 indexing, embedding generation, ranking, recommendations, query parsing, LLM-based text judging, fixing anomalies in builders.

## I.9 Definition of Done

- [x] Focused quality validator for `ProductRepresentationBundle`
- [x] Catalog-level observational summary
- [x] Tests (`tests/representation/test_quality.py`)
- [x] Notebook `18_representation_quality_validation.ipynb`

## I.10 Next step

Phase 3.11 Representation Dataset Generation (see Part J).

---

# Part J — Phase 3.11 Representation Dataset Generation

**Upstream:** Phase 2 `product_catalog.parquet`; Phase 3.9 pipeline; Phase 3.10 quality validation (optional at generation time)  
**Downstream:** Lexical index, embedding index, hybrid retrieval (not implemented here)

## J.1 Purpose

Materialize validated Phase 3 **product-side representations** into a reusable **Parquet dataset** (one row per `product_id`) for offline indexing and analytics—without implementing search, embeddings, or serving.

```text
Canonical Catalog (Phase 2)
        ↓
Representation Pipeline (Phase 3.9)
        ↓
Representation Dataset (Phase 3.11)
        ↓
(future) BM25 / embeddings / hybrid retrieval
```

## J.2 Input / output contract

| | |
|---|---|
| **Input** | Phase 2 processed catalog Parquet (`product_catalog.parquet`) via existing `ProcessedDatasetWriter` validation |
| **Output** | `product_representations.parquet` + `product_representations.manifest.json` under `resources/processed/` |
| **Join key** | `product_id` (unique, one row per canonical product) |

Columns: structured `ProductRepresentation` fields (multi-value stored as pipe-delimited strings), `product_text`, `lexical_text`, `semantic_text`, and filtering metadata (`source`, `color_raw`, `color_is_coded`, prices, `price_anomaly`). Facet fields shared with structured representation are stored once on the structured columns; quality validation ensures filtering facet parity.

## J.3 Batch processing and memory

Generation reads canonical Parquet in **batches** (`pyarrow.parquet.ParquetFile.iter_batches`), builds bundles per record, writes batch rows through `ParquetWriter`, and **does not** retain all bundles or quality reports in memory.

## J.4 Determinism and idempotence

Deterministic column order, stable serialization, manifest checksum (SHA-256). Regeneration **replaces** the prior artifact atomically (temp file + `os.replace`); row count must match the canonical catalog on success. Failed runs remove temporary files and do not publish a partial final Parquet/manifest pair.

## J.5 Public API

- `generate_representation_dataset(canonical_parquet_path, output_path, ...)`
- `RepresentationDatasetGenerator.generate(...)`
- `validate_representation_dataset(path, ...)`
- `load_representation_dataset_manifest(path)`

Implementation: `src/productiq/representation/dataset.py`, `dataset_schema.py`

## J.6 Non-goals

BM25, embeddings, pgvector/FAISS, ranking, recommendations, query parsing, LLMs, FastAPI, Redis, distributed orchestration.

## J.7 Definition of Done

- [x] Batch Parquet dataset generation from canonical catalog
- [x] Manifest aligned with Phase 2 reproducibility conventions
- [x] Post-generation validation
- [x] Tests (`tests/representation/test_dataset.py`)
- [x] Notebook `19_representation_dataset_generation.ipynb`

## J.8 Next step

Phase 3.12 Production Integration + Testing (see Part K and `final-architecture-review.md` §53).

---

# Part K — Phase 3.12 Production Integration & Closure

**Status:** Integration tests, artifact verification, architecture closure (no new retrieval functionality).

## K.1 End-to-end flow (frozen)

```text
Canonical Product Catalog (Phase 2)
        ↓
Structured ProductRepresentation (3.3)
        ↓
Specialized views — Product Text (3.4), Lexical (3.5), Semantic (3.6), Filtering (3.7)
        ↓
ProductRepresentationBundle (3.9)
        ↓
Quality validation (3.10, optional at scale)
        ↓
Materialized representation dataset (3.11)
        ↓
Future retrieval / ranking (Phase 4+)
```

The representation layer is the **contract** between canonical catalog ground truth and downstream indexing systems. Query-side contracts (3.8) remain parallel to product-side generation.

## K.2 Integration proof

`tests/representation/test_phase3_integration.py` verifies cross-layer coherence, dataset row fidelity to `bundle_to_dataset_row`, edge cases, determinism, and (when present) sample rows from the production Parquet artifact.

## K.3 Definition of Done

- [x] Cross-layer integration tests
- [x] Dataset consistency tests
- [x] Phase 3 architecture closure documented
- [x] Production artifact generation path verified

Phase 4 (BM25, embeddings, hybrid retrieval, ranking) is **not** started here.
