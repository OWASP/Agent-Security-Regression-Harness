# Informative IETF Crosswalk (`draft-durga-*` & OWASP ASI01-ASI10 Benchmark DOI)

This page is an informative reference for scenario authors and integrators. It is not a harness assertion, scenario, or conformance requirement; the harness passes or fails strictly on its own assertions. The Internet-Drafts listed below are individual submissions (work in progress).

| Harness Concept | IETF Internet-Draft | Companion Technical Report DOI | Reference Corpus Path |
|---|---|---|---|
| Trace field recognition, RFC 8785 JCS receipts, and fail-closed empty traces (`#195`, PR `#198`) | [`draft-durga-agenttrust-trace-verification-00`](https://datatracker.ietf.org/doc/draft-durga-agenttrust-trace-verification/) | [`10.5281/zenodo.23775009`](https://doi.org/10.5281/zenodo.23775009) (`TR-2026-03`), [`10.5281/zenodo.23775532`](https://doi.org/10.5281/zenodo.23775532) (`TR-2026-04`) | `ietf-drafts/draft-durga-agenttrust-trace-verification-00.xml` |
| Data-plane vs. control-plane context isolation, scope attenuation, and commit-point approval (`#179`, PR `#181`, PR `#175`) | [`draft-durga-wimse-ctx-isolation-00`](https://datatracker.ietf.org/doc/draft-durga-wimse-ctx-isolation/) & [`draft-durga-agent-tx-compensation-lease-00`](https://datatracker.ietf.org/doc/draft-durga-agent-tx-compensation-lease/) | [`10.5281/zenodo.23735274`](https://doi.org/10.5281/zenodo.23735274) (`TR-2026-01`), [`10.5281/zenodo.23776574`](https://doi.org/10.5281/zenodo.23776574) (`TR-2026-06`) | `ietf-drafts/draft-durga-wimse-ctx-isolation-00.xml`, `ietf-drafts/draft-durga-agent-tx-compensation-lease-00.xml` |
| Multi-hop delegated authority & post-quantum hybrid delegation receipts (`#180`) | [`draft-durga-pquip-pqc-agentic-delegation-00`](https://datatracker.ietf.org/doc/draft-durga-pquip-pqc-agentic-delegation/) | [`10.5281/zenodo.23776217`](https://doi.org/10.5281/zenodo.23776217) (`TR-2026-05`) | `ietf-drafts/draft-durga-pquip-pqc-agentic-delegation-00.xml` |
| 100-Scenario OWASP ASI01-ASI10 Adversarial Benchmark Archive | DataCite DOI [`10.57967/hf/11352`](https://doi.org/10.57967/hf/11352) | [`10.5281/zenodo.23735497`](https://doi.org/10.5281/zenodo.23735497) (`TR-2026-02`), [`10.5281/zenodo.23723284`](https://doi.org/10.5281/zenodo.23723284) | `owasp-asi-benchmark/owasp_asi01_asi10_100_scenarios.jsonl` |

## Reference Corpus, Archival DOIs & Machine-Readable Crosswalk

- **Reference Corpus Repository (`Apache-2.0`, `CITATION.cff`):** <https://github.com/drk-ram/agentic-security-ietf-corpus>
- **Reference Benchmark Package (`agentic-governance-benchmarks` v1.0.0):** <https://github.com/drk-ram/enterprise-agentic-governance-benchmarks> (`DOI: 10.5281/zenodo.23723284`)
- **Archived Benchmark Dataset (`DOI: 10.57967/hf/11352`):** <https://doi.org/10.57967/hf/11352>
- **Foundational Zero Trust & Agentic AI Systems Papers:** [`10.38124/ijsrmt.v4i12.1050`](https://doi.org/10.38124/ijsrmt.v4i12.1050), [`10.38124/ijsrmt.v4i11.1049`](https://doi.org/10.38124/ijsrmt.v4i11.1049), [`10.38124/ijsrmt.v4i5.1043`](https://doi.org/10.38124/ijsrmt.v4i5.1043)

```json
{
  "schema": "agent-harness-ietf-crosswalk/v1",
  "normative": false,
  "corpus": "https://github.com/drk-ram/agentic-security-ietf-corpus",
  "benchmarks_repo": "https://github.com/drk-ram/enterprise-agentic-governance-benchmarks",
  "benchmark_doi": "10.57967/hf/11352",
  "zenodo_dois": [
    "10.5281/zenodo.23735274",
    "10.5281/zenodo.23735497",
    "10.5281/zenodo.23775009",
    "10.5281/zenodo.23775532",
    "10.5281/zenodo.23776217",
    "10.5281/zenodo.23776574",
    "10.5281/zenodo.23723284"
  ],
  "drafts": [
    "draft-durga-agenttrust-trace-verification-00",
    "draft-durga-wimse-ctx-isolation-00",
    "draft-durga-pquip-pqc-agentic-delegation-00",
    "draft-durga-agent-tx-compensation-lease-00"
  ]
}
```
