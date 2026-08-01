// ──────────────────────────────────────────────────────────────
// LLM Playground — comparison frontend (F3 + F4)
// Vanilla JS, no dependencies
// ──────────────────────────────────────────────────────────────

/**
 * Get all provider checkbox elements.
 * @returns {NodeListOf<HTMLInputElement>}
 */
function getProviderCheckboxes() {
  return document.querySelectorAll('#provider-selector input[type="checkbox"]');
}

/**
 * Get the list of selected provider slugs.
 * @returns {string[]}
 */
function getSelectedProviders() {
  const selected = [];
  getProviderCheckboxes().forEach(function (cb) {
    if (cb.checked) {
      selected.push(cb.getAttribute('data-provider'));
    }
  });
  return selected;
}

/**
 * Validate user input before making API call.
 * @returns {{ valid: boolean, error?: string }}
 */
function validateInput() {
  var prompt = document.getElementById('prompt-input');
  var promptText = prompt ? prompt.value.trim() : '';
  var providers = getSelectedProviders();

  if (!promptText) {
    return { valid: false, error: 'Please enter a prompt.' };
  }

  if (providers.length === 0) {
    return { valid: false, error: 'Please select at least one provider.' };
  }

  return { valid: true };
}

/**
 * Send comparison request to the backend API.
 * POST /api/playground/compare
 */
async function compare() {
  // ── Validate ──
  const validation = validateInput();
  if (!validation.valid) {
    renderError(validation.error);
    return;
  }

  // ── Clear previous results and errors ──
  const resultsGrid = document.getElementById('results-grid');
  const errorBanner = document.getElementById('error-banner');
  if (errorBanner) errorBanner.hidden = true;

  // ── Loading state ──
  const compareBtn = document.getElementById('compare-btn');
  const originalText = compareBtn ? compareBtn.textContent : 'Compare';
  if (compareBtn) {
    compareBtn.disabled = true;
    compareBtn.classList.add('loading');
    compareBtn.innerHTML = '<span class="spinner"></span> Comparing...';
  }

  // Show loading overlay in results grid
  if (resultsGrid) {
    resultsGrid.setAttribute('aria-busy', 'true');
    resultsGrid.innerHTML =
      '<div class="loading-overlay">' +
      '<div class="spinner"></div>' +
      '<span>Comparing providers...</span>' +
      '</div>';
  }

  // ── Build request ──
  const promptInput = document.getElementById('prompt-input');
  const providers = getSelectedProviders();
  const payload = {
    prompt: promptInput ? promptInput.value.trim() : '',
    providers: providers,
    system_prompt: document.getElementById('system-prompt-input')?.value.trim() || null,
  };

  try {
    // ── Send POST request ──
    const response = await fetch('/api/playground/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      // Try to get error detail from response body
      let detail = 'Server returned ' + response.status;
      try {
        const errData = await response.json();
        if (errData.detail) detail = errData.detail;
      } catch (_) {
        /* ignore */
      }
      throw new Error(detail);
    }

    const data = await response.json();

    // ── Render results ──
    if (data && data.results) {
      lastRenderedResults = data.results;
      renderResults(data.results);
      saveRecentRun(payload, data.results);
    } else {
      renderError('Unexpected response format from server.');
    }
  } catch (err) {
    renderError(err.message || 'Network error: could not reach the server.');
  } finally {
    // ── Restore button state ──
    if (resultsGrid) resultsGrid.setAttribute('aria-busy', 'false');
    if (compareBtn) {
      compareBtn.disabled = false;
      compareBtn.classList.remove('loading');
      compareBtn.textContent = originalText;
      updateButtonState();
    }
  }
}

/**
 * Render comparison results into the results grid.
 * @param {Object} results - Provider name -> result object mapping
 */
function renderResults(results) {
  const grid = document.getElementById('results-grid');
  if (!grid) return;

  // ── Convert to array, sort by total latency ascending ──
  const entries = [];
  for (var key in results) {
    if (results.hasOwnProperty(key)) {
      entries.push(results[key]);
    }
  }

  entries.sort(function (a, b) {
    var latA = a.latency ? a.latency.total_ms : 0;
    var latB = b.latency ? b.latency.total_ms : 0;
    return latA - latB;
  });

  // ── Identify fastest (non-error) provider ──
  var fastestProvider = null;
  var fastestLatency = Infinity;
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i];
    if (!e.error && e.latency && e.latency.total_ms < fastestLatency) {
      fastestLatency = e.latency.total_ms;
      fastestProvider = e.provider || e.name;
    }
  }

  // ── Build cards ──
  grid.innerHTML = '';
  for (var j = 0; j < entries.length; j++) {
    var entry = entries[j];
    var card = createCard(entry, entry.provider === fastestProvider);
    grid.appendChild(card);
  }
}

/**
 * Create a single result card DOM element.
 * @param {Object} result - Provider result object
 * @param {boolean} isFastest - Whether this is the fastest provider
 * @returns {HTMLElement}
 */
function createCard(result, isFastest) {
  const prov = result.provider || 'unknown';
  const model = result.model || '';
  const content = result.content || '';
  const hasError = !!result.error;

  // ── Card wrapper ──
  const card = document.createElement('div');
  card.className = 'card' + (hasError ? ' card-error' : '');
  card.setAttribute('data-provider', prov);

  // ── Header ──
  const header = document.createElement('div');
  header.className = 'card-header';

  const nameSpan = document.createElement('span');
  nameSpan.className = 'provider-name';
  nameSpan.textContent = prov;

  const modelSpan = document.createElement('span');
  modelSpan.className = 'provider-model';
  modelSpan.textContent = model;

  header.appendChild(nameSpan);
  header.appendChild(modelSpan);
  card.appendChild(header);

  // ── Body ──
  const body = document.createElement('div');
  body.className = 'card-body';
  if (hasError) {
    const errorText = document.createElement('p');
    errorText.textContent = result.error;
    body.appendChild(errorText);

    if (result.error_code) {
      const code = document.createElement('p');
      code.className = 'error-code';
      code.textContent = 'Category: ' + result.error_code.replaceAll('_', ' ');
      body.appendChild(code);
    }
    if (result.recovery_action) {
      const recovery = document.createElement('p');
      recovery.className = 'recovery-action';
      recovery.textContent = 'Recovery: ' + result.recovery_action;
      body.appendChild(recovery);
    }
  } else {
    body.textContent = content;
  }
  card.appendChild(body);

  // ── Footer (metrics) ──
  const footer = document.createElement('div');
  footer.className = 'card-footer';

  if (!hasError) {
    // Latency metric
    var latencyTotal = result.latency ? result.latency.total_ms : 0;
    var latencyTtft = result.latency ? result.latency.time_to_first_token_ms : 0;

    appendMetric(footer, 'Latency', formatMs(latencyTotal));

    appendMetric(footer, 'TTFT', formatMs(latencyTtft));

    // Latency bar
    const barContainer = document.createElement('div');
    barContainer.style.width = '100%';

    const barLabel = document.createElement('div');
    barLabel.className = 'metric-label';
    barLabel.textContent = 'RESPONSE TIME';
    barContainer.appendChild(barLabel);

    const bar = document.createElement('div');
    bar.className = 'latency-bar';

    const fill = document.createElement('div');
    fill.className = 'latency-bar-fill';
    // Scale: normalize to a reasonable max (10s = 100%)
    var pct = Math.min(100, (latencyTotal / 10000) * 100);
    fill.style.width = Math.max(2, pct) + '%';

    // Color code: green <1s, yellow 1-5s, red >5s
    if (latencyTotal < 1000) {
      fill.classList.add('fast');
    } else if (latencyTotal < 5000) {
      fill.classList.add('medium');
    } else {
      fill.classList.add('slow');
    }

    bar.appendChild(fill);
    barContainer.appendChild(bar);
    footer.appendChild(barContainer);

    // Tokens
    var tokensUsed = result.tokens_used || 0;
    appendMetric(footer, 'Tokens', String(tokensUsed));

    // Cost (6 decimal places)
    var cost = result.cost_usd || 0;
    appendMetric(footer, 'Cost', '$' + cost.toFixed(6));

    // Fastest badge
    if (isFastest) {
      const badge = document.createElement('span');
      badge.className = 'fastest-badge';
      badge.textContent = '\u26a1 Fastest';
      footer.appendChild(badge);
    }
  } else {
    // Error cards expose category, recovery guidance, and a scoped retry.
    appendMetric(footer, 'Status', 'Error');
    const retryBtn = document.createElement('button');
    retryBtn.className = 'retry-btn';
    retryBtn.type = 'button';
    retryBtn.textContent = 'Retry provider';
    retryBtn.addEventListener('click', function () {
      retryProvider(prov, retryBtn);
    });
    footer.appendChild(retryBtn);
  }

  // Copy button
  const copyBtnContainer = document.createElement('div');
  copyBtnContainer.style.marginLeft = 'auto';
  copyBtnContainer.style.alignSelf = 'flex-end';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'copy-btn';
  copyBtn.textContent = '\u{1F4CB} Copy';
  copyBtn.addEventListener('click', function () {
    copyResponse(prov, model, hasError ? result.error : content);
  });
  copyBtnContainer.appendChild(copyBtn);
  footer.appendChild(copyBtnContainer);

  card.appendChild(footer);
  return card;
}

/**
 * Append a metric label+value to a footer element.
 * @param {HTMLElement} parent
 * @param {string} label
 * @param {string} value
 */
function appendMetric(parent, label, value) {
  const container = document.createElement('div');
  container.className = 'metric';

  const lbl = document.createElement('div');
  lbl.className = 'metric-label';
  lbl.textContent = label;

  const val = document.createElement('div');
  val.className = 'metric-value';
  val.textContent = value;

  container.appendChild(lbl);
  container.appendChild(val);
  parent.appendChild(container);
}

/**
 * Format milliseconds for display.
 * @param {number} ms
 * @returns {string}
 */
function formatMs(ms) {
  if (ms >= 1000) {
    return (ms / 1000).toFixed(2) + 's';
  }
  return ms.toFixed(0) + 'ms';
}

/**
 * Show a general error banner.
 * @param {string} message - Error message to display
 */
function renderError(message) {
  var banner = document.getElementById('error-banner');
  if (banner) {
    banner.textContent = message;
    banner.hidden = false;
  }

  // Also clear any loading state in results grid
  var grid = document.getElementById('results-grid');
  if (grid) {
    var loadingOverlay = grid.querySelector('.loading-overlay');
    if (loadingOverlay) {
      grid.innerHTML = '';
    }
  }
}

/**
 * Update Compare button enabled/disabled state based on input state.
 */
function updateButtonState() {
  var btn = document.getElementById('compare-btn');
  if (!btn) return;

  var prompt = document.getElementById('prompt-input');
  var promptText = prompt ? prompt.value.trim() : '';
  var providers = getSelectedProviders();

  btn.disabled = !(promptText && providers.length > 0);
}

/**
 * Select all provider checkboxes.
 */
function selectAll() {
  getProviderCheckboxes().forEach(function (cb) {
    cb.checked = true;
  });
  updateButtonState();
}

/**
 * Clear all provider checkboxes.
 */
function clearAll() {
  getProviderCheckboxes().forEach(function (cb) {
    cb.checked = false;
  });
  updateButtonState();
}

/**
 * Copy provider response to clipboard.
 * @param {string} provider - Provider name
 * @param {string} model - Model name
 * @param {string} content - Response text
 */
function copyResponse(provider, model, content) {
  var text = 'Provider: ' + provider +
    (model ? ' (' + model + ')' : '') +
    '\n\n' + content;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      function () {
        showCopiedTooltip(event && event.target ? event.target : null);
      },
      function () {
        fallbackCopy(text);
      }
    );
  } else {
    fallbackCopy(text);
  }
}

/**
 * Fallback copy using execCommand.
 * @param {string} text
 */
function fallbackCopy(text) {
  var textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand('copy');
    showCopiedTooltip(null);
  } catch (e) {
    /* silently fail */
  }
  document.body.removeChild(textarea);
}

/**
 * Show a brief "Copied!" tooltip on the clicked button.
 * @param {HTMLElement|null} btn
 */
function showCopiedTooltip(btn) {
  if (!btn) {
    // Try to find the active copy button
    btn = document.querySelector('.copy-btn:focus, .copy-btn:hover');
  }
  if (btn) {
    var originalText = btn.textContent;
    btn.textContent = '\u2705 Copied!';
    btn.classList.add('copied');
    setTimeout(function () {
      btn.textContent = originalText;
      btn.classList.remove('copied');
    }, 2000);
  }
}

// ── Event listeners (initialized on DOMContentLoaded) ──
document.addEventListener('DOMContentLoaded', function () {
  // Compare button
  var compareBtn = document.getElementById('compare-btn');
  if (compareBtn) {
    compareBtn.addEventListener('click', compare);
  }

  // Select All / Clear All buttons
  var selectAllBtn = document.getElementById('select-all-btn');
  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', selectAll);
  }

  var clearAllBtn = document.getElementById('clear-all-btn');
  if (clearAllBtn) {
    clearAllBtn.addEventListener('click', clearAll);
  }

  // Provider checkbox changes -> update button state
  getProviderCheckboxes().forEach(function (cb) {
    cb.addEventListener('change', updateButtonState);
  });

  // Prompt input -> update button state
  var promptInput = document.getElementById('prompt-input');
  if (promptInput) {
    promptInput.addEventListener('input', updateButtonState);
  }

  // Initial button state
  updateButtonState();
});

// ── Live reload support (development) ──
// Re-run button state update when DOM changes
if (typeof MutationObserver !== 'undefined') {
  var observer = new MutationObserver(function () {
    updateButtonState();
  });
  var observeTarget = document.getElementById('provider-selector');
  if (observeTarget) {
    observer.observe(observeTarget, { childList: true, subtree: true });
  }
}

// Next-version workflow helpers: private, device-local preferences and history.
const PLAYGROUND_PREFS_KEY = 'ai-vibe-playground-preferences-v1';
const PLAYGROUND_RUNS_KEY = 'ai-vibe-playground-recent-runs-v1';
let lastRenderedResults = null;

function savePreferences() {
  const prompt = document.getElementById('system-prompt-input');
  const prefs = {
    providers: getSelectedProviders(),
    systemPrompt: prompt ? prompt.value : '',
    sort: document.getElementById('sort-results')?.value || 'latency'
  };
  localStorage.setItem(PLAYGROUND_PREFS_KEY, JSON.stringify(prefs));
}

function loadPreferences() {
  try {
    const prefs = JSON.parse(localStorage.getItem(PLAYGROUND_PREFS_KEY) || '{}');
    getProviderCheckboxes().forEach(cb => { cb.checked = (prefs.providers || []).includes(cb.dataset.provider); });
    const systemPrompt = document.getElementById('system-prompt-input');
    if (systemPrompt) systemPrompt.value = prefs.systemPrompt || '';
    const sort = document.getElementById('sort-results');
    if (sort && prefs.sort) sort.value = prefs.sort;
  } catch (_) { localStorage.removeItem(PLAYGROUND_PREFS_KEY); }
  updateButtonState();
}

function saveRecentRun(payload, results) {
  let runs = [];
  try { runs = JSON.parse(localStorage.getItem(PLAYGROUND_RUNS_KEY) || '[]'); } catch (_) { runs = []; }
  runs.unshift({
    id: 'run-' + Date.now(),
    createdAt: new Date().toISOString(),
    prompt: payload.prompt,
    providers: payload.providers,
    results: Object.values(results || {}).map(r => ({provider: r.provider, model: r.model, error: r.error || null}))
  });
  localStorage.setItem(PLAYGROUND_RUNS_KEY, JSON.stringify(runs.slice(0, 3)));
  loadRecentRuns();
  document.dispatchEvent(new CustomEvent('playground:run-completed', {detail: {providerCount: payload.providers.length}}));
}

function loadRecentRuns() {
  const host = document.getElementById('recent-runs');
  if (!host) return;
  let runs = [];
  try { runs = JSON.parse(localStorage.getItem(PLAYGROUND_RUNS_KEY) || '[]'); } catch (_) { runs = []; }
  const heading = '<h2 id="recent-runs-heading">Recent comparisons</h2>';
  if (!runs.length) { host.innerHTML = heading + '<p class="empty-state">Your three most recent comparisons will appear here on this device.</p>'; return; }
  const list = document.createElement('ol');
  list.className = 'recent-run-list';
  runs.forEach(run => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = run.prompt.slice(0, 80) + ' · ' + run.providers.join(', ');
    button.addEventListener('click', () => {
      document.getElementById('prompt-input').value = run.prompt;
      getProviderCheckboxes().forEach(cb => { cb.checked = run.providers.includes(cb.dataset.provider); });
      updateButtonState();
      document.getElementById('prompt-input').focus();
    });
    item.appendChild(button); list.appendChild(item);
  });
  host.innerHTML = heading; host.appendChild(list);
}

function sortAndRerender() {
  if (!lastRenderedResults) return;
  const mode = document.getElementById('sort-results')?.value || 'latency';
  const entries = Object.values(lastRenderedResults);
  entries.sort((a, b) => mode === 'cost' ? (a.cost_usd || 0) - (b.cost_usd || 0) : mode === 'provider' ? (a.provider || '').localeCompare(b.provider || '') : (a.latency?.total_ms || 0) - (b.latency?.total_ms || 0));
  const ordered = {}; entries.forEach(item => { ordered[item.provider] = item; });
  renderResults(ordered); savePreferences();
}

document.addEventListener('DOMContentLoaded', function () {
  loadPreferences(); loadRecentRuns();
  document.getElementById('system-prompt-input')?.addEventListener('change', savePreferences);
  document.getElementById('sort-results')?.addEventListener('change', sortAndRerender);
  getProviderCheckboxes().forEach(cb => cb.addEventListener('change', savePreferences));
});

/** Load safe setup readiness and annotate the existing provider choices. */
async function loadProviderReadiness() {
  const summary = document.getElementById('provider-readiness-summary');
  try {
    const response = await fetch('/api/playground/providers');
    if (!response.ok) throw new Error('Status service returned ' + response.status);
    const data = await response.json();
    let ready = 0;
    (data.providers || []).forEach(item => {
      const checkbox = document.querySelector('[data-provider="' + item.provider + '"]');
      const label = checkbox ? checkbox.closest('label') : null;
      if (!label) return;
      label.querySelector('.provider-status')?.remove();
      const status = document.createElement('span');
      status.className = 'provider-status ' + (item.configured ? 'ready' : 'setup-required');
      status.textContent = item.local ? 'Local' : item.configured ? 'Ready' : 'Setup required';
      status.title = item.model;
      label.appendChild(status);
      checkbox.disabled = !item.configured;
      if (item.configured) ready += 1;
    });
    if (summary) summary.textContent = ready + ' of ' + data.providers.length + ' providers ready. Unavailable providers are disabled.';
    updateButtonState();
  } catch (error) {
    if (summary) summary.textContent = 'Provider readiness could not be loaded. Existing selections remain available.';
    getProviderCheckboxes().forEach(cb => { cb.disabled = false; });
  }
}

document.addEventListener('DOMContentLoaded', function () {
  loadProviderReadiness();
  document.getElementById('refresh-provider-status')?.addEventListener('click', loadProviderReadiness);
});


/** Retry only one failed provider while preserving successful results. */
async function retryProvider(provider, button) {
  const prompt = document.getElementById('prompt-input')?.value.trim() || '';
  if (!prompt) {
    renderError('Enter a prompt before retrying the provider.');
    document.getElementById('prompt-input')?.focus();
    return;
  }
  const original = button ? button.textContent : 'Retry provider';
  if (button) {
    button.disabled = true;
    button.classList.add('retrying');
    button.textContent = 'Retrying...';
  }
  try {
    const payload = {
      prompt: prompt,
      providers: [provider],
      system_prompt: document.getElementById('system-prompt-input')?.value.trim() || null
    };
    const response = await fetch('/api/playground/compare', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Retry failed with status ' + response.status);
    }
    const data = await response.json();
    lastRenderedResults = lastRenderedResults || {};
    lastRenderedResults[provider] = data.results[provider];
    renderResults(lastRenderedResults);
    saveRecentRun(payload, data.results);
    document.dispatchEvent(new CustomEvent('playground:provider-retried', {detail: {provider: provider}}));
  } catch (error) {
    renderError(error.message || 'Provider retry failed.');
    if (button) {
      button.disabled = false;
      button.classList.remove('retrying');
      button.textContent = original;
    }
  }
}
