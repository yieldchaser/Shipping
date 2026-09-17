# China customs (GACC) – OPTIONAL manual export (quarterly reconciliation only)

Routine monthly data comes from the automated design in AGENT_HANDOFF.md §2.6.
Use this only to overwrite SMM/derived figures with exact GACC values.

Why manual: http://stats.customs.gov.cn serves data through Jul-2026, but every query
passes through a slider-puzzle CAPTCHA (toCaptchaView). That is a human-verification gate,
so it is not automated here.

Steps (数据查询 → 按条件查询):
1. 进出口类型: 进口 · 币制: 美元
2. 币制 **美元** (US dollars) · 年份 2025, 月份 1–12, tick 分月展示 → then repeat for 2026 (1–7)
3. 输出字段组 1: 商品 → value `26060000` (bauxite)   (second run: `2818` with 4-digit, or `28182000`)
4. 输出字段组 2: 贸易伙伴 → leave blank (all partners)
5. 查询 → solve the slider → 导出数据 (CSV/XLS)

Fills:
- Guinea bauxite mirror: 2025-05, 2025-07 … 2025-12, 2026-01, 2026-02, 2026-06 (+ re-check 2025-01…04)
- China alumina imports (HS 2818): 2025-01 … 2026-07
Drop the exported files in the chat / repo and they parse straight into the patch format.
Aug-2026 detail appears ~Sep 20.
