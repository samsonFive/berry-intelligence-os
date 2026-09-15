# Trust feedback reason vocabulary

Exclusion accepts no reason on the initial action or one controlled value:

| Value | Meaning |
|---|---|
| `irrelevant` | Outside the analyst's intelligence question |
| `duplicate` | Same underlying item is already represented |
| `wrong_entity` | Linked or inferred company/entity is wrong |
| `wrong_berry` | Berry scope is wrong |
| `wrong_region` | Geographic scope is wrong |
| `wrong_berry_or_region` | Compatibility value from the roadmap's combined reason |
| `weak_source` | Source is too weak for this use |
| `unreadable` | Usable source content is unavailable |
| `outdated` | Too old for the intended active view |
| `misleading_extraction` | Extracted content misrepresents the source |
| `other` | A reason outside the initial controlled vocabulary |

The value is stored on both the state projection and immutable review event. It is analyst feedback, not a rewrite of source quality, acquisition outcome, or canonical trust.
