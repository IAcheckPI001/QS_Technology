

---
mode: agent
---

Review the proposed change against the current architecture.

First inspect:
- `.github/copilot-instructions.md`
- `docs/ai/architecture.md`
- `docs/ai/current-state.md`
- `docs/ai/decisions.md`

Then:

1. Identify affected components.
2. Identify architectural dependencies.
3. Check whether the proposed change violates existing boundaries.
4. Identify risks.
5. Propose the minimum viable implementation.
6. Do not modify code until the architecture assessment is complete.

Output:
- Current architecture
- Impacted components
- Risks
- Recommended approach
- Files likely to change
- Validation strategy