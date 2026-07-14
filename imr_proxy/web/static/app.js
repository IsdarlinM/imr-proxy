(function () {
  "use strict";

  const currentPath = window.location.pathname;
  document.querySelectorAll(".nav-link").forEach((link) => {
    const href = link.getAttribute("href") || "";
    const active = href === "/"
      ? currentPath === "/"
      : currentPath === href || currentPath.startsWith(href + "/");
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
  });

  const filterForm = document.getElementById("traffic-filters");
  const trafficLog = document.getElementById("traffic-log");
  if (!filterForm || !trafficLog) return;

  const filterStatus = document.getElementById("filter-status");
  const lastUpdated = document.getElementById("last-updated");
  const activeFilters = document.getElementById("active-filters");
  const trafficError = document.getElementById("traffic-error");
  const liveIndicator = document.getElementById("live-indicator");
  const liveStatusText = document.getElementById("live-status-text");
  const toggleLive = document.getElementById("toggle-live");
  const refreshNow = document.getElementById("refresh-now");
  const resetFilters = document.getElementById("reset-filters");
  const previousPage = document.getElementById("previous-page");
  const nextPage = document.getElementById("next-page");
  const pageStatus = document.getElementById("page-status");
  const drawer = document.getElementById("flow-drawer");
  const drawerBackdrop = document.getElementById("flow-drawer-backdrop");
  const drawerClose = document.getElementById("close-flow-drawer");
  const drawerTitle = document.getElementById("flow-drawer-title");
  const drawerSubtitle = document.getElementById("flow-drawer-subtitle");
  const drawerLoading = document.getElementById("flow-drawer-loading");
  const drawerError = document.getElementById("flow-drawer-error");
  const drawerContent = document.getElementById("flow-drawer-content");
  const fullPageLink = document.getElementById("flow-full-page-link");

  const state = {
    live: true,
    loading: false,
    offset: 0,
    total: 0,
    socket: null,
    socketConnected: false,
    reconnectTimer: null,
    reconnectAttempts: 0,
    fallbackTimer: null,
    refreshTimer: null,
    refreshQueued: false,
    lastRevision: null,
    selectedFlowId: null,
    selectedUpdatedAt: null,
    drawerRequest: 0,
  };

  const fallbackPollingIntervalMs = 3000;
  const realtimeRefreshDebounceMs = 80;
  const persistedKey = "imr-proxy-traffic-filters-v3";

  function value(value, fallback = "—") {
    return value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function oneLine(input, fallback = "—") {
    return value(input, fallback).replace(/\s+/g, " ").trim() || fallback;
  }

  function formatTime(input) {
    if (!input) return "—";
    const date = new Date(input);
    if (Number.isNaN(date.getTime())) return String(input);
    return date.toLocaleTimeString([], {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    });
  }

  function formatDate(input) {
    if (!input) return "—";
    const date = new Date(input);
    if (Number.isNaN(date.getTime())) return String(input);
    return date.toLocaleString([], { hour12: false });
  }

  function formatDuration(input) {
    const numeric = Number(input);
    return Number.isFinite(numeric) ? `${numeric.toFixed(1)} ms` : "—";
  }

  function formatBytes(input) {
    let numeric = Number(input || 0);
    if (!Number.isFinite(numeric) || numeric < 0) numeric = 0;
    const units = ["B", "KB", "MB", "GB"];
    let unit = 0;
    while (numeric >= 1024 && unit < units.length - 1) {
      numeric /= 1024;
      unit += 1;
    }
    return unit === 0 ? `${Math.round(numeric)} B` : `${numeric.toFixed(1)} ${units[unit]}`;
  }

  function headerValue(headers, name) {
    const wanted = name.toLowerCase();
    const entry = Object.entries(headers || {}).find(([key]) => key.toLowerCase() === wanted);
    return entry ? String(entry[1]) : null;
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function token(label, tokenValue, className = "") {
    const element = node("span", `log-token ${className}`.trim());
    if (label) element.appendChild(node("b", "log-token-label", `${label}=`));
    element.append(document.createTextNode(oneLine(tokenValue)));
    return element;
  }

  function protocolFor(flow) {
    return flow.http_version || flow.scheme || (flow.intercepted_tls ? "TLS intercepted" : "—");
  }

  function destinationFor(flow) {
    if (flow.server_address) return flow.server_address;
    if (!flow.host) return "—";
    return flow.port ? `${flow.host}:${flow.port}` : flow.host;
  }

  function statusClass(status) {
    if (status === null || status === undefined || status === "") return "status-none";
    const numeric = Number(status);
    if (!Number.isFinite(numeric)) return "status-none";
    return `status-${Math.floor(numeric / 100)}xx`;
  }

  function renderLogRows(items) {
    const fragment = document.createDocumentFragment();
    if (!items.length) {
      fragment.appendChild(node("div", "traffic-log-empty", "No traffic matches the active filters."));
      trafficLog.replaceChildren(fragment);
      return;
    }

    items.forEach((flow) => {
      const row = node("button", "traffic-log-row");
      row.type = "button";
      row.dataset.flowId = flow.id;
      row.dataset.updatedAt = flow.updated_at || flow.started_at || "";
      row.setAttribute("role", "listitem");
      row.setAttribute("aria-label", `${flow.event_type || "http"} ${flow.method || ""} ${flow.url || flow.host || ""}`);
      if (state.selectedFlowId === flow.id) row.classList.add("selected");

      const primary = node("span", "log-primary");
      const time = node("time", "log-time", formatTime(flow.updated_at || flow.started_at));
      time.title = value(flow.updated_at || flow.started_at);
      primary.appendChild(time);
      primary.appendChild(node("b", `log-event event-${oneLine(flow.event_type, "http").toLowerCase()}`, `${oneLine(flow.event_type, "http").toUpperCase()}/${oneLine(flow.state, "complete").toUpperCase()}`));
      primary.appendChild(node("strong", "log-method", oneLine(flow.method)));
      primary.appendChild(node("span", `log-status ${statusClass(flow.status_code)}`, value(flow.status_code)));
      const target = node("span", "log-target", oneLine(flow.url || flow.host));
      target.title = value(flow.url || flow.host);
      primary.appendChild(target);
      if (flow.highest_severity && flow.highest_severity !== "info") {
        primary.appendChild(node("span", `log-severity sev-${flow.highest_severity}`, flow.highest_severity));
      }
      row.appendChild(primary);

      const meta = node("span", "log-meta");
      meta.appendChild(token("src", flow.client_address));
      meta.appendChild(token("dst", destinationFor(flow)));
      meta.appendChild(token("proto", protocolFor(flow)));
      meta.appendChild(token("ua", flow.user_agent));
      meta.appendChild(token("req", formatBytes(flow.request_size), "log-size"));
      meta.appendChild(token("res", formatBytes(flow.response_size), "log-size"));
      meta.appendChild(token("dur", formatDuration(flow.duration_ms), "log-duration"));
      if (flow.content_type) meta.appendChild(token("type", flow.content_type, "log-content-type"));
      meta.appendChild(token("findings", flow.finding_count || 0));
      if (Array.isArray(flow.tags) && flow.tags.length) meta.appendChild(token("tags", flow.tags.slice(0, 5).join(",")));
      if (flow.error_message) meta.appendChild(token("error", flow.error_message, "log-error"));
      row.appendChild(meta);

      row.addEventListener("click", () => openFlowDrawer(flow.id, row));
      fragment.appendChild(row);
    });
    trafficLog.replaceChildren(fragment);
  }

  function setDrawerOpen(open) {
    drawer.classList.toggle("open", open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    drawerBackdrop.hidden = !open;
    document.body.classList.toggle("drawer-open", open);
    if (!open) {
      trafficLog.querySelectorAll(".traffic-log-row.selected").forEach((row) => row.classList.remove("selected"));
      state.selectedFlowId = null;
      state.selectedUpdatedAt = null;
    }
  }

  function detailItem(label, detailValue) {
    const item = node("div", "drawer-kv-item");
    item.appendChild(node("span", "drawer-kv-label", label));
    item.appendChild(node("strong", "drawer-kv-value", oneLine(detailValue)));
    return item;
  }

  function jsonBlock(title, data, open = false) {
    const details = node("details", "drawer-section");
    details.open = open;
    details.appendChild(node("summary", "drawer-section-title", title));
    const pre = node("pre", "drawer-code");
    pre.textContent = JSON.stringify(data ?? {}, null, 2);
    details.appendChild(pre);
    return details;
  }

  function renderFindings(findings) {
    const details = node("details", "drawer-section");
    details.open = Boolean(findings && findings.length);
    details.appendChild(node("summary", "drawer-section-title", `Findings (${(findings || []).length})`));
    const list = node("div", "drawer-findings");
    if (!findings || !findings.length) {
      list.appendChild(node("p", "muted", "No defensive findings for this event."));
    } else {
      findings.forEach((finding) => {
        const card = node("article", `drawer-finding sev-border-${finding.severity || "info"}`);
        card.appendChild(node("h4", "", `${oneLine(finding.severity, "info").toUpperCase()} · ${oneLine(finding.title)}`));
        card.appendChild(node("code", "", oneLine(finding.id)));
        if (finding.evidence) card.appendChild(node("p", "", `Evidence: ${finding.evidence}`));
        if (finding.remediation) card.appendChild(node("p", "", `Remediation: ${finding.remediation}`));
        list.appendChild(card);
      });
    }
    details.appendChild(list);
    return details;
  }

  function renderDrawer(flow) {
    const request = flow.request || {};
    const response = flow.response || null;
    drawerTitle.textContent = `${oneLine(request.method)} ${oneLine(request.host || request.url)}`;
    drawerSubtitle.textContent = oneLine(request.url);
    fullPageLink.href = `/flows/${encodeURIComponent(flow.id)}`;
    drawerContent.replaceChildren();

    const badges = node("div", "drawer-badges");
    badges.appendChild(node("span", `event-badge event-${oneLine(flow.event_type, "http").toLowerCase()}`, oneLine(flow.event_type, "http")));
    badges.appendChild(node("span", `state-badge state-${oneLine(flow.state, "complete").toLowerCase()}`, oneLine(flow.state, "complete")));
    badges.appendChild(node("span", `pill sev-${flow.findings && flow.findings.length ? oneLine(flow.findings[0].severity, "info") : "info"}`, `${(flow.findings || []).length} findings`));
    drawerContent.appendChild(badges);

    if (flow.error_message) drawerContent.appendChild(node("div", "alert error", flow.error_message));

    const overview = node("section", "drawer-kv-grid");
    [
      ["Started", formatDate(flow.started_at)],
      ["Updated", formatDate(flow.updated_at)],
      ["Duration", formatDuration(flow.duration_ms)],
      ["Source", flow.client_address],
      ["Destination", flow.server_address || `${request.host || "—"}${request.port ? `:${request.port}` : ""}`],
      ["Protocol", (response && response.http_version) || request.http_version || request.scheme],
      ["Status", response ? `${value(response.status_code)} ${oneLine(response.reason, "")}`.trim() : "—"],
      ["TLS visibility", flow.intercepted_tls ? "Intercepted" : "Passthrough / plain"],
      ["User-Agent", headerValue(request.headers, "user-agent")],
      ["Content-Type", response ? headerValue(response.headers, "content-type") : "—"],
      ["Request size", formatBytes(request.body_size)],
      ["Response size", formatBytes(response && response.body_size)],
      ["Redirect", flow.redirect_to],
      ["Session", flow.session_id],
    ].forEach(([label, detailValue]) => overview.appendChild(detailItem(label, detailValue)));
    drawerContent.appendChild(overview);

    drawerContent.appendChild(jsonBlock("Request headers", request.headers || {}, true));
    drawerContent.appendChild(jsonBlock("Request cookies", request.cookies || {}));
    if (request.body_text) drawerContent.appendChild(jsonBlock("Request body", { body: request.body_text }));
    if (response) {
      drawerContent.appendChild(jsonBlock("Response headers", response.headers || {}, true));
      drawerContent.appendChild(jsonBlock("Response cookies", response.cookies || {}));
      if (response.body_text) drawerContent.appendChild(jsonBlock("Response body", { body: response.body_text }));
    }
    drawerContent.appendChild(jsonBlock("Connection / event metadata", flow.metadata || {}));
    drawerContent.appendChild(jsonBlock("TLS metadata", flow.tls_metadata || {}));
    drawerContent.appendChild(renderFindings(flow.findings || []));
  }

  async function openFlowDrawer(flowId, sourceRow = null, options = {}) {
    state.selectedFlowId = flowId;
    trafficLog.querySelectorAll(".traffic-log-row.selected").forEach((row) => row.classList.remove("selected"));
    const row = sourceRow || Array.from(trafficLog.querySelectorAll(".traffic-log-row"))
      .find((candidate) => candidate.dataset.flowId === flowId);
    if (row) {
      row.classList.add("selected");
      state.selectedUpdatedAt = row.dataset.updatedAt || null;
    }
    setDrawerOpen(true);
    drawerLoading.hidden = false;
    drawerError.hidden = true;
    drawerContent.replaceChildren();
    const requestId = ++state.drawerRequest;
    try {
      const response = await fetch(`/api/flows/${encodeURIComponent(flowId)}`, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (response.status === 401) {
        window.location.assign("/login?next=/");
        return;
      }
      if (!response.ok) throw new Error(`Event detail request failed (${response.status})`);
      const payload = await response.json();
      if (requestId !== state.drawerRequest || state.selectedFlowId !== flowId) return;
      renderDrawer(payload);
      if (!options.preserveFocus) drawerClose.focus({ preventScroll: true });
    } catch (error) {
      if (requestId !== state.drawerRequest) return;
      drawerError.textContent = error instanceof Error ? error.message : "Unable to load event details.";
      drawerError.hidden = false;
    } finally {
      if (requestId === state.drawerRequest) drawerLoading.hidden = true;
    }
  }

  function closeDrawer() {
    state.drawerRequest += 1;
    setDrawerOpen(false);
  }

  drawerClose.addEventListener("click", closeDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer.classList.contains("open")) closeDrawer();
  });

  function rawFormValues() {
    const values = {};
    new FormData(filterForm).forEach((formValue, key) => {
      const normalized = String(formValue).trim();
      if (normalized) values[key] = normalized;
    });
    return values;
  }

  function formValues() {
    const values = rawFormValues();
    ["from_time", "to_time"].forEach((key) => {
      if (!values[key]) return;
      const parsed = new Date(values[key]);
      if (!Number.isNaN(parsed.getTime())) values[key] = parsed.toISOString();
    });
    return values;
  }

  function buildQuery() {
    const params = new URLSearchParams(formValues());
    params.set("meta", "true");
    params.set("offset", String(state.offset));
    return params;
  }

  function saveFilters() {
    try { localStorage.setItem(persistedKey, JSON.stringify(rawFormValues())); } catch (_) { /* optional */ }
  }

  function restoreFilters() {
    try {
      const saved = JSON.parse(localStorage.getItem(persistedKey) || "{}");
      Object.entries(saved).forEach(([key, savedValue]) => {
        const control = filterForm.elements.namedItem(key);
        if (control && typeof savedValue === "string") control.value = savedValue;
      });
    } catch (_) { /* optional */ }
  }

  function renderActiveFilters() {
    activeFilters.replaceChildren();
    const ignored = new Set(["limit", "order"]);
    Object.entries(formValues()).forEach(([key, filterValue]) => {
      if (ignored.has(key)) return;
      const chip = node("button", "filter-chip", `${key.replaceAll("_", " ")}: ${filterValue} ×`);
      chip.type = "button";
      chip.addEventListener("click", () => {
        const control = filterForm.elements.namedItem(key);
        if (control) control.value = "";
        state.offset = 0;
        saveFilters();
        renderActiveFilters();
        loadTraffic();
      });
      activeFilters.appendChild(chip);
    });
    if (!activeFilters.children.length) activeFilters.appendChild(node("span", "muted", "No advanced filters active"));
  }

  function updatePagination(limit) {
    const page = Math.floor(state.offset / limit) + 1;
    const pages = Math.max(1, Math.ceil(state.total / limit));
    pageStatus.textContent = `Page ${page} of ${pages}`;
    previousPage.disabled = state.offset <= 0;
    nextPage.disabled = state.offset + limit >= state.total;
  }

  function setLoading(loading) {
    state.loading = loading;
    trafficLog.classList.toggle("is-loading", loading);
    refreshNow.disabled = loading;
  }

  function showError(message) {
    trafficError.hidden = !message;
    trafficError.textContent = message || "";
  }

  function setLiveStatus(mode, label) {
    ["active", "paused", "degraded", "connecting"].forEach((name) => liveIndicator.classList.toggle(name, name === mode));
    liveStatusText.textContent = label;
  }

  function applyStats(stats) {
    if (!stats) return;
    const mapping = {
      "metric-total": stats.total,
      "metric-high-risk": stats.high_risk,
      "metric-pending": stats.pending,
      "metric-errors": stats.errors,
      "metric-connects": stats.connects,
    };
    Object.entries(mapping).forEach(([id, metricValue]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = String(metricValue || 0);
    });
  }

  async function loadStats() {
    const response = await fetch("/api/traffic/stats", { headers: { Accept: "application/json" }, cache: "no-store" });
    if (response.status === 401) throw new Error("Session expired");
    if (!response.ok) throw new Error(`Stats request failed (${response.status})`);
    applyStats(await response.json());
  }

  async function loadTraffic() {
    if (state.loading) {
      state.refreshQueued = true;
      return;
    }
    setLoading(true);
    showError("");
    const params = buildQuery();
    const requestQuery = params.toString();
    try {
      const [response] = await Promise.all([
        fetch(`/api/flows?${requestQuery}`, { headers: { Accept: "application/json" }, cache: "no-store" }),
        loadStats().catch(() => null),
      ]);
      if (response.status === 401) {
        window.location.assign("/login?next=/");
        return;
      }
      if (!response.ok) throw new Error(`Traffic request failed (${response.status})`);
      const payload = await response.json();
      if (requestQuery !== buildQuery().toString()) {
        state.refreshQueued = true;
        return;
      }
      const items = payload.items || [];
      renderLogRows(items);
      state.total = Number(payload.total || 0);
      const limit = Number(payload.limit || params.get("limit") || 250);
      filterStatus.textContent = `${items.length} shown · ${state.total} matching events`;
      lastUpdated.textContent = `Updated ${new Date(payload.generated_at || Date.now()).toLocaleTimeString()}`;
      updatePagination(limit);

      if (state.selectedFlowId) {
        const selected = items.find((item) => item.id === state.selectedFlowId);
        if (selected && (selected.updated_at || selected.started_at) !== state.selectedUpdatedAt) {
          state.selectedUpdatedAt = selected.updated_at || selected.started_at;
          openFlowDrawer(state.selectedFlowId, null, { preserveFocus: true });
        }
      }
    } catch (error) {
      showError(error instanceof Error ? error.message : "Unable to refresh traffic.");
      if (!state.socketConnected) setLiveStatus("degraded", "Fallback");
    } finally {
      setLoading(false);
      if (state.refreshQueued) {
        state.refreshQueued = false;
        queueMicrotask(loadTraffic);
      }
    }
  }

  async function loadOptions() {
    try {
      const [optionsResponse, sessionsResponse] = await Promise.all([
        fetch("/api/flows/options", { headers: { Accept: "application/json" }, cache: "no-store" }),
        fetch("/api/sessions", { headers: { Accept: "application/json" }, cache: "no-store" }),
      ]);
      if (optionsResponse.ok) {
        const options = await optionsResponse.json();
        const datalist = document.getElementById("host-options");
        if (datalist) {
          const fragment = document.createDocumentFragment();
          (options.hosts || []).forEach((host) => {
            const option = document.createElement("option");
            option.value = host;
            fragment.appendChild(option);
          });
          datalist.replaceChildren(fragment);
        }
      }
      if (sessionsResponse.ok) {
        const sessions = await sessionsResponse.json();
        const sessionSelect = document.getElementById("filter-session");
        if (sessionSelect) {
          const current = sessionSelect.value;
          Array.from(sessionSelect.options).slice(1).forEach((option) => option.remove());
          sessions.forEach((session) => {
            const option = document.createElement("option");
            option.value = session.id;
            option.textContent = `${session.name} · ${session.created_at}`;
            sessionSelect.appendChild(option);
          });
          sessionSelect.value = current;
        }
      }
    } catch (_) { /* suggestions are optional */ }
  }

  function websocketUrl() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws/traffic`;
  }

  function stopFallbackPolling() {
    if (state.fallbackTimer) clearInterval(state.fallbackTimer);
    state.fallbackTimer = null;
  }

  function startFallbackPolling() {
    if (state.fallbackTimer || !state.live) return;
    state.fallbackTimer = setInterval(() => {
      if (state.live && !document.hidden && state.offset === 0 && !state.socketConnected) loadTraffic();
    }, fallbackPollingIntervalMs);
  }

  function queueRealtimeRefresh() {
    if (!state.live || state.offset !== 0) return;
    if (state.refreshTimer) clearTimeout(state.refreshTimer);
    state.refreshTimer = setTimeout(() => {
      state.refreshTimer = null;
      loadTraffic();
    }, realtimeRefreshDebounceMs);
  }

  function scheduleReconnect() {
    if (!state.live || state.reconnectTimer) return;
    const delay = Math.min(10000, 750 * (2 ** state.reconnectAttempts));
    state.reconnectAttempts += 1;
    state.reconnectTimer = setTimeout(() => {
      state.reconnectTimer = null;
      connectTrafficStream();
    }, delay);
  }

  function connectTrafficStream() {
    if (!state.live) return;
    if (!("WebSocket" in window)) {
      setLiveStatus("degraded", "Polling fallback");
      startFallbackPolling();
      return;
    }
    if (state.socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(state.socket.readyState)) return;
    setLiveStatus("connecting", "Connecting");
    const socket = new WebSocket(websocketUrl());
    state.socket = socket;
    socket.addEventListener("open", () => {
      if (state.socket !== socket) return;
      state.socketConnected = true;
      state.reconnectAttempts = 0;
      stopFallbackPolling();
      setLiveStatus("active", "Live");
      showError("");
    });
    socket.addEventListener("message", (event) => {
      if (state.socket !== socket) return;
      let payload;
      try { payload = JSON.parse(event.data); } catch (_) { return; }
      if (payload.revision !== undefined) state.lastRevision = payload.revision;
      if (payload.type === "ready") {
        setLiveStatus("active", "Live");
        queueRealtimeRefresh();
      } else if (payload.type === "traffic_changed") {
        applyStats(payload.stats);
        queueRealtimeRefresh();
      } else if (payload.type === "heartbeat" || payload.type === "pong") {
        setLiveStatus("active", "Live");
      }
    });
    socket.addEventListener("error", () => {
      if (socket.readyState === WebSocket.OPEN) socket.close(1011, "Transport error");
    });
    socket.addEventListener("close", (event) => {
      if (state.socket !== socket) return;
      state.socket = null;
      state.socketConnected = false;
      if (!state.live) return;
      if (event.code === 4401) {
        setLiveStatus("degraded", "Session expired");
        showError("Your console session expired. Sign in again to resume live traffic.");
        setTimeout(() => window.location.assign("/login?next=/"), 900);
        return;
      }
      if (event.code === 4403) {
        setLiveStatus("degraded", "Blocked");
        showError("The live traffic connection was rejected by the origin policy.");
        return;
      }
      setLiveStatus("degraded", "Reconnecting");
      startFallbackPolling();
      scheduleReconnect();
    });
  }

  function disconnectTrafficStream() {
    if (state.reconnectTimer) clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
    stopFallbackPolling();
    if (state.socket) {
      const socket = state.socket;
      state.socket = null;
      state.socketConnected = false;
      if ([WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) socket.close(1000, "Live updates paused");
    }
  }

  function setLive(live) {
    state.live = live;
    toggleLive.textContent = live ? "Pause live" : "Resume live";
    if (!live) {
      disconnectTrafficStream();
      setLiveStatus("paused", "Paused");
      return;
    }
    setLiveStatus("connecting", "Connecting");
    loadTraffic();
    connectTrafficStream();
  }

  let debounceTimer = null;
  [document.getElementById("filter-q"), document.getElementById("filter-host")].forEach((control) => {
    if (!control) return;
    control.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.offset = 0;
        saveFilters();
        renderActiveFilters();
        loadTraffic();
      }, 350);
    });
  });

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    state.offset = 0;
    saveFilters();
    renderActiveFilters();
    loadTraffic();
  });
  filterForm.querySelectorAll("select, input[type=number]").forEach((control) => {
    control.addEventListener("change", () => {
      state.offset = 0;
      saveFilters();
      renderActiveFilters();
      loadTraffic();
    });
  });
  toggleLive.addEventListener("click", () => setLive(!state.live));
  refreshNow.addEventListener("click", loadTraffic);
  resetFilters.addEventListener("click", () => {
    filterForm.reset();
    document.getElementById("filter-limit").value = "250";
    document.getElementById("filter-order").value = "desc";
    state.offset = 0;
    try { localStorage.removeItem(persistedKey); } catch (_) { /* optional */ }
    renderActiveFilters();
    loadTraffic();
  });
  previousPage.addEventListener("click", () => {
    const limit = Number(document.getElementById("filter-limit").value || 250);
    state.offset = Math.max(0, state.offset - limit);
    setLive(false);
    loadTraffic();
  });
  nextPage.addEventListener("click", () => {
    const limit = Number(document.getElementById("filter-limit").value || 250);
    state.offset += limit;
    setLive(false);
    loadTraffic();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.live) {
      loadTraffic();
      connectTrafficStream();
    }
  });
  window.addEventListener("beforeunload", disconnectTrafficStream);

  async function initializeDashboard() {
    restoreFilters();
    renderActiveFilters();
    await loadOptions();
    restoreFilters();
    renderActiveFilters();
    await loadTraffic();
    connectTrafficStream();
  }

  initializeDashboard();
})();
