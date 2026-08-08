# OpenFIQA Studio — Standards Conformance and T&E Requirements

**Status:** requirements specification, not yet implemented
**Scope:** the capabilities that distinguish an exploratory research tool from a controlled
biometric test-and-evaluation environment

---

## Provenance of this document

These 50 requirements were derived from the publicly described functions of standards,
conformance, and test-and-evaluation organisations in the biometric community — in particular the
role of evaluating whether a biometric implementation or transaction conforms to a defined
specification, and of producing engineering and certification evidence from that assessment.

**This is not an official requirements list issued by any agency.** No normative agency
requirements document was consulted in writing it, and none is cited here. It is a statement of
what OpenFIQA Studio must be able to do to be usable by conformance and T&E personnel, written
from the outside.

The standards named below — ISO/IEC 29794-5, DoD EBTS, NATO STANAG 4715, and the INTERPOL
biometric transmission specifications — are named because they are the real, published targets
that biometric interoperability is assessed against. Naming them as adapter targets is a
statement of intended scope, not a claim that any conformance capability exists today.

---

## Positioning consequence

The requirements below change what OpenFIQA Studio is:

```text
OpenFIQA Studio
Biometric Quality & Verification IDE

    ↓ extends into

OpenFIQA Studio — T&E Edition
Standards Conformance, Quality Assurance & Biometric Evaluation Workbench
```

The second layer is not a different product. It is the same typed workflow graph, the same
adapter registry, and the same provenance engine operated under a controlled evaluation
discipline. The difference is that the exploratory mode answers *what does this data show*, while
the T&E mode answers *does this implementation conform, and can that finding be reproduced by
someone else*.

The strategic effect is that OpenFIQA Studio stops being one laboratory's FIQA application and
becomes a **vendor-neutral biometric test harness** into which OFIQ, OFIQpy, US-FIQA, vendor
algorithms, acquisition systems, matchers, and future ISO/DoD profiles are inserted and evaluated
under a common evidence model.

---

## Priority requirements

Five of the fifty carry the positioning. If only five are built, build these:

| # | Requirement | Why it is load-bearing |
|---|---|---|
| 1 | Standards conformance workspace | Reframes the product from accuracy reporting to conformance assessment |
| 11 | Implementation equivalence testing | Makes OFIQ ↔ OFIQpy ↔ US-FIQA differences measurable rather than asserted |
| 38 | End-to-end evidence lineage | Every figure resolves to the samples and code that produced it |
| 40 | One-click reproduction | A third party can rerun a package and get a verdict, not a vibe |
| 50 | Controlled T&E mode | Turns the whole application from exploration into evaluation |

---

## A. Standards conformance workspace (1–10)

1. **Standards Conformance Workspace** — a dedicated mode for evaluating whether a biometric
   implementation conforms to a defined standard or profile, rather than merely reporting model
   accuracy.
2. **OFIQ / ISO quality conformance testing** — explicitly map each OFIQ/OFIQpy feature to its
   normative definition, implementation, test, expected range, and pass/fail result.
3. **DoD EBTS validation** — ingest and export biometric transaction packages and run automated
   structural and profile validation.
4. **NATO STANAG 4715 validation** — treat allied interoperability as an explicit test target
   rather than an eventual integration concern.
5. **INTERPOL format and profile validation** — a further explicit conformance adapter, since
   INTERPOL biometric transmission specifications are a published assessment target.
6. **Standards registry inside the IDE** — show which standards apply to each engine, dataset,
   workflow, transaction type, and output.
7. **Standards-version pinning** — a result must state which revision and profile it was tested
   against.
8. **Machine-readable conformance suites** — `conformance/ofiq.yaml`, `conformance/ebts.yaml`,
   and peers, rather than conformance existing only in prose.
9. **Requirement-level verdicts** — pass, fail, warning, and not-applicable reported per
   individual requirement, not per run.
10. **Generated conformance report** — suitable for engineering review, with every finding linked
    to the evidence that produced it.

## B. Implementation equivalence and provenance (11–17)

11. **OFIQ C++ ↔ OFIQpy equivalence testing** — side-by-side execution on exactly the same source
    image and parameters.
12. **OFIQ ↔ US-FIQA comparison without conflating semantics** — standardised quality components
    and learned unified scores must remain visibly distinct.
13. **Cross-implementation tolerance testing** — acceptable differences defined feature by
    feature, never one universal epsilon imposed across all components.
14. **Implementation provenance** — repository, commit SHA, compiler or interpreter, package
    version, model hash, configuration, and runtime recorded for every execution.
15. **Reference implementation designation** — explicitly identify which engine or result is
    acting as the control.
16. **Golden test vectors** — standardised, hashed images with known expected outputs for
    regression and conformance tests.
17. **Automatic regression detection** — flag when a new OFIQpy or OpenFIQA version changes those
    expected outputs.

## C. Quality analysis and controlled degradation (18–23)

18. **Quality-component inspector** — not one aggregate quality number; an evaluator must see
    exactly why an image is assessed poorly.
19. **Sample-level drill-down** — from every aggregate statistic to the exact biometric samples
    responsible for it.
20. **Image degradation laboratory** — resolution, JPEG and JPEG 2000 compression, blur, noise,
    contrast, illumination, pose, crop, face size, occlusion, and dynamic range.
21. **Controlled degradation sweeps** — for example JPEG quality 100→10, or face size 512→32 px.
22. **Quality-under-degradation curves** for every FIQA implementation.
23. **Recognition-under-degradation curves** — showing where degradation crosses from cosmetic
    quality loss into operational recognition loss.

## D. Quality–recognition linkage and matcher evaluation (24–30)

24. **Quality-vs-recognition analysis** — the operative question is not "does OFIQ detect blur"
    but "does the quality measure predict conditions associated with biometric failure".
25. **Error-versus-reject curves and AU-ERC** — the direct measure of a FIQA method's practical
    utility.
26. **ROC and DET analysis** with selectable operating points.
27. **FMR, FNMR, TAR, and FRR** computed with exact threshold provenance.
28. **Quality-conditioned matcher performance** — matcher behaviour reported separately for low-,
    medium-, and high-quality acquisition bands.
29. **Multiple matcher support** — so conclusions about FIQA are not artifacts of one recognition
    model.
30. **Matcher-independent FIQA evaluation** where scientifically appropriate.

## E. Failure and disagreement investigation (31–34)

31. **Failure explorer** with compound predicates, e.g. `OFIQ=GOOD AND USFIQA=POOR AND MATCH=FAIL`.
32. **Cross-engine disagreement browser** — surface the samples on which OFIQ, OFIQpy, US-FIQA,
    and OpenFIQA disagree most strongly.
33. **Outlier analysis** — click one anomalous point and immediately inspect the underlying
    sample, its transformations, every engine output, and the matcher scores.
34. **Real-vs-synthetic labelling** — synthetic, transformed, augmented, and authentic
    acquisitions permanently distinguishable, never inferred at read time.

## F. Evidence, lineage, and reproduction (35–42)

35. **Dataset provenance and governance** — source, authorisation, subset, split, transformation
    history, subject-independent partitioning, and permitted use.
36. **Cryptographic hashing of input artifacts** — so the exact file evaluated can be proven
    later.
37. **Immutable run manifests** — all inputs, transformations, code versions, parameters, random
    seeds, models, outputs, and hashes.
38. **End-to-end evidence lineage** — Figure → Metric → Evaluation → Scores → Model → Images →
    Dataset, traversable in both directions.
39. **Audit logging** — who ran what, with which implementation and configuration, and what was
    exported.
40. **Reproduction mode** — receive an experiment package, rerun it, and return one of
    `EXACT`, `WITHIN TOLERANCE`, `DIFFERENT`, `MISSING`, or `BLOCKED`.
41. **Scientific status separation** — `COMPUTED` ≠ `VALIDATED` ≠ `REPRODUCED` ≠ `CONFORMANT`.
    This distinction must be impossible to miss in the UI.
42. **Independent test-environment support** — the same workflow reproducible on a clean machine,
    not only on the developer workstation.

## G. Data protection and deployment posture (43–46)

43. **Air-gapped and local execution mode** — biometric information carries explicit protection
    and handling obligations; the product must never require external connectivity to function.
44. **No-default-cloud architecture** — datasets and images never leave the machine merely
    because a visualisation or ML feature was opened.
45. **Role-based access and data marking** — supporting public, controlled or restricted,
    synthetic, generated, and locally sensitive research artifacts.
46. **Software supply-chain evidence** — dependency versions, environment lock, model hashes,
    SBOM, external binaries, and source provenance.

## H. Extensibility and evidence delivery (47–50)

47. **Plugin and API interoperability layer** — an extensible test platform with standardised
    interfaces, not one laboratory's hard-coded research application.
48. **Headless CLI/API equivalence** — anything the GUI performs must also execute as a signed,
    version-controlled workflow in automated T&E.
49. **Certification and evidence package export** — conformance findings, test configuration,
    input manifest, execution evidence, exceptions, software versions, and reproducibility
    information in one deliverable.
50. **Test & Evaluation Mode** — a mode that converts the whole application from exploratory
    research into a controlled evaluation environment:

    ```text
    select standard / profile
        ↓
    select implementation
        ↓
    select reference corpus
        ↓
    run prescribed tests
        ↓
    investigate exceptions
        ↓
    reproduce
        ↓
    issue evidence package
    ```

---

## Relationship to the PRD

These requirements are additive to [`01_PRD.md`](01_PRD.md) and reuse its machinery:

| T&E requirement | PRD section it extends |
|---|---|
| 1–10 conformance workspace | new — no PRD equivalent yet |
| 11–17 equivalence and provenance | §26 OFIQ ↔ OFIQpy equivalence workflow, §28 provenance graph |
| 18–23 degradation | §6 Image Laboratory, §7 Degradation Studio, §8 sweeps |
| 24–30 evaluation | §19 verification evaluation, §20 FIQA evaluation, §22 statistical evaluation |
| 31–34 failure analysis | §24 interactive failure analysis, §25 feature inspector |
| 35–42 evidence and reproduction | §28 provenance graph, §30 reproduction mode |
| 43–46 data protection | §35 security and biometric-data requirements |
| 47–48 extensibility | §11 adapter architecture, §32 CLI equivalence |
| 49–50 evidence delivery | §29 publication mode — generalised from papers to evidence packages |

The conformance workspace (1–10) and the T&E mode (50) are the only genuinely new subsystems.
Everything else is a discipline imposed on machinery the PRD already specifies.
