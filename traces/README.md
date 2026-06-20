# Worked-case reasoning traces

This directory contains public-review trace appendices for the two worked cases whose model reasoning is quoted in the manuscript.

| File | Manuscript location | Contents |
| --- | --- | --- |
| `CLI.C.574655575_gemini_gradient.md` | Table `tab:trace-gradient`; §6.2 gradient discussion; related construct-validity discussion in §5.2 | Gemini-2.5-flash thinking-arm traces for the blind baseline, GN/G1/E1/GL5/G4/G5 x0.5 cells, and the G5 x2 cell. |
| `CLI.C.569614162_demand_characteristic.md` | Table `tab:demand-characteristic`; §6.3 demand-characteristic discussion; related construct-validity discussion in §5.2 | Grok-4.3 GN/G1/G5 x0.5 thinking-arm traces, Doubao GN/G5 x0.5 thinking-arm traces, and all three DeepSeek-V4-Pro T=0.7 repetitions for GN/G5 x0.5 thinking-arm cells. |

The source case materials were already desensitized before model prompting and public release. These files are limited to the model-exposed `thoughts`, `raw_output`, `parsed_amount`, and minimal cell metadata needed to verify quoted reasoning. They do not include request payloads, full case prompts, token usage, provider routing metadata, or API credentials.

Extraction counts:

- `CLI.C.574655575_gemini_gradient.md`: 8 records.
- `CLI.C.569614162_demand_characteristic.md`: 11 records.

The extracted text was screened before publication for direct personal names, institution names, contact identifiers, and concrete place strings. No unredacted identity or concrete-location strings were found in the released trace files.
