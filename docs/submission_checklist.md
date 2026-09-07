# Competition Submission Checklist

Official competition: https://www.kaggle.com/competitions/ai-4-s-open-innovation-artificial-intelligence-for-life-scien/overview  
Mandatory registration form: https://docs.google.com/forms/d/e/1FAIpQLSdRAat5jIunRaFNh_NntsVeJUnekEJDrbuokLZ32LFgCwPtiA/viewform?usp=publish-editor  
Preliminary deadline: **10 October 2026**  
Declared category: **End-to-End System**  
Official submission surface: **one submitted Kaggle Writeup plus the separate registration form**

## Project materials complete locally

- [x] Detected-event end-to-end scope stated consistently
- [x] Clear problem, target users, workflow impact, and adoption path
- [x] Licensed public data with creators, DOIs, checksums, and processing rules
- [x] Runnable code, pinned environment, saved models, and lightweight public examples
- [x] Cross-platform judge entry point: `python demo.py --demo-only`
- [x] Group-isolated training and evaluation
- [x] Exact publisher-value reproduction
- [x] Confidence intervals, permutation tests, threshold sensitivity, and ablations
- [x] Event-level channel status and six-segment recording-stability QC
- [x] Optional raw-voltage QC API with an explicit event-input boundary
- [x] Neuronal-avalanche, mutual-information, transfer-entropy, and predictive Granger descriptors
- [x] Reference-deviation Shapley evidence and exact paired-score component contributions
- [x] Goal-aware multidimensional intervention evaluation
- [x] Reference distance, network-silencing risk, optional reversibility, and evidence limits
- [x] NeuroChip 1.0 event schema and resumable Axion converter
- [x] PDF/HTML/CSV/JSON reporting and local SQLite project registry
- [x] Frozen-model GIN and independent Trujillo external stress tests
- [x] Five-level validation evidence table shown in the application
- [x] Automated tests and desktop/mobile browser QA
- [x] README, data card, model card, user guide, license notices, and requirements matrix
- [x] Technical report source revised to the official 15-20-page target
- [x] Kaggle Writeup begins with the mandatory category declaration
- [x] Five-minute video narration and real-operation shot list revised to the official criteria
- [ ] Refresh the actual captioned Demo video after the user declares the system final
- [ ] Rebuild and integrity-check both final ZIP archives after the video refresh

## Registration and team eligibility

- [x] Submit the separate registration form before the Kaggle Writeup deadline
- [x] Confirm the team has one to five members and one leader (NeuroChip: 赵梦颖 leader, 席玉杰 member)
- [ ] Confirm each person belongs to only one team
- [x] Replace `[TEAM_NAME]`, member, affiliation, and role placeholders
- [ ] State truthfully whether the team qualifies for the cross-disciplinary bonus
- [ ] Do not claim the bonus unless both AI/computer-science and biology/bioengineering/clinical expertise are represented by real team members

## Public links

- [ ] Publish the code repository and verify it opens without login
- [ ] Upload the maximum-five-minute Demo video and verify it plays without login
- [ ] Upload the technical-report PDF to Kaggle or a stable public address
- [ ] Upload the four PNG figures or replace their Markdown paths with public image links
- [ ] Optionally deploy the Streamlit application without login or payment
- [ ] Replace all `[PUBLIC_*]` placeholders in `docs/kaggle_writeup.md`

## Required Writeup content

- [x] Category declaration at the beginning
- [ ] Public Demo video attachment or URL, no more than five minutes
- [ ] Public code repository URL
- [x] Project summary of approximately 200-300 words
- [ ] Technical report attachment or public PDF URL
- [x] Problem importance and potential impact
- [x] Data source, license, processing, privacy, and compliance disclosure
- [x] Methods, architecture, implementation, experiments, results, reliability, limitations, and practical value
- [x] Reproduction commands and input/output definitions
- [x] AI-tool and third-party dependency disclosure
- [ ] Optional public application URL

## Official scoring alignment

- **Problem Importance and Potential Impact, 30%:** repeated neural-chip assay bottleneck, explicit failure modes, target users, three concrete use cases, and bounded adoption path.
- **Technical Approach and Innovation, 30%:** scope-aware QC, conservative feature selection, leakage-resistant modeling, model explanations, and goal-aware multidimensional paired evaluation.
- **Results and Validation, 20%:** five-level evidence hierarchy spanning exact reproduction, grouped controlled testing, held-out real organoids, frozen cross-domain transfer, and an independent organoid protocol.
- **Reproducibility and Implementation Quality, 10%:** one-command Demo, checksums, checkpoints, pinned environment, tests, models, reports, manifests, and audit scripts.
- **Presentation Quality, 10%:** usable dashboard, evidence display, concise Writeup, 15-20-page report, four figures, and a real-operation video.

## Final logged-out verification

- [ ] Hosted video matches the final local file and plays without login
- [ ] Repository README displays all four figures
- [ ] `python demo.py --demo-only` works from the public repository
- [ ] Full download links resolve and checksums match
- [ ] Technical report opens and all pages and figures are readable
- [ ] No private path, username, credential, token, or account detail is exposed
- [ ] Every link remains public through the review period
- [ ] `python scripts/audit_submission.py --require-public-links` passes
- [ ] Kaggle Writeup is submitted rather than left as a draft
