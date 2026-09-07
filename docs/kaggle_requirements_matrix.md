# Kaggle Requirements Matrix

Official competition: https://www.kaggle.com/competitions/ai-4-s-open-innovation-artificial-intelligence-for-life-scien/overview  
Submission category: **End-to-End System**  
Preliminary deadline: **10 October 2026**

## Mandatory submission elements

| Official requirement | Project response | Current status | Final action owner |
|---|---|---|---|
| Complete the separate registration form before submission | Registration URL is recorded in the checklist and handoff | Pending | Entrant |
| Declare one category at the beginning of the Writeup | `Submission Category: End-to-End System` is the first declaration | Complete | Codex |
| Submit one official Kaggle Writeup | Competition-ready draft in `docs/kaggle_writeup.md` | Draft complete; public links pending | Entrant |
| Public Demo video, maximum 5 minutes, no login | Real-operation Chinese script and shot list in `docs/video_script_5min_cn.md` | Final recording pending final system declaration | Codex + entrant upload |
| Public reproducible code repository | Lightweight examples, models, tests, environment, entry point, and full reproduction scripts | Local repository complete; public URL pending | Entrant |
| Technical report in Writeup or public PDF | Self-contained 15-20-page report source and rendered PDF | Local draft complete; team fields/public URL pending | Codex + entrant fields |
| Authorized data and media | Four public datasets, licenses, DOIs, checksums, derivative scope, and third-party notices | Complete | Codex |
| Disclose AI-tool use | Codex assistance disclosed in README, Writeup, and technical report | Complete | Codex |

## Evaluation alignment

| Criterion | Weight | Evidence supplied | Remaining risk |
|---|---:|---|---|
| Problem Importance and Potential Impact | 30% | Repeated neural-chip workflow, three concrete failure modes, target users, assay-review use cases, local/offline adoption path | No prospective labor-time or economic-impact study |
| Technical Approach and Innovation | 30% | Scope-aware QC, leakage-resistant grouping, robust PCA/Isolation Forest, deterministic Shapley evidence, conservative feature selection, goal-aware multidimensional intervention evaluation | No new foundational AI architecture; innovation is system and validation design |
| Results and Validation | 20% | 45/45 source reproduction, grouped controlled benchmark, leave-one-organoid-out real-dose association, frozen GIN test, independent Trujillo organoid test, ablations and sensitivity windows | Small training cohorts; external organoid endpoint has 12 pairs |
| Reproducibility and Implementation Quality | 10% | `demo.py`, pinned dependencies, manifests, hashes, checkpoints, models, tests, reports, data/model cards, package and audit scripts | Full external raw data are large and downloaded separately |
| Presentation Quality | 10% | Streamlit workflow, four figures, evidence table, technical PDF, concise Writeup, video script | Final refreshed video and public hosting remain pending |

## Team and account fields that cannot be inferred

- NeuroChip
- `[TEAM_LEADER_NAME]`
- `[TEAM_MEMBER_NAMES_AFFILIATIONS_AND_ROLES]`
- `[YES_OR_NO_WITH_SUPPORTING_ROLES]` for the cross-disciplinary bonus
- `[PUBLIC_REPOSITORY_URL]`
- `[PUBLIC_VIDEO_URL]`
- `[PUBLIC_REPORT_URL_OR_KAGGLE_ATTACHMENT]`
- `[PUBLIC_DEMO_URL]` if the optional application is deployed
- Registration form completion confirmation

The cross-disciplinary bonus must be claimed only if the real team includes both AI/computer-science and biology, bioengineering, or clinical expertise. Team size must remain within the official one-to-five-member limit, and each person may join only one team.

## Final logged-out checks

1. Open the repository, video, report, application, and every figure link in a private browser window.
2. Run `python demo.py --demo-only` from the published repository environment.
3. Confirm the video is no longer than five minutes and shows actual input, workflow, interface operation, output, and results.
4. Replace all bracketed placeholders in the Writeup, report, checklist, and handoff.
5. Run `python scripts/audit_submission.py --require-public-links` after rebuilding the final video and archives.
6. Submit the Kaggle Writeup rather than leaving it as a draft.
