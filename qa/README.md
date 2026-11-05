# Primary Revision quality checks

Run \`node scripts/verify-bank.mjs\` from the repository root. GitHub Actions runs the same check on every main branch push and pull request. The results are available as a downloadable \`primary-revision-source-fidelity\` workflow artifact.

The checker inspects all 1,102 questions (including stems, options, answer keys, explanations, rich-content fields, source locators, image references, search coverage and question identity). It also checks that offline assets, progress storage keys and the existing Firebase discussion integration remain present.

**Important limitations:** This is an automated structural screening, **not** a clinical content review or a comparison against the original book PDFs. Report flags require manual review and should not be silently rewritten. The original source PDFs must be consulted to verify typography, tables, figures, explanations and clinical correctness.

This change does not update any question content, Firebase configuration, Firestore rules or user progress data.
