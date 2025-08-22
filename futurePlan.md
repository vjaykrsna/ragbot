# Future Plan: Improve Telegram History Extraction Speed

## Current Status
- Using Telethon for scraping.
- Achieving ~30-40 messages/second.
- Goal: Scale to 100-200 messages/second.

## Identified Bottlenecks & Improvement Strategies

1.  **Single Account Limitation:**
    -   **Issue:** Relying on a single Telegram account hits per-account rate limits, limiting throughput.
    -   **Plan:** Implement a multi-account system.
        -   Manage multiple `TelegramClient` instances, each with its own session.
        -   Distribute scraping tasks (e.g., different groups, message ranges) across these clients concurrently using `asyncio`.
        -   Handle `FloodWait` errors per client to prevent stalling the entire process.

2.  **Network Latency:**
    -   **Issue:** High latency to Telegram Data Centers can slow down request/response cycles.
    -   **Plan:** Deploy the scraper on a server located closer to Telegram's Data Centers.

3.  **Storage Layer Bottleneck:**
    -   **Issue:** Synchronous writes to the database or file system can become a bottleneck at higher speeds.
    -   **Plan:**
        -   Optimize database writes (e.g., batch inserts, asynchronous writes if the DB library supports it).
        -   Profile the current storage implementation to identify specific slowdowns.

4.  **Fetching Logic Optimization:**
    -   **Issue:** Sub-optimal use of Telethon's fetching methods.
    -   **Plan:**
        -   Ensure maximum `limit` (e.g., 100) is used in `client.get_messages` calls.
        -   Investigate if direct API calls or more advanced Telethon features can offer marginal gains.

5.  **Proxy Usage (Supporting Multi-Account):**
    -   **Issue:** Managing multiple accounts from a single IP can trigger rate limits or blocks.
    -   **Plan:** Integrate proxy support (datacenter or residential) for each Telethon client instance to distribute network origin.

## Next Steps
- Prioritize implementation of the multi-account system as it offers the most significant potential for scaling throughput.
- Set up a test environment to evaluate performance gains from multi-account and proxy usage.
- Re-evaluate performance after multi-account implementation to identify the next most impactful bottleneck.