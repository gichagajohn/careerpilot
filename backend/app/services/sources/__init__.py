"""Source adapters for opportunity discovery.

Rules (spec §3, §15):
  - Official API where available (Adzuna, Remotive, RemoteOK, Arbeitnow).
  - Web search APIs (Google CSE / Serper / Tavily) for everything else —
    discovery only, never scraping LinkedIn/Indeed (ToS).
  - RSS feeds where a publisher offers them.
All adapters return RawListing objects; normalization happens downstream.
"""
