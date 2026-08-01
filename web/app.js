const state = {
  token: localStorage.getItem("idp_token") || "",
  currentUser: null,
  mode: "login",
  catalog: { apps: [], images: [] },
  destinations: [],
  applications: [],
  workloads: [],
  systemReadiness: {
    dispatch_token_present: false,
    callback_token_present: false,
    preview_routing_configured: false,
  },
  deploymentPollTimer: null,
  sandboxPollTimer: null,
  sandboxCountdownTimer: null,
  sandboxDeployment: null,
  refreshInFlight: false,
};

const SANDBOX_HOST = window.SANDBOX_HOST || "localhost";

const elements = Object.fromEntries(
  [
    "sessionStatus", "logoutButton", "loginTab", "registerTab", "authForm", "authSubmit",
    "authMessage", "username", "password", "destinationCount", "destinationList", "apiHealth",
    "applicationCount", "readyDestinationCount", "workloadCount", "toggleCreateButton",
    "applicationForm", "templateSelect", "appName", "imageField", "image", "repositoryField",
    "repositoryUrl", "port", "environment", "destinationSelect", "selectedDestinationReadiness",
    "applicationReview", "applicationMessage", "cancelCreateButton", "applicationList",
    "refreshButton", "refreshStatus", "workloadList", "logsTarget", "logsOutput",
    "sandboxTemplate", "sandboxLaunchButton", "sandboxStatus", "sandboxDeploymentId",
    "sandboxCountdown", "sandboxPort", "sandboxOpenLink", "sandboxMessage", "sourceRepositoryOption",
  ].map((id) => [id, document.querySelector(`#${id}`)])
);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    if (typeof payload === "string" && contentType.includes("text/html")) {
      const title = payload.match(/<title>(.*?)<\/title>/i)?.[1]?.replace(/\s+/g, " ").trim();
      throw new Error(title || `Request failed with HTTP ${response.status}`);
    }
    const detail = payload.detail || payload || "Request failed";
    if (Array.isArray(detail)) {
      throw new Error(detail.map((item) => `${item.loc?.at(-1) || "request"}: ${item.msg}`).join(". "));
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function statusClass(status) {
  return `pill status-${escapeHtml(status)}`;
}

function terminalSandboxStatus(status) {
  return ["running", "expired", "failed", "stopped"].includes(status);
}

function sandboxHostPort(deployment) {
  return deployment?.metadata_json?.host_port || deployment?.port || deployment?.container_port;
}

function sandboxIsExpired(deployment) {
  return Boolean(deployment?.expires_at && new Date(deployment.expires_at).getTime() <= Date.now());
}

function workloadHostPort(workload) {
  return workload?.metadata_json?.host_port || workload?.port;
}

function shortRuntimeId(workload) {
  const runtimeId = workload?.metadata_json?.runtime_id || "";
  return runtimeId ? runtimeId.slice(0, 12) : "Not reported";
}

function workloadHealthUrl(workload) {
  return workload?.metadata_json?.health_url || "";
}

function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function stopSandboxPoll() {
  if (state.sandboxPollTimer) {
    window.clearTimeout(state.sandboxPollTimer);
    state.sandboxPollTimer = null;
  }
}

function stopSandboxCountdown() {
  if (state.sandboxCountdownTimer) {
    window.clearInterval(state.sandboxCountdownTimer);
    state.sandboxCountdownTimer = null;
  }
}

function renderSandbox(deployment) {
  const effectiveDeployment = deployment && sandboxIsExpired(deployment) && !["failed", "stopped"].includes(deployment.status)
    ? { ...deployment, status: "expired" }
    : deployment;
  state.sandboxDeployment = effectiveDeployment;
  const status = effectiveDeployment?.status || "idle";
  elements.sandboxStatus.className = statusClass(status);
  elements.sandboxStatus.textContent = status.replaceAll("_", " ");
  elements.sandboxDeploymentId.textContent = effectiveDeployment?.id ? `#${effectiveDeployment.id}` : "Not started";
  const hostPort = sandboxHostPort(effectiveDeployment);
  elements.sandboxPort.textContent = hostPort || "Pending";

  if (status === "running" && state.systemReadiness.preview_routing_configured && effectiveDeployment?.url) {
    elements.sandboxOpenLink.href = effectiveDeployment.url;
    elements.sandboxOpenLink.hidden = false;
  } else {
    elements.sandboxOpenLink.hidden = true;
    elements.sandboxOpenLink.removeAttribute("href");
  }

  elements.sandboxLaunchButton.disabled = status === "queued";
  if (effectiveDeployment?.last_error) {
    elements.sandboxMessage.textContent = effectiveDeployment.last_error;
  } else if (status === "running" && !state.systemReadiness.preview_routing_configured) {
    elements.sandboxMessage.textContent = `Runtime Created (Port :${hostPort}). Preview routing is not configured.`;
  } else if (status === "expired") {
    elements.sandboxMessage.textContent = "Sandbox expired and the preview container was removed.";
  }
}

function tickSandboxCountdown() {
  const deployment = state.sandboxDeployment;
  if (!deployment?.expires_at) {
    elements.sandboxCountdown.textContent = "--:--";
    return;
  }
  const remaining = new Date(deployment.expires_at).getTime() - Date.now();
  elements.sandboxCountdown.textContent = formatDuration(remaining);
  if (remaining <= 0 && !["expired", "failed", "stopped"].includes(deployment.status)) {
    renderSandbox({ ...deployment, status: "expired" });
    stopSandboxPoll();
    stopSandboxCountdown();
  }
}

function startSandboxCountdown() {
  stopSandboxCountdown();
  tickSandboxCountdown();
  state.sandboxCountdownTimer = window.setInterval(tickSandboxCountdown, 1000);
}

async function pollSandboxDeployment(id) {
  stopSandboxPoll();
  try {
    const deployment = await api(`/deployments/${id}`);
    renderSandbox(deployment);
    startSandboxCountdown();
    if (deployment.status === "queued") {
      state.sandboxPollTimer = window.setTimeout(() => pollSandboxDeployment(id), 3000);
    }
    if (terminalSandboxStatus(deployment.status)) {
      await loadWorkloads();
    }
  } catch (error) {
    elements.sandboxMessage.textContent = error.message;
  }
}

async function handleSandboxLaunch() {
  stopSandboxPoll();
  stopSandboxCountdown();
  elements.sandboxMessage.textContent = "Launching sandbox...";
  elements.sandboxLaunchButton.disabled = true;
  elements.sandboxOpenLink.hidden = true;
  try {
    const template = elements.sandboxTemplate.value;
    const deployment = await api(`/sandbox/demo?template=${encodeURIComponent(template)}`, {
      method: "POST",
      body: JSON.stringify({ template }),
    });
    elements.sandboxMessage.textContent = "";
    renderSandbox(deployment);
    startSandboxCountdown();
    if (deployment.status === "queued") {
      state.sandboxPollTimer = window.setTimeout(() => pollSandboxDeployment(deployment.id), 3000);
    }
    await loadWorkloads();
  } catch (error) {
    elements.sandboxMessage.textContent = error.message;
    elements.sandboxLaunchButton.disabled = false;
    renderSandbox({ status: "failed" });
  }
}

function setMode(mode) {
  state.mode = mode;
  elements.loginTab.classList.toggle("active", mode === "login");
  elements.registerTab.classList.toggle("active", mode === "register");
  elements.authSubmit.textContent = mode === "login" ? "Login" : "Register";
  elements.authMessage.textContent = "";
}

function setSignedIn(signedIn) {
  elements.sessionStatus.textContent = state.currentUser
    ? `${state.currentUser.username} (${state.currentUser.role})`
    : signedIn ? "Signed in" : "Signed out";
  elements.logoutButton.disabled = !signedIn;
  elements.toggleCreateButton.disabled = !signedIn;
  elements.refreshButton.disabled = !signedIn;
}

function sourceType() {
  return document.querySelector('input[name="sourceType"]:checked').value;
}

function requestedResources() {
  return [...document.querySelectorAll('input[name="resource"]:checked')].map((input) => input.value);
}

function renderCatalog(catalog) {
  state.catalog = catalog;
  elements.templateSelect.innerHTML = [
    '<option value="" disabled>Choose an allowlisted template</option>',
    ...catalog.apps.map((app) => `<option value="${escapeHtml(app.id)}">${escapeHtml(app.name)}</option>`),
  ].join("");
  if (catalog.apps.length) {
    elements.templateSelect.value = catalog.apps[0].id;
    applyTemplate(catalog.apps[0].id);
  }
}

async function loadCatalog() {
  renderCatalog(await api("/catalog", { headers: {} }));
}

function destinationLabel(destination) {
  const provider = destination.provider.replaceAll("_", " ");
  return `${destination.name} · ${provider} · ${destination.status.replaceAll("_", " ")}`;
}

function renderDestinations(destinations) {
  state.destinations = destinations;
  const ready = destinations.filter((destination) => destination.readiness.ready).length;
  elements.destinationCount.textContent = `${ready} ready`;
  elements.readyDestinationCount.textContent = `${ready} / ${destinations.length}`;
  elements.destinationSelect.innerHTML = [
    '<option value="">Select a destination</option>',
    ...destinations.map((destination) => (
      `<option value="${destination.id}">${escapeHtml(destinationLabel(destination))}</option>`
    )),
  ].join("");
  elements.destinationList.innerHTML = destinations.map((destination) => `
    <div class="destination-row">
      <div>
        <strong>${escapeHtml(destination.name)}</strong>
        <span class="meta">${escapeHtml(destination.kind.replaceAll("_", " "))}</span>
      </div>
      <span class="${statusClass(destination.status)}">${escapeHtml(destination.status.replaceAll("_", " "))}</span>
    </div>
  `).join("");
}

function renderSelectedDestination() {
  const destination = state.destinations.find((item) => item.id === Number(elements.destinationSelect.value));
  if (!destination) {
    elements.selectedDestinationReadiness.textContent = "Choose a destination to see its readiness.";
    updateReview();
    return;
  }
  const missing = destination.readiness.missing || [];
  elements.selectedDestinationReadiness.innerHTML = destination.readiness.ready
    ? `<strong>Ready</strong><span>This destination can accept application deployments.</span>`
    : `<strong>Setup required</strong><span>${missing.map(escapeHtml).join(" · ")}</span>`;
  updateReview();
}

async function loadDestinations() {
  if (!state.token) return;
  renderDestinations(await api("/destinations"));
}

function renderApplications(applications) {
  state.applications = applications;
  elements.applicationCount.textContent = `${applications.length} registered`;
  if (!applications.length) {
    elements.applicationList.innerHTML = '<p class="empty-state">No applications registered yet.</p>';
    return;
  }
  elements.applicationList.innerHTML = applications.map((application) => {
    const source = application.repository_url || application.image || "source pending";
    const resources = application.resource_requests.length
      ? application.resource_requests.map((item) => item.replaceAll("_", " ")).join(", ")
      : "No dependencies requested";
    return `
      <article class="application-card">
        <header>
          <div>
            <h3>${escapeHtml(application.name)}</h3>
            <p class="meta">${escapeHtml(source)}</p>
          </div>
          <span class="${statusClass(application.status)}">${escapeHtml(application.status.replaceAll("_", " "))}</span>
        </header>
        <dl>
          <div><dt>Destination</dt><dd>${escapeHtml(application.destination?.name || "unknown")}</dd></div>
          <div><dt>Environment</dt><dd>${escapeHtml(application.environment)}</dd></div>
          <div><dt>Resources</dt><dd>${escapeHtml(resources)}</dd></div>
          <div><dt>URL</dt><dd>${application.metadata_json.url
            ? `<a href="${escapeHtml(application.metadata_json.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(application.metadata_json.url)}</a>`
            : "Not published"}</dd></div>
        </dl>
        ${application.status === "setup_required"
          ? '<p class="notice">This application is cataloged, but its destination or resources still require operator setup.</p>'
          : ""}
        ${application.metadata_json.last_error
          ? `<p class="notice">${escapeHtml(application.metadata_json.last_error)}</p>`
          : ""}
        <div class="row-actions">
          ${["ready_to_deploy", "failed", "running"].includes(application.status)
            ? `<button type="button" data-application-action="deploy" data-id="${application.id}">${application.status === "running" ? "Redeploy" : "Deploy"}</button>`
            : ""}
          ${["queued", "deploying"].includes(application.status)
            ? '<button type="button" disabled>Deployment in progress</button>'
            : ""}
        </div>
      </article>
    `;
  }).join("");
}

function scheduleDeploymentPoll() {
  if (state.deploymentPollTimer) {
    window.clearTimeout(state.deploymentPollTimer);
    state.deploymentPollTimer = null;
  }
  const deploymentActive = state.applications.some((application) =>
    ["queued", "deploying"].includes(application.status)
  );
  if (!state.token || !deploymentActive) return;
  elements.refreshStatus.textContent = "Watching deployment";
  state.deploymentPollTimer = window.setTimeout(() => refreshDashboard(false), 5000);
}

async function loadApplications() {
  if (!state.token) return;
  renderApplications(await api("/applications"));
}

function renderWorkloads(workloads) {
  state.workloads = workloads;
  const running = workloads.filter((workload) => workload.status === "running").length;
  elements.workloadCount.textContent = `${running} running`;
  if (!workloads.length) {
    elements.workloadList.innerHTML = state.token
      ? '<p class="empty-state">No runtime workloads are connected.</p>'
      : '<p class="empty-state">Sign in to inspect runtime workloads.</p>';
    return;
  }
  elements.workloadList.innerHTML = workloads.map((workload) => {
    const hostPort = workloadHostPort(workload);
    const healthUrl = workloadHealthUrl(workload);
    const logs = workload.metadata_json?.logs;
    return `
      <div class="workload-row">
        <div class="workload-main">
          <div class="workload-title">
            <strong>${escapeHtml(workload.name)}</strong>
            <span class="${statusClass(workload.status)}">${escapeHtml(workload.status.replaceAll("_", " "))}</span>
          </div>
          <span class="meta">${escapeHtml(workload.image)} · ${escapeHtml(workload.namespace)}</span>
          <div class="workload-facts">
            <span>Runtime ${escapeHtml(shortRuntimeId(workload))}</span>
            <span>Port ${escapeHtml(hostPort || "pending")}</span>
            <span>${logs ? "Logs reported" : "No logs yet"}</span>
          </div>
          <div class="workload-links">
            ${workload.url
              ? `<a href="${escapeHtml(workload.url)}" target="_blank" rel="noopener noreferrer">Open URL</a>`
              : '<span class="meta">URL pending</span>'}
            ${healthUrl
              ? `<a href="${escapeHtml(healthUrl)}" target="_blank" rel="noopener noreferrer">Health</a>`
              : ""}
          </div>
        </div>
        <div class="row-actions">
          <button class="ghost" type="button" data-action="status" data-id="${workload.id}">Status</button>
          <button class="ghost" type="button" data-action="logs" data-id="${workload.id}" data-name="${escapeHtml(workload.name)}" data-namespace="${escapeHtml(workload.namespace)}">Logs</button>
        </div>
      </div>
    `;
  }).join("");
}

async function loadWorkloads() {
  if (!state.token) return;
  renderWorkloads(await api("/deployments"));
}

function applyTemplate(templateId) {
  const template = state.catalog.apps.find((item) => item.id === templateId);
  if (!template) return;
  document.querySelector('input[name="sourceType"][value="container_image"]').checked = true;
  elements.appName.value = template.default_app_name;
  elements.image.value = template.image;
  elements.port.value = template.port;
  updateSourceFields();
  updateReview();
}

function updateSourceFields() {
  const repository = sourceType() === "repository";
  if (repository) {
    document.querySelector('input[name="sourceType"][value="container_image"]').checked = true;
  }
  elements.repositoryField.hidden = true;
  elements.imageField.hidden = false;
  elements.repositoryUrl.required = false;
  elements.image.required = true;
  elements.image.readOnly = true;
  updateReview();
}

function updateReview() {
  const destination = state.destinations.find((item) => item.id === Number(elements.destinationSelect.value));
  const resources = requestedResources();
  const source = sourceType() === "repository" ? elements.repositoryUrl.value : elements.image.value;
  elements.applicationReview.innerHTML = `
    <div><span class="meta">Application</span><strong>${escapeHtml(elements.appName.value || "Not set")}</strong></div>
    <div><span class="meta">Source</span><strong>${escapeHtml(source || "Not set")}</strong></div>
    <div><span class="meta">Destination</span><strong>${escapeHtml(destination?.name || "Not selected")}</strong></div>
    <div><span class="meta">Dependencies</span><strong>${escapeHtml(resources.length ? resources.join(", ") : "None")}</strong></div>
  `;
}

function toggleApplicationForm(show) {
  elements.applicationForm.hidden = !show;
  elements.toggleCreateButton.textContent = show ? "Close" : "New application";
  if (show) updateReview();
}

async function handleApplicationCreate(event) {
  event.preventDefault();
  elements.applicationMessage.textContent = "Registering application...";
  const payload = {
    name: elements.appName.value.trim(),
    source_type: sourceType(),
    repository_url: elements.repositoryUrl.value.trim() || null,
    image: elements.image.value.trim() || null,
    port: Number(elements.port.value),
    destination_id: Number(elements.destinationSelect.value),
    environment: elements.environment.value,
    resource_requests: requestedResources(),
  };
  try {
    const application = await api("/applications", { method: "POST", body: JSON.stringify(payload) });
    elements.applicationMessage.textContent = `${application.name} is registered as ${application.status.replaceAll("_", " ")}.`;
    elements.applicationForm.reset();
    elements.port.value = 80;
    updateSourceFields();
    await loadApplications();
    toggleApplicationForm(false);
  } catch (error) {
    elements.applicationMessage.textContent = error.message;
  }
}

async function handleAuth(event) {
  event.preventDefault();
  try {
    if (state.mode === "register") {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username: elements.username.value.trim(), password: elements.password.value }),
      });
    }
    const login = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: elements.username.value.trim(), password: elements.password.value }),
    });
    state.token = login.access_token;
    localStorage.setItem("idp_token", state.token);
    state.currentUser = await api("/auth/me");
    setSignedIn(true);
    elements.authMessage.textContent = "Signed in.";
    await Promise.all([loadDestinations(), loadApplications(), loadWorkloads()]);
    scheduleDeploymentPoll();
  } catch (error) {
    elements.authMessage.textContent = error.message;
  }
}

async function handleWorkloadAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  try {
    if (button.dataset.action === "status") {
      const workload = await api(`/deployments/${button.dataset.id}`);
      elements.logsTarget.textContent = workload.name;
      elements.logsOutput.textContent = JSON.stringify(workload, null, 2);
    } else {
      const workload = state.workloads.find((item) => item.id === Number(button.dataset.id));
      if (workload?.metadata_json?.runtime === "linux_docker") {
        elements.logsTarget.textContent = workload.name;
        elements.logsOutput.textContent = workload.metadata_json.logs || "No runtime logs have been reported yet.";
      } else {
        elements.logsTarget.textContent = `${button.dataset.namespace}/${button.dataset.name}`;
        const result = await api(
          `/monitoring/logs/${encodeURIComponent(button.dataset.name)}?namespace=${encodeURIComponent(button.dataset.namespace)}`
        );
        elements.logsOutput.textContent = result.logs;
      }
    }
  } catch (error) {
    elements.logsOutput.textContent = error.message;
  }
}

async function handleApplicationAction(event) {
  const button = event.target.closest("button[data-application-action]");
  if (!button) return;
  button.disabled = true;
  button.textContent = "Queuing...";
  try {
    await api(`/applications/${button.dataset.id}/deploy`, { method: "POST" });
    await loadApplications();
    scheduleDeploymentPoll();
  } catch (error) {
    elements.applicationMessage.textContent = error.message;
    button.disabled = false;
    button.textContent = "Deploy";
  }
}

async function loadApiHealth() {
  try {
    const readiness = await api("/readyz", { headers: {} });
    elements.apiHealth.textContent = readiness.status;
  } catch {
    elements.apiHealth.textContent = "not ready";
  }
}

async function loadSystemReadiness() {
  try {
    state.systemReadiness = await api("/system/readiness", { headers: {} });
    elements.sandboxLaunchButton.disabled = !(
      state.systemReadiness.dispatch_token_present && state.systemReadiness.callback_token_present
    );
    if (state.sandboxDeployment) renderSandbox(state.sandboxDeployment);
  } catch {
    state.systemReadiness = {
      dispatch_token_present: false,
      callback_token_present: false,
      preview_routing_configured: false,
    };
  }
}

function updateActiveNav() {
  const hash = window.location.hash || "#applications";
  document.querySelectorAll(".topnav a").forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === hash);
  });
}

async function refreshDashboard(announce = true) {
  if (!state.token || state.refreshInFlight) return;
  state.refreshInFlight = true;
  if (announce) {
    elements.refreshButton.disabled = true;
    elements.refreshButton.textContent = "Refreshing...";
    elements.refreshStatus.textContent = "";
  }
  try {
    const results = await Promise.allSettled([
      loadApplications(),
      loadDestinations(),
      loadWorkloads(),
      loadApiHealth(),
      loadSystemReadiness(),
    ]);
    const failures = results.filter((result) => result.status === "rejected");
    elements.refreshStatus.textContent = failures.length
      ? `Updated with ${failures.length} error${failures.length === 1 ? "" : "s"}`
      : `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    if (failures.length) {
      elements.logsOutput.textContent = failures
        .map((result) => result.reason?.message || "Refresh request failed")
        .join("\n");
    }
  } finally {
    state.refreshInFlight = false;
    if (announce) {
      elements.refreshButton.textContent = "Refresh";
      elements.refreshButton.disabled = false;
    }
    scheduleDeploymentPoll();
  }
}

elements.loginTab.addEventListener("click", () => setMode("login"));
elements.registerTab.addEventListener("click", () => setMode("register"));
elements.authForm.addEventListener("submit", handleAuth);
elements.logoutButton.addEventListener("click", () => {
  if (state.deploymentPollTimer) window.clearTimeout(state.deploymentPollTimer);
  state.deploymentPollTimer = null;
  stopSandboxPoll();
  stopSandboxCountdown();
  state.token = "";
  state.currentUser = null;
  localStorage.removeItem("idp_token");
  setSignedIn(false);
  renderApplications([]);
  renderDestinations([]);
  renderWorkloads([]);
});
elements.toggleCreateButton.addEventListener("click", () => toggleApplicationForm(elements.applicationForm.hidden));
elements.cancelCreateButton.addEventListener("click", () => toggleApplicationForm(false));
elements.applicationForm.addEventListener("submit", handleApplicationCreate);
elements.templateSelect.addEventListener("change", (event) => applyTemplate(event.target.value));
elements.destinationSelect.addEventListener("change", renderSelectedDestination);
elements.applicationForm.addEventListener("input", updateReview);
document.querySelectorAll('input[name="sourceType"]').forEach((input) => input.addEventListener("change", updateSourceFields));
elements.refreshButton.addEventListener("click", () => refreshDashboard());
elements.workloadList.addEventListener("click", handleWorkloadAction);
elements.applicationList.addEventListener("click", handleApplicationAction);
elements.sandboxLaunchButton.addEventListener("click", handleSandboxLaunch);
window.addEventListener("hashchange", updateActiveNav);

setSignedIn(Boolean(state.token));
updateActiveNav();
loadCatalog().catch(() => {});
loadApiHealth();
loadSystemReadiness();
if (state.token) {
  api("/auth/me")
    .then((user) => {
      state.currentUser = user;
      setSignedIn(true);
      return Promise.all([loadDestinations(), loadApplications(), loadWorkloads()])
        .then(scheduleDeploymentPoll);
    })
    .catch(() => {
      state.token = "";
      localStorage.removeItem("idp_token");
      setSignedIn(false);
    });
}
