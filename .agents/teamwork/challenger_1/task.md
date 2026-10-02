# Task: Challenger 1 (Automated Security, Regex & Test Suite Challenger)

Read:
- E:\wa bot longchain\.agents\teamwork\ORIGINAL_REQUEST.md
- E:\wa bot longchain\PROJECT.md
- E:\wa bot longchain\laporan.md
- E:\wa bot longchain\.env.example

Action:
1. Run automated search/regex verification:
   - Check for leaked WeatherAPI key `76d7a4136a6948e8ac464008250810`
   - Check for unmasked phone number `62895418133345`
   - Check for `file:///`
   - Check that `.env.example` contains `WEATHER_API_KEY`, `ADMIN_API_KEY`, and proper model names.
2. Run test suite using the project venv (`.venv\Scripts\python -m unittest discover tests`).
3. Report empirical verification results.

Deliver:
- Report in E:\wa bot longchain\.agents\teamwork\challenger_1\report.md
- Handoff in E:\wa bot longchain\.agents\teamwork\challenger_1\handoff.md with explicit verdict: APPROVE or REJECT.
