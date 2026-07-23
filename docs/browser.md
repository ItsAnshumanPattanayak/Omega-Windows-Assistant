# Omega safe browser automation

Phase 13 provides an optional adapter for one Omega-controlled browser session. It does not automate an existing personal browser profile and does not create a second assistant, parser, permission path, or history system.

## Backend and setup

Omega uses the open-source Playwright Python library as its only full-control browser framework. The dependency is optional:

```powershell
python -m pip install -e ".[browser]"
```

The default `edge` setting uses the installed Microsoft Edge channel. Playwright-managed browser binaries are never downloaded during import or startup. To opt into managed Chromium, configure `preferred_browser: chromium`, then run the separate explicit installation:

```powershell
python -m playwright install chromium
```

Playwright is imported only when a browser command explicitly starts the backend. Missing packages or browser channels return a safe unavailable result while terminal, GUI, voice, application, file, folder, history, and recovery features continue to work.

## Architecture

`BrowserConfiguration` validates immutable safety boundaries. `UrlValidator` canonicalizes hosts, handles IDNs, rejects unsafe schemes and network ranges, and produces a query/fragment-free audit URL. `BrowserManager` serializes bounded operations behind a lock and returns typed `ActionResult` records. `PlaywrightBrowserBackend` owns one non-persistent isolated context; domain records contain UUID tab IDs rather than Playwright objects.

`BrowserActionDispatcher` converts the normal parser result into an `Action`, creates `SafetyContext`, and submits the executor callback to `SafeExecutionGateway`. The gateway classifies, evaluates policy, confirms, revalidates, executes once, and persists the command/action/result lifecycle. Terminal, GUI, and voice all call `OmegaSession`; no adapter calls the backend directly.

The real backend validates all network requests before continuing them and the manager validates the resulting page URL again. Unsafe redirects therefore fail closed. Closing Omega stops only the exact context and browser instance it created.

## Configuration

The `browser` YAML section controls enablement, the allowlisted browser and search engine, HTTPS/HTTP policy, timeouts, maximum tabs, and URL/title/text/query/bookmark bounds. Unknown keys, loose booleans, booleans used as integers, unsupported browsers/engines, invalid ranges, and malformed schemes fail closed.

HTTPS is enabled by default. HTTP can be enabled only by trusted YAML policy. The following permanent restrictions cannot be enabled through YAML or runtime settings: `file:` navigation, URL credentials, `javascript:` or `data:` URLs, downloads, form submission, sensitive input, and private mode. Localhost and private networks remain disabled by default.

## Supported commands

- `Open browser` and `Close browser`
- `Open example.com`
- `Search the web for Python decorators`
- `Open a new tab`, `List tabs`, `Switch to tab 2`, and `Close tab 1`
- `Refresh page`, `Go back`, and `Go forward`
- `Get page information`
- `Find the word installation on this page`
- `Open bookmark Docs`
- `Save this page as Docs`

Search uses fixed templates for DuckDuckGo, Bing, or Google and safe query encoding. Users cannot supply a search template. Spoken domain conversion is intentionally narrow (`example dot com`); ambiguous names require a clearer URL.

Page information contains a bounded title, validated/redacted current URL, stable tab ID, load state, bounded visible text, and optional match count. It never returns raw HTML, cookies, local/session storage, authorization headers, hidden form values, or password values. Search results omit title and page text from persisted result data because those fields often repeat the query.

Bookmarks are stored only in the current Omega process, use validated HTTPS URLs and bounded unique names, and are listed deterministically. They do not read or modify Edge, Chrome, or Firefox bookmark databases. Saving requires exact scoped confirmation. Bookmark persistence and replacement/deletion are deferred.

## Prohibited operations

Omega does not enter or retrieve passwords; log in; upload files; submit forms, messages, posts, legal agreements, purchases, payments, banking, or cryptocurrency operations; bypass CAPTCHAs, authentication, access controls, paywalls, certificate warnings, or browser protections; download executables or other files; install extensions; expose cookies/tokens/storage/profile data; accept user JavaScript, DevTools commands, or browser scripts; scrape authenticated content; crawl at scale; or evade automation detection.

## Privacy, history, and logging

Browser actions retain their command/action IDs and use existing SQLite lifecycle persistence. Action metadata stores only safe fields such as intent, redacted URL/host, tab ID, search engine, query/text length, status, and timestamps. Query parameters, fragments, credentials, cookies, tokens, browser profiles, downloads, and complete unbounded page bodies are not added to action metadata or logs. Page text is control-character cleaned and strictly bounded.

The original user command follows Omega's existing command-history policy. Users should not place secrets in commands. Browser errors shown to users contain safe messages; diagnostic exceptions remain in secure development logging.

## GUI and voice

GUI browser buttons submit normal commands through `GuiController` on the existing bounded worker runner. Duplicate clicks are blocked while busy and Tk widgets are updated only on the Tk thread. Voice transcripts preserve `CommandSource.VOICE` and use the same parser, dispatcher, gateway, and exact confirmation manager as typed commands. Speech output uses concise safe messages and does not read page bodies aloud.

## Testing and troubleshooting

Normal CI uses `FakeBrowserBackend`, performs no network request, launches no browser, and uses finite in-memory operations:

```powershell
python -m pytest -p no:cacheprovider tests/browser -v
```

Real-browser smoke testing is manual and opt-in: use a harmless public HTTPS page, finite timeouts, no login/forms/downloads, and close the Omega session afterward. It is not required for normal CI.

If the backend is unavailable, confirm the optional extra is installed and that `preferred_browser` names an installed channel. Chromium users must run the separate browser-install command. Local/private URLs, HTTP, credentials, internal browser pages, malformed ports, and excessive URLs are intentionally rejected.

Known limitations: bookmarks are process-local; no embedded renderer exists; no automatic login, clicking, forms, downloads, uploads, full semantic summarization, native profile/bookmark integration, or browser recovery is provided.
