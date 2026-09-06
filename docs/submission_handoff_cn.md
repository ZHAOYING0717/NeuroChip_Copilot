# NeuroChip Copilot 提交交接说明

## 官方要求口径

- 比赛：AI4S Open Innovation: AI for Life Science
- 官方页面：https://www.kaggle.com/competitions/ai-4-s-open-innovation-artificial-intelligence-for-life-scien/overview
- 初赛截止：**2026 年 10 月 10 日**
- 申报类别：**End-to-End System**
- 正式提交：Kaggle Writeup
- 额外必做：在提交前填写比赛页面给出的独立报名表
- 团队：1-5 人、1 名队长、每人只能加入 1 支队伍

## 当前本地产物

- Writeup 源稿：`docs/kaggle_writeup.md`
- 技术报告源稿：`docs/technical_report.md`
- 技术报告 PDF：`output/pdf/NeuroChip_Copilot_Technical_Report.pdf`
- 视频脚本与镜头表：`docs/video_script_5min_cn.md`
- 四张竞赛图：`docs/assets/figure0_architecture.png` 至 `figure3_external_validation.png`
- 一页样例报告：`output/pdf/neurochip_sample_report.pdf`
- 官方要求矩阵：`docs/kaggle_requirements_matrix.md`
- 最终视频与两个 ZIP：保留旧文件作为历史产物，但必须等系统被确认“最终版”后重建

## 已完成的证据链

- 45 条前脑类器官记录完成发布者源值复现。
- 45 条原始记录和 135 个受控扰动完成按来源组隔离的异常检验。
- 19 个地西泮条件、4 个类器官完成留一类器官验证。
- GIN 66 个匹配孔完成冻结模型的人源/大鼠二维网络压力测试。
- Trujillo 6 个处理对和 6 个同期对照对完成独立类器官协议压力测试，并与同孔自然漂移比较。
- 网页“模型解释”页直接显示五层证据、支持结论和不能支持的结论。

## 参赛者必须提供的信息

1. 队伍正式名称。
2. 队长和所有成员姓名、单位、角色。
3. 是否真实具备 AI/计算机和生物学/生物工程/临床双背景，以决定是否申报跨学科加分。
4. 报名表已经提交的确认。
5. 公开代码仓库、公开演示视频、公开报告和可选公开网站链接。

这些信息不能由程序推断，当前均保留为方括号占位符。跨学科加分只在真实成员构成符合要求时填写“是”。

## 提交前不得扩大解释的结论

- 分组异常 AUROC `0.858` 只代表对预定义事件扰动的识别能力，不是疾病或毒性模型。
- 地西泮 Spearman `rho=0.904` 和高剂量 AUROC `0.964` 来自 4 个类器官、1 种化合物，剂量估计仍是探索性结果。
- GIN 药理/TTX AUROC `0.952/0.950` 是二维培养跨域压力测试，不是类器官验证。
- Trujillo AUROC `0.889` 来自 12 个匹配对，只支持一个独立类器官协议中的强变化检测。
- 多维干预评价的“好坏”取决于预先选择的实验目标；单个前后配对不能替代生物学重复、载体/时间对照和毒性实验。
- 事件表只能支持事件层 QC；没有原始电压就不能判断电压噪声、硬件死电极或波形质量。

## 用户确认最终版后必须重新完成

1. 用最终网页重新录制不超过 5 分钟的实际操作视频并烧录字幕。
2. 重新生成技术报告 PDF，并检查全部页面和图表。
3. 重新构建公开仓库 ZIP 与完整提交 ZIP，不能混入旧视频或旧报告。
4. 填入团队信息和所有公开链接，清除全部占位符。
5. 在无登录浏览器中验证仓库、视频、报告、图片和可选网站。
6. 运行 `python scripts/audit_submission.py --require-public-links`。
7. 填写独立报名表，并在 Kaggle 正式提交 Writeup，不能只保存草稿。
