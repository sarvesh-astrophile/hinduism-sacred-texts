## Browser MCP Tools Available
### Navigation
- `browser-mcp_browser_navigate` — navigate to a URL (reuses current tab, or `new_tab`)
- `browser-mcp_browser_list_tabs` — list all open browser tabs with URLs and titles
- `browser-mcp_browser_get_new_tab` — get the most recently opened tab (e.g. after OAuth popups)
- `browser-mcp_browser_switch_tab` — activate a tab by ID
- `browser-mcp_browser_close_tab` — close a tab by ID

### Page Content & State
- `browser-mcp_browser_get_page_content` — get page content as text or HTML
- `browser-mcp_browser_screenshot` — take a screenshot of the visible area (base64 PNG or saved to disk)
- `browser-mcp_browser_execute_script` — execute JS in the page context
- `browser-mcp_browser_console_logs` — get recent console messages
- `browser-mcp_browser_list_frames` — list all iframes with URLs and indices
- `browser-mcp_browser_select_frame` — run JS inside a specific iframe by index
- `browser-mcp_browser_handle_dialog` — accept/dismiss alert(), confirm(), or prompt() dialogs

### Interaction (CSS + text selectors, e.g. `text=Get started`, `button:text(Submit)`)
- `browser-mcp_browser_click` — click an element (works on Angular/React SPAs, CSP-strict sites)
- `browser-mcp_browser_fill` — fill a text input field
- `browser-mcp_browser_hover` — hover over an element to trigger tooltips/dropdowns
- `browser-mcp_browser_press_key` — press a key, incl. modifiers (ctrl/alt/shift/meta)
- `browser-mcp_browser_scroll` — scroll to an element or by pixels
- `browser-mcp_browser_select_option` — select an option in a dropdown (native + custom)
- `browser-mcp_browser_set_combobox` — set values on autocomplete/combobox inputs (multi-select)
- `browser-mcp_browser_set_date` — set date inputs incl. calendar pickers
- `browser-mcp_browser_dismiss_overlays` — dismiss popups, modals, cookie banners

### Forms & Files
- `browser-mcp_browser_upload_file` — upload file(s) to `<input type="file">`
- `browser-mcp_browser_drop_file` — upload into drag-drop zones

### Storage & Data
- `browser-mcp_browser_get_cookies` — get cookies for a domain
- `browser-mcp_browser_set_cookies` — set one or more cookies
- `browser-mcp_browser_get_local_storage` — read localStorage (all or by key)
- `browser-mcp_browser_set_local_storage` — set a localStorage key-value pair
- `browser-mcp_browser_extract_token` — navigate to provider API settings page to read its API token
- `browser-mcp_browser_fetch` — make an HTTP request from the extension background (bypasses CORS/CSP)

### Waiting & Helpers
- `browser-mcp_browser_wait` — wait for an element/text to appear
- `browser-mcp_browser_wait_for_network` — wait for a network request to complete
- `browser-mcp_browser_ask_user` — show an overlay asking the user for input (2FA, CAPTCHA, OAuth)
- `browser-mcp_browser_solve_captcha` — detect/solve reCAPTCHA, hCaptcha, Cloudflare Turnstile, FunCaptcha
- `browser-mcp_browser_about` — info/wish/bug reporting for the Browser MCP plugin
