# CodeNova AI — Feature Demo Files

Open this `4thmile` folder in CodeNova (File → Open Folder). Each file
demonstrates one feature. All refactor outputs are `javac`-verified to compile.

| File | Feature | How to demo |
|------|---------|-------------|
| `01_ExtractMethod.java` | Extract Method + Unused Import | Wand icon → **Refactor (Preview)** → shows 3 extracted helpers + import removed |
| `02_DeadCode.java` | Dead Code Removal | Refactor → removes unused field, method, and imports |
| `03_Conditions.java` | Condition Simplification (De Morgan) | Refactor → `!(a>=b && a!=0)` becomes `a<b || a==0` |
| `04_Duplicates.java` | Duplicate Detection | Analyze / Refactor → flags the two identical methods |
| `05_Errors.java` | Real-time Error Detection | Open it → **PROBLEMS** tab shows 1 syntax + 3 runtime + 2 warnings, live |
| `06_Clean.java` | Fail-safe (no false changes) | Refactor → "Code is already clean — no changes needed" |
| `07_Metrics.java` | Metrics + AI Health Dashboard | Beaker icon → **Analyze Code**; or ask AI "show code health" |
| `08_Completion.java` | Auto-complete + snippets | In `main()` type `sout`+Tab, `fori`+Tab, `psvm`+Tab |
| `connected-demo/` | Dependency Graph | Open that folder → Graph panel → **Build Dependency Graph** → shows edges |

## Quick supervisor script
1. **Auto error detection** — open `05_Errors.java`, don't click anything → PROBLEMS populates instantly; fix the missing `;` and watch it clear live.
2. **Refactoring with safety** — open `01_ExtractMethod.java` → Refactor (Preview) → Accept. Note: *the engine rolls back anything that wouldn't compile.*
3. **Snippets** — open `08_Completion.java` → type `sout` + Tab.
4. **AI + metrics** — open `07_Metrics.java` → Chat → "Explain this code" and "show code health".
5. **Dependency graph** — open `connected-demo/` folder → Build Dependency Graph → real connections appear.
6. **Run** — open `06_Clean.java`, add a `main`, press **F5** → compiles & runs in the terminal.
7. **Git push** — Source Control → cloud-upload button → enter your GitHub repo URL + Personal Access Token (once) → pushes to your own repo.
