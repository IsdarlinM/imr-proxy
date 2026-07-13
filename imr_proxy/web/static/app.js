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

  function labelMobileTable(table) {
    if (!table) return;
    const labels = Array.from(table.querySelectorAll("thead th")).map((cell) =>
      (cell.textContent || "").trim()
    );
    table.querySelectorAll("tbody tr").forEach((row) => {
      row.querySelectorAll("td").forEach((cell, index) => {
        if (!cell.classList.contains("empty") && !cell.dataset.label) {
          cell.dataset.label = labels[index] || "Field";
        }
      });
    });
  }

  document.querySelectorAll(".data-table.mobile-cards").forEach(labelMobileTable);

  document.querySelectorAll(".data-table tbody tr").forEach((row) => {
    row.addEventListener("mouseenter", () => row.classList.add("row-active"));
    row.addEventListener("mouseleave", () => row.classList.remove("row-active"));
  });

  const filterForm = document.getElementById("traffic-filters");
  const flowTable = document.getElementById("flows");
  if (!filterForm || !flowTable) return;

  const tableBody = flowTable.querySelector("tbody");
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
  };

  const fallbackPollingIntervalMs = 3000;
  const realtimeRefreshDebounceMs = 80;
  const persistedKey = "imr-proxy-traffic-filters-v2";

  function text(value) {
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleTimeString([], {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function formatDuration(value) {
    if (value === null || value === undefined) return "—";
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return `${numeric.toFixed(1)} ms`;
  }

  function createCell(label, className) {
    const cell = document.createElement("td");
    cell.dataset.label = label;
    if (className) cell.className = className;
    return cell;
  }

  function badge(value, kind) {
    const element = document.createElement("span");
    const safeValue = String(value || (kind === "severity" ? "info" : "unknown")).toLowerCase();
    const safeClass = safeValue.replace(/[^a-z0-9_-]/g, "-");
    element.className = kind === "severity"
      ? `pill sev-${safeClass}`
      : `${kind}-badge ${kind}-${safeClass}`;
    element.textContent = safeValue;
    return element;
  }

  function renderRows(items) {
    const fragment = document.createDocumentFragment();
    if (!items.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 8;
      cell.className = "empty";
      cell.textContent = "No traffic matches the active filters.";
      row.appendChild(cell);
      fragment.appendChild(row);
      tableBody.replaceChildren(fragment);
      return;
    }

    items.forEach((flow) => {
      const row = document.createElement("tr");
      row.dataset.flowId = flow.id;

      const timeCell = createCell("Time", "nowrap");
      timeCell.textContent = formatDate(flow.updated_at || flow.started_at);
      timeCell.title = text(flow.updated_at || flow.started_at);
      row.appendChild(timeCell);

      const typeCell = createCell("Type");
      typeCell.appendChild(badge(flow.event_type || "http", "event"));
      row.appendChild(typeCell);

      const stateCell = createCell("State");
      stateCell.appendChild(badge(flow.state || "complete", "state"));
      row.appendChild(stateCell);

      const methodCell = createCell("Method");
      const method = document.createElement("span");
      method.className = "method";
      method.textContent = text(flow.method);
      methodCell.appendChild(method);
      row.appendChild(methodCell);

      const urlCell = createCell("Host / URL", "url");
      const urlLink = document.createElement("a");
      urlLink.href = `/flows/${encodeURIComponent(flow.id)}`;
      urlLink.textContent = text(flow.url || flow.host);
      urlLink.title = text(flow.url || flow.host);
      urlCell.appendChild(urlLink);
      if (flow.error_message) {
        const error = document.createElement("small");
        error.className = "row-error";
        error.textContent = flow.error_message;
        urlCell.appendChild(error);
      }
      row.appendChild(urlCell);

      const statusCell = createCell("Status");
      statusCell.textContent = text(flow.status_code);
      row.appendChild(statusCell);

      const durationCell = createCell("Duration");
      durationCell.textContent = formatDuration(flow.duration_ms);
      row.appendChild(durationCell);

      const severityCell = createCell("Severity");
      severityCell.appendChild(badge(flow.highest_severity || "info", "severity"));
      row.appendChild(severityCell);

      row.addEventListener("mouseenter", () => row.classList.add("row-active"));
      row.addEventListener("mouseleave", () => row.classList.remove("row-active"));
      fragment.appendChild(row);
    });
    tableBody.replaceChildren(fragment);
  }

  function rawFormValues() {
    const values = {};
    new FormData(filterForm).forEach((value, key) => {
      const normalized = String(value).trim();
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
    const values = formValues();
    const params = new URLSearchParams(values);
    params.set("meta", "true");
    params.set("offset", String(state.offset));
    return params;
  }

  function saveFilters() {
    try {
      localStorage.setItem(persistedKey, JSON.stringify(rawFormValues()));
    } catch (_) {
      // Local storage may be disabled. Filtering still works.
    }
  }

  function restoreFilters() {
    try {
      const saved = JSON.parse(localStorage.getItem(persistedKey) || "{}");
      Object.entries(saved).forEach(([key, value]) => {
        const control = filterForm.elements.namedItem(key);
        if (control && typeof value === "string") control.value = value;
      });
    } catch (_) {
      // Ignore malformed or unavailable local storage.
    }
  }

  function renderActiveFilters() {
    activeFilters.replaceChildren();
    const ignored = new Set(["limit", "order"]);
    const values = formValues();
    Object.entries(values).forEach(([key, value]) => {
      if (ignored.has(key)) return;
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "filter-chip";
      chip.textContent = `${key.replaceAll("_", " ")}: ${value} ×`;
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
    if (!activeFilters.children.length) {
      const empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = "No advanced filters active";
      activeFilters.appendChild(empty);
    }
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
    flowTable.classList.toggle("is-loading", loading);
    refreshNow.disabled = loading;
  }

  function showError(message) {
    trafficError.hidden = !message;
    trafficError.textContent = message || "";
  }

  function setLiveStatus(mode, label) {
    ["active", "paused", "degraded", "connecting"].forEach((name) => {
      liveIndicator.classList.toggle(name, name === mode);
    });
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
    Object.entries(mapping).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = String(value || 0);
    });
  }

  async function loadStats() {
    const response = await fetch("/api/traffic/stats", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (response.status === 401) {
      window.location.assign("/login?next=/");
      throw new Error("Session expired");
    }
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
        fetch(`/api/flows?${requestQuery}`, {
          headers: { Accept: "application/json" },
          cache: "no-store",
        }),
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

      renderRows(payload.items || []);
      state.total = Number(payload.total || 0);
      const limit = Number(payload.limit || params.get("limit") || 250);
      filterStatus.textContent = `${(payload.items || []).length} shown · ${state.total} matching events`;
      lastUpdated.textContent = `Updated ${new Date(payload.generated_at || Date.now()).toLocaleTimeString()}`;
      updatePagination(limit);
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
    } catch (_) {
      // Optional filter suggestions must not break the live console.
    }
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
      if (state.live && !document.hidden && state.offset === 0 && !state.socketConnected) {
        loadTraffic();
      }
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
      try {
        payload = JSON.parse(event.data);
      } catch (_) {
        return;
      }
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
      if ([WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) {
        socket.close(1000, "Live updates paused");
      }
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
    try {
      localStorage.removeItem(persistedKey);
    } catch (_) {
      // Ignore unavailable local storage.
    }
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
