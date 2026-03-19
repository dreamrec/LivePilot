---
name: memory
description: Browse, search, and manage your saved technique library
---

Show the user's technique memory library. Follow these steps:

1. Call `memory_list(limit=20)` to get an overview of saved techniques
2. Format as an organized list grouped by type:
   - **Beats** — beat_pattern techniques
   - **Device Chains** — device_chain techniques
   - **Mix Templates** — mix_template techniques
   - **Browser Pins** — browser_pin techniques
   - **Preferences** — preference techniques
3. For each technique show: name, summary, rating (stars), favorite marker, tags
4. Show total count and breakdown by type

After presenting, ask if the user wants to:
- **Search** — "search for [query]" → use memory_recall
- **View details** — "show me [name]" → use memory_get
- **Delete** — "delete [name]" → use memory_delete (confirm first)
- **Rate** — "rate [name] 5 stars" → use memory_favorite
