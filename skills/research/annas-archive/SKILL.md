---
name: annas-archive
description: "Search Anna's Archive and download books on request."
version: 2.0.0
author: bperris
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Books, Ebooks, Research, Download]
    related_skills: [pdf]
---

# Anna's Archive Book Fetching

Find and download books from Anna's Archive (annas-archive.gl) on request. The agent searches for the books the user asked about, reviews the results against the request, and downloads each match. The site sits behind a DDoS-Guard JavaScript challenge, so every page visit goes through the browser (`browser_navigate`); only the final file transfer uses `terminal` + `curl`. No Tor, no Tor Browser, no membership required.

## When to Use

- The user asks to find, fetch, or download books on a topic, by title, or by author.
- The user names several books or a subject and expects the matching ebooks saved locally.
- The user wants a reading list turned into actual files in `~/ebooks/`.

## Prerequisites

- A working browser: `browser_navigate` must be available and able to reach `annas-archive.gl`. The browser solves the DDoS-Guard challenge automatically on first load; wait a few seconds after navigating before reading the page.
- `curl` in the environment for the final file download.
- A target directory, default `~/ebooks/`. Create it if missing.

## How to Run

The whole flow is browser-first. Navigate, wait for the challenge to clear, extract links, then download with `curl`. Do not use `curl` against `annas-archive.gl` itself — it always gets a 403 challenge.

## Quick Reference

| Step | Action |
|------|--------|
| Search | `browser_navigate` to `https://annas-archive.gl/search?q=QUERY` |
| Book page | `browser_navigate` to `https://annas-archive.gl/md5/MD5_ID` |
| Download page | `browser_navigate` to the `slow_download` link on the book page |
| File | `curl -L` the partner link from the download page into `~/ebooks/` |

## Procedure

### 1. Parse the request into queries

Turn the user's ask into one or more search queries. For a subject, use the subject phrase. For named books, one query per book (title + author surname when known). For an author, the author's name. Done when every book or subject in the request maps to at least one query.

### 2. Search Anna's Archive for each query

`browser_navigate` to `https://annas-archive.gl/search?q=QUERY` (URL-encode the query). Wait a few seconds for the DDoS-Guard check to clear, then read the page. Extract each result's MD5 ID and title from links matching `/md5/`. If a search returns nothing or irrelevant results, try a shorter or differently-worded query before giving up. Done when each query has either results or a confirmed empty search after a reworded retry.

### 3. Select the books that match the request

Compare each result's title, author, and year against what the user asked for. Prefer exact title/author matches; for a subject request, pick the well-known, on-topic titles. Note the MD5 ID of each selected book. If the user asked for a specific book and the top result is a different edition, prefer the edition whose year/publisher matches the request. Done when every requested book has a chosen MD5 ID (or an explicit reason it was not found).

### 4. Get the download link for each book

For each MD5 ID, `browser_navigate` to `https://annas-archive.gl/md5/MD5_ID`. On the book page, find the `slow_download` links (free, no membership). `browser_navigate` to the first `slow_download` link; the page shows a "Download from partner website" section with a "📚 Download now" link to a partner server (a non-`annas-archive.gl` host). Copy that partner URL. Done when every selected book has a partner download URL.

### 5. Download each file

For each partner URL, run `curl -L -A "Mozilla/5.0" -o "~/ebooks/<Author>/<Title>.<ext>" "PARTNER_URL"` with `terminal`. The partner servers are not DDoS-Guard protected, so plain `curl` works. Save under `~/ebooks/<Author>/` with a sanitized title. A failed download prints an error; retry it once before moving on. Done when every selected book is either saved or has failed twice with a recorded reason.

### 6. Report what landed

Summarize for the user: which books downloaded, the file paths, and any that failed (with the reason). If the user asked for a reading list, list the downloaded files grouped by author. Done when the user knows exactly which books are on disk and which are not.

## Pitfalls

- **Never `curl` annas-archive.gl directly.** Search, book, and download pages all return a 403 DDoS-Guard challenge to non-browser clients. The browser is mandatory for those three steps; only the partner file host is `curl`-able.
- **Wait for the challenge to clear.** After navigating, the page shows "Checking your browser before accessing..." for a few seconds. Reading too early returns the challenge page. Wait, then re-read.
- **Fast downloads need membership.** Use `slow_download` links — they are free and work without an account. `fast_download` links redirect to a "not a member" page.
- **Partner links expire.** The "📚 Download now" URL is time-limited. Download promptly after extracting it; if it 404s, re-navigate to the `slow_download` page for a fresh link.
- **Search relevance is loose.** Anna's Archive matches loosely; verify each result's title/author/year against the request before downloading. A reworded query often finds the right edition.
- **Don't re-download duplicates.** Check `~/ebooks/` for an existing file before downloading the same book again.

## Verification

- Search returns results with MD5 IDs after the challenge clears.
- The book page yields a `slow_download` link.
- The download page yields a partner URL on a non-`annas-archive.gl` host.
- `curl` of the partner URL produces a file that `file` identifies as an EPUB/PDF/MOBI (not HTML), larger than 1 KB.