const PROMPT_MAX_LENGTH = 20000;

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
      resetDecisionStateForNewRun();
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
  renderComparisonSummary(results);

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
  document.getElementById('export-markdown')?.removeAttribute('disabled');
  document.getElementById('export-json')?.removeAttribute('disabled');
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
  card.className = 'card' + (hasError ? ' card-error' : '') +
    (preferredProvider === prov ? ' preferred-provider' : '');
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

  if (!hasError) {
    const preferredBtn = document.createElement('button');
    preferredBtn.className = 'preferred-btn';
    preferredBtn.type = 'button';
    preferredBtn.textContent = preferredProvider === prov ? 'Preferred' : 'Mark preferred';
    preferredBtn.setAttribute('aria-pressed', String(preferredProvider === prov));
    preferredBtn.addEventListener('click', function () {
      selectPreferredResult(prov);
    });
    footer.appendChild(preferredBtn);
  }

  // Copy button
  const copyBtnContainer = document.createElement('div');
  copyBtnContainer.style.marginLeft = 'auto';
  copyBtnContainer.style.alignSelf = 'flex-end';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'copy-btn';
  copyBtn.textContent = '\u{1F4CB} Copy';
  copyBtn.addEventListener('click', function () {
    copyResponse(prov, model, hasError ? result.error : content, copyBtn);
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
  var promptTooLong = promptText.length > PROMPT_MAX_LENGTH;

  if (prompt) prompt.setAttribute('aria-invalid', String(promptTooLong));
  var validation = document.getElementById('prompt-validation-message');
  if (validation) {
    validation.textContent = promptTooLong
      ? 'Prompt is too long. Reduce it to 20,000 characters or fewer.'
      : '';
  }
  btn.disabled = !(promptText && !promptTooLong && providers.length > 0);
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
 * @param {HTMLElement|null} trigger - Button that initiated the copy
 */
function copyResponse(provider, model, content, trigger) {
  var text = 'Provider: ' + provider +
    (model ? ' (' + model + ')' : '') +
    '\n\n' + content;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      function () {
        showCopiedTooltip(trigger);
      },
      function () {
        fallbackCopy(text, trigger);
      }
    );
  } else {
    fallbackCopy(text, trigger);
  }
}

/**
 * Fallback copy using execCommand.
 * @param {string} text
 */
function fallbackCopy(text, trigger) {
  var textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand('copy');
    showCopiedTooltip(trigger);
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

  document.getElementById('export-markdown')?.addEventListener('click', function () {
    exportComparison('markdown');
  });
  document.getElementById('export-json')?.addEventListener('click', function () {
    exportComparison('json');
  });

  // Provider checkbox changes -> update button state
  getProviderCheckboxes().forEach(function (cb) {
    cb.addEventListener('change', updateButtonState);
  });

  // Prompt input -> update button state
  var promptInput = document.getElementById('prompt-input');
  if (promptInput) {
    promptInput.addEventListener('input', function () {
      updatePromptCharacterCount();
      updateButtonState();
    });
    updatePromptCharacterCount();
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
const PLAYGROUND_DECISION_KEY = 'ai-vibe-playground-decision-v1';
let lastRenderedResults = null;
let preferredProvider = null;

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
    systemPrompt: payload.system_prompt || '',
    providers: payload.providers,
    providerCount: payload.providers.length,
    results: Object.values(results || {}).map(r => ({provider: r.provider, model: r.model, error: r.error || null}))
  });
  localStorage.setItem(PLAYGROUND_RUNS_KEY, JSON.stringify(runs.slice(0, 3)));
  loadRecentRuns();
  document.dispatchEvent(new CustomEvent('playground:run-completed', {detail: {providerCount: payload.providers.length}}));
}

function formatRecentRunTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Unknown time'
    : date.toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'});
}

function loadRecentRuns() {
  const host = document.getElementById('recent-runs-list');
  if (!host) return;
  let runs = [];
  try { runs = JSON.parse(localStorage.getItem(PLAYGROUND_RUNS_KEY) || '[]'); } catch (_) { runs = []; }
  if (!runs.length) {
    host.innerHTML = '<p class="empty-state">Your three most recent comparisons will appear here on this device.</p>';
    return;
  }
  const list = document.createElement('ol');
  list.className = 'recent-run-list';
  runs.forEach(run => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    const providerCount = run.providerCount || run.providers.length;
    const runTime = formatRecentRunTime(run.createdAt);
    button.textContent = run.prompt.slice(0, 80) + ' · ' +
      providerCount + ' providers · ' + runTime;
    button.setAttribute('aria-label',
      'Restore comparison from ' + runTime + ' with ' +
      providerCount + ' providers: ' + run.prompt.slice(0, 100));
    button.addEventListener('click', () => {
      document.getElementById('prompt-input').value = run.prompt;
      const systemPrompt = document.getElementById('system-prompt-input');
      if (systemPrompt) systemPrompt.value = run.systemPrompt || '';
      getProviderCheckboxes().forEach(cb => {
        cb.checked = run.providers.includes(cb.dataset.provider) && !cb.disabled;
      });
      updateButtonState();
      document.getElementById('prompt-input').focus();
    });
    item.appendChild(button); list.appendChild(item);
  });
  host.innerHTML = '';
  host.appendChild(list);
}

function clearRecentRuns() {
  localStorage.removeItem(PLAYGROUND_RUNS_KEY);
  loadRecentRuns();
  document.dispatchEvent(new CustomEvent('playground:history-cleared'));
  document.getElementById('clear-history')?.focus();
}

function toggleShortcutHelp(forceOpen) {
  const panel = document.getElementById('shortcut-help');
  const toggle = document.getElementById('shortcut-help-toggle');
  if (!panel || !toggle) return;
  const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : panel.hidden;
  panel.hidden = !shouldOpen;
  toggle.setAttribute('aria-expanded', String(shouldOpen));
  if (shouldOpen) {
    document.getElementById('shortcut-help-close')?.focus();
  } else {
    toggle.focus();
  }
}

function isEditableTarget(target) {
  if (!target) return false;
  return target.tagName === 'TEXTAREA' ||
    target.tagName === 'INPUT' ||
    target.tagName === 'SELECT' ||
    target.isContentEditable;
}

function handleKeyboardShortcut(event) {
  const editable = isEditableTarget(event.target);
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    if (!document.getElementById('compare-btn')?.disabled) compare();
    return;
  }
  if (!editable && event.key === '/') {
    event.preventDefault();
    document.getElementById('prompt-input')?.focus();
    return;
  }
  if (!editable && event.key === '?') {
    event.preventDefault();
    toggleShortcutHelp();
    return;
  }
  if (event.key === 'Escape' && !document.getElementById('shortcut-help')?.hidden) {
    event.preventDefault();
    toggleShortcutHelp(false);
  }
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
  document.getElementById('clear-history')?.addEventListener('click', clearRecentRuns);
  document.getElementById('decision-note')?.addEventListener('input', saveDecisionState);
  loadDecisionState();
  document.getElementById('shortcut-help-toggle')?.addEventListener('click', function () {
    toggleShortcutHelp();
  });
  document.getElementById('shortcut-help-close')?.addEventListener('click', function () {
    toggleShortcutHelp(false);
  });
  document.addEventListener('keydown', handleKeyboardShortcut);
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


/** Return a privacy-safe snapshot of the current comparison. */
function buildExportSnapshot() {
  const sanitizedResults = {};
  Object.entries(lastRenderedResults || {}).forEach(([provider, result]) => {
    const safeResult = Object.assign({}, result);
    delete safeResult.raw;
    delete safeResult.api_key;
    delete safeResult.apiKey;
    delete safeResult.authorization;
    sanitizedResults[provider] = safeResult;
  });
  return {
    schemaVersion: '1.0',
    generatedAt: new Date().toISOString(),
    prompt: document.getElementById('prompt-input')?.value || '',
    systemPrompt: document.getElementById('system-prompt-input')?.value || '',
    preferredProvider: preferredProvider,
    decisionNote: document.getElementById('decision-note')?.value || '',
    providers: Object.keys(sanitizedResults),
    results: sanitizedResults
  };
}

/** Build a readable Markdown decision record. */
function buildMarkdownExport(snapshot) {
  const lines = [
    '# LLM Provider Comparison',
    '',
    '- Generated: ' + snapshot.generatedAt,
    '- Providers: ' + snapshot.providers.join(', '),
    '',
    '## Prompt',
    '',
    snapshot.prompt || '(empty)',
  ];
  if (snapshot.systemPrompt) {
    lines.push('', '## System prompt', '', snapshot.systemPrompt);
  }
  lines.push('', '## Decision', '');
  lines.push('Preferred provider: ' + (snapshot.preferredProvider || '(not selected)'));
  if (snapshot.decisionNote) {
    lines.push('', snapshot.decisionNote);
  }
  Object.entries(snapshot.results).forEach(([provider, result]) => {
    lines.push('', '## ' + provider + (result.model ? ' · ' + result.model : ''), '');
    if (result.error) {
      lines.push('**Status:** Error', '', result.error);
      if (result.error_code) lines.push('', '**Category:** ' + result.error_code);
      if (result.recovery_action) lines.push('', '**Recovery:** ' + result.recovery_action);
    } else {
      lines.push(result.content || '(empty response)');
    }
    lines.push(
      '',
      '- Cost: $' + Number(result.cost_usd || 0).toFixed(6),
      '- Tokens: ' + String(result.tokens_used || 0),
      '- Latency: ' + String(result.latency?.total_ms || 0) + ' ms'
    );
  });
  return lines.join('\n');
}

/** Download UTF-8 content without sending comparison data to a server. */
function downloadTextFile(filename, content, mimeType) {
  const blob = new Blob([content], {type: mimeType + ';charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** Export the current comparison as Markdown or schema-versioned JSON. */
function exportComparison(format) {
  if (!lastRenderedResults || !Object.keys(lastRenderedResults).length) {
    renderError('Run a comparison before exporting.');
    return;
  }
  const snapshot = buildExportSnapshot();
  const date = snapshot.generatedAt.slice(0, 10);
  if (format === 'markdown') {
    downloadTextFile(
      'llm-comparison-' + date + '.md',
      buildMarkdownExport(snapshot),
      'text/markdown'
    );
  } else {
    downloadTextFile(
      'llm-comparison-' + date + '.json',
      JSON.stringify(snapshot, null, 2),
      'application/json'
    );
  }
  document.dispatchEvent(new CustomEvent(
    'playground:comparison-exported',
    {detail: {format: format, providerCount: snapshot.providers.length}}
  ));
}


/** Clear decision evidence when a genuinely new comparison replaces results. */
function resetDecisionStateForNewRun() {
  preferredProvider = null;
  const decisionNote = document.getElementById('decision-note');
  if (decisionNote) decisionNote.value = '';
  localStorage.removeItem(PLAYGROUND_DECISION_KEY);
  updatePreferredSummary();
}

/** Persist decision evidence only on the current device. */
function saveDecisionState() {
  const state = {
    preferredProvider: preferredProvider,
    decisionNote: document.getElementById('decision-note')?.value || ''
  };
  localStorage.setItem(PLAYGROUND_DECISION_KEY, JSON.stringify(state));
}

function loadDecisionState() {
  let state = {};
  try {
    state = JSON.parse(localStorage.getItem(PLAYGROUND_DECISION_KEY) || '{}');
  } catch (_) {
    localStorage.removeItem(PLAYGROUND_DECISION_KEY);
  }
  preferredProvider = state.preferredProvider || null;
  const note = document.getElementById('decision-note');
  if (note) note.value = state.decisionNote || '';
  updatePreferredSummary();
}

function updatePreferredSummary() {
  const summary = document.getElementById('preferred-result-summary');
  if (!summary) return;
  summary.textContent = preferredProvider
    ? 'Preferred provider: ' + preferredProvider
    : 'No preferred result selected.';
}

function selectPreferredResult(provider) {
  preferredProvider = preferredProvider === provider ? null : provider;
  saveDecisionState();
  updatePreferredSummary();
  if (lastRenderedResults) renderResults(lastRenderedResults);
  document.dispatchEvent(new CustomEvent(
    'playground:preferred-result-selected',
    {detail: {provider: provider, selected: preferredProvider === provider}}
  ));
}


/** Render aggregate evidence without implying that one provider is universally best. */
function renderComparisonSummary(results) {
  const host = document.getElementById('comparison-summary');
  if (!host) return;
  const entries = Object.values(results || {});
  if (!entries.length) {
    host.innerHTML = '<h2 id="comparison-summary-heading">Comparison summary</h2>' +
      '<p class="empty-state">No comparison results yet.</p>';
    return;
  }

  const successful = entries.filter(item => !item.error);
  const failed = entries.length - successful.length;
  const totalCost = successful.reduce(
    (sum, item) => sum + (Number.isFinite(Number(item.cost_usd)) ? Number(item.cost_usd) : 0),
    0
  );
  const totalTokens = successful.reduce(
    (sum, item) => sum + (Number.isFinite(Number(item.tokens_used)) ? Number(item.tokens_used) : 0),
    0
  );

  let fastestProvider = null;
  let fastestLatency = Infinity;
  let cheapestProvider = null;
  let cheapestCost = Infinity;
  successful.forEach(item => {
    const latency = Number(item.latency?.total_ms);
    const cost = Number(item.cost_usd);
    if (Number.isFinite(latency) && latency < fastestLatency) {
      fastestLatency = latency;
      fastestProvider = item.provider;
    }
    if (Number.isFinite(cost) && cost < cheapestCost) {
      cheapestCost = cost;
      cheapestProvider = item.provider;
    }
  });

  const stateText = failed > 0 && successful.length > 0
    ? 'This is a partial comparison. Completed results remain usable.'
    : failed === entries.length
      ? 'All provider attempts failed. Review recovery guidance and retry.'
      : 'All selected provider attempts completed.';
  const metrics = [
    ['Successful', successful.length],
    ['Failed', failed],
    ['Total cost', '$' + totalCost.toFixed(6)],
    ['Total tokens', totalTokens],
    ['Lowest latency', fastestProvider || 'Not available'],
    ['Lowest cost', cheapestProvider || 'Not available']
  ];

  const heading = document.createElement('h2');
  heading.id = 'comparison-summary-heading';
  heading.textContent = 'Comparison summary';
  const status = document.createElement('p');
  status.className = failed ? 'summary-status partial' : 'summary-status';
  status.textContent = stateText;
  const note = document.createElement('p');
  note.className = 'summary-note';
  note.textContent = "No provider is labeled 'best'; choose using the metric relevant to your task.";
  const list = document.createElement('dl');
  list.className = 'summary-metrics';
  metrics.forEach(([label, value]) => {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    const detail = document.createElement('dd');
    term.textContent = label;
    detail.textContent = String(value);
    item.append(term, detail);
    list.appendChild(item);
  });
  host.replaceChildren(heading, status, list, note);
}


/** Keep prompt length and remaining capacity visible before submission. */
function updatePromptCharacterCount() {
  const prompt = document.getElementById('prompt-input');
  const counter = document.getElementById('prompt-character-count');
  if (!prompt || !counter) return;
  const count = prompt.value.length;
  const remaining = Math.max(0, PROMPT_MAX_LENGTH - count);
  counter.textContent = count.toLocaleString() + ' of ' +
    PROMPT_MAX_LENGTH.toLocaleString() + ' characters · ' +
    remaining.toLocaleString() + ' characters remaining';
  counter.classList.toggle('near-limit', remaining <= 1000);
  counter.classList.toggle('at-limit', remaining === 0);
}
