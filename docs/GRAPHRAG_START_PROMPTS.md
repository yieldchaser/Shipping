# GraphRAG build: prompts the owner pastes into DeepSeek Harness

Setup is already done: the gateway runs at logon, keys are stored, and dsh points at the gateway. Open DeepSeek Harness, go to the **Shipping** workspace, click **New Session**, and check that the model reads "DeepSeek V4.1 Flash (gateway)".

## First start (once)

```
git checkout -b kb-build (main is already up to date). Stay on this one branch in this one checkout: never create other branches, worktrees or clones.
Execute docs/GRAPHRAG_AGENT_TASK.md end to end. Read it fully first, then docs/GRAPHRAG_BUILD_PLAN.md and every file it lists.
Begin with §0.1: write kb/reports/DESIGN_REVIEW.md, attack the plan, and adopt every improvement that keeps or raises quality.
The goal is cross-connection and depth: any shipping question, surface or deep, answered with exact, cited evidence. Quality beats cost.
Work autonomously; do not ask me questions. Stop only at the stop conditions in §6 or at checkpoints C1 and C2.
At a checkpoint, end your turn and wait for my message; never approve on my behalf.
Run python kb/tripwire.py before every gate; if it fails, stop.
Never lower a quality gate. If the budget runs out, cover fewer documents at full quality and declare the rest.
Slow replies mean the model queue is busy; keep going. Never touch tools/agent_gateway.
Keep kb/reports/STATUS.md current, with real spend from http://127.0.0.1:4100/stats.
Commit and push branch kb-build after every passed phase. Never push to main. Never print or commit any key.
If this session ends, the next one continues from kb/reports/STATUS.md.
```

## Resume (after a shutdown, crash or closed session)

Delete `kb\PAUSE` first if you created it, then paste:

```
Continue the GraphRAG build on branch kb-build. Follow docs/GRAPHRAG_AGENT_TASK.md §10.2 first (read kb/reports/STATUS.md, run python kb/resume.py, restart dead or paused jobs), then carry on from the Next action. All rules in the task file still apply.
```

## At a checkpoint (C1 or C2)

Read `kb/reports/C1_REVIEW.md` (or `C2_EVAL.md`), then reply in the chat. For example:

```
C1 approved. <your rulings on the flagged items, or any model override>. Continue.
```

## Clean stop before a shutdown (optional)

Create an empty file `kb\PAUSE`, wait about a minute, then shut down. Shutting down without it is also safe.
