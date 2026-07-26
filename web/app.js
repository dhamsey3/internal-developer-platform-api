const state = {
  token: localStorage.getItem("idp_token") || "",
  currentUser: null,
  mode: "login",
  catalog: { apps: [], images: [] },
  destinations: [],
  applications: [],
  workloads: [],
};

const elements = Object.fromEntries(
  [
    "sessionStatus", "logoutButton", "loginTab", "registerTab", "authForm", "authSubmit",
    "authMessage", "username", "password", "destinationCount", "destinationList", "apiHealth",
    "applicationCount", "readyDestinationCount", "workloadCount", "toggleCreateButton",
    "applicationForm", "templateSelect", "appName", "imageField", "image", "repositoryField",
    "repositoryUrl", "port", "environment", "destinationSelect", "selectedDestinationReadiness",
    "applicationReview", "applicationMessage", "cancelCreateButton", "applicationList",
    "refreshButton", "workloadList", "logsTarget", "logsOutput",
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
    '<option value="">Custom application</option>',
    ...catalog.apps.map((app) => `<option value="${escapeHtml(app.id)}">${escapeHtml(app.name)}</option>`),
  ].join("");
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

async function loadApplications() {
  if (!state.token) return;
  renderApplications(await api("/applications"));
}

function renderWorkloads(workloads) {
  state.workloads = workloads;
  const running = workloads.filter((workload) => workload.status === "running").length;
  elements.workloadCount.textContent = `${running} running`;
  if (!workloads.length) {
    elements.workloadList.innerHTML = '<p class="empty-state">No runtime workloads are connected.</p>';
    return;
  }
  elements.workloadList.innerHTML = workloads.map((workload) => `
    <div class="workload-row">
      <div>
        <strong>${escapeHtml(workload.name)}</strong>
        <span class="meta">${escapeHtml(workload.image)} · ${escapeHtml(workload.namespace)}</span>
      </div>
      <span class="${statusClass(workload.status)}">${escapeHtml(workload.status)}</span>
      <div class="row-actions">
        <button class="ghost" type="button" data-action="status" data-id="${workload.id}">Status</button>
        <button class="ghost" type="button" data-action="logs" data-name="${escapeHtml(workload.name)}" data-namespace="${escapeHtml(workload.namespace)}">Logs</button>
      </div>
    </div>
  `).join("");
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
  elements.repositoryField.hidden = !repository;
  elements.imageField.hidden = repository;
  elements.repositoryUrl.required = repository;
  elements.image.required = !repository;
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
      elements.logsTarget.textContent = `${button.dataset.namespace}/${button.dataset.name}`;
      const result = await api(
        `/monitoring/logs/${encodeURIComponent(button.dataset.name)}?namespace=${encodeURIComponent(button.dataset.namespace)}`
      );
      elements.logsOutput.textContent = result.logs;
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

elements.loginTab.addEventListener("click", () => setMode("login"));
elements.registerTab.addEventListener("click", () => setMode("register"));
elements.authForm.addEventListener("submit", handleAuth);
elements.logoutButton.addEventListener("click", () => {
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
elements.refreshButton.addEventListener("click", () => Promise.all([loadApplications(), loadDestinations(), loadWorkloads()]));
elements.workloadList.addEventListener("click", handleWorkloadAction);
elements.applicationList.addEventListener("click", handleApplicationAction);

setSignedIn(Boolean(state.token));
loadCatalog().catch(() => {});
loadApiHealth();
if (state.token) {
  api("/auth/me")
    .then((user) => {
      state.currentUser = user;
      setSignedIn(true);
      return Promise.all([loadDestinations(), loadApplications(), loadWorkloads()]);
    })
    .catch(() => {
      state.token = "";
      localStorage.removeItem("idp_token");
      setSignedIn(false);
    });
}
