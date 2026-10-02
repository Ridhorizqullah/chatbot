# Task: Challenger 2 (Mermaid Syntax & Parsing Stress-Tester)

Read:
- E:\wa bot longchain\.agents\teamwork\ORIGINAL_REQUEST.md
- E:\wa bot longchain\PROJECT.md
- E:\wa bot longchain\laporan.md

Action:
1. Extract every Mermaid diagram block from `laporan.md` (Diagram 2.1, Diagram 2.2, Diagram 7.4, Diagram 10).
2. Write a Python script or syntax validator to parse and check each diagram for:
   - Syntax grammar validity
   - No unescaped `<` or `>` in labels
   - No illegal `->` operator in state labels
   - Correct choice state definitions (`state if_state <<choice>>`)
   - Valid node transitions and connections
   - Clean Gantt syntax
3. Stress-test markdown parsing and table formatting.

Deliver:
- Report in E:\wa bot longchain\.agents\teamwork\challenger_2\report.md
- Handoff in E:\wa bot longchain\.agents\teamwork\challenger_2\handoff.md with explicit verdict: APPROVE or REJECT.
