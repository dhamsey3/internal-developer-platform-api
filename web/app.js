const state = {
  token: localStorage.getItem("idp_token") || "",
  currentUser: null,
  mode: "login",
  kubernetesDryRun: true,
  catalog: { apps: [], images: [] },
  selectedTemplate: null,
};

const elements = {
  sessionStatus: document.querySelector("#sessionStatus"),
  logoutButton: document.querySelector("#logoutButton"),
  loginTab: document.querySelector("#loginTab"),
  registerTab: document.querySelector("#registerTab"),
  authForm: document.querySelector("#authForm"),
  authSubmit: document.querySelector("#authSubmit"),
  authMessage: document.querySelector("#authMessage"),
  username: document.querySelector("#username"),
  password: document.querySelector("#password"),
  clusterForm: document.querySelector("#clusterForm"),
  clusterStatus: document.querySelector("#clusterStatus"),
  clusterMessage: document.querySelector("#clusterMessage"),
  awsPreflightButton: document.querySelector("#awsPreflightButton"),
  monitoringRefreshButton: document.querySelector("#monitoringRefreshButton"),
  apiHealth: document.querySelector("#apiHealth"),
  clusterHealth: document.querySelector("#clusterHealth"),
  nodeHealth: document.querySelector("#nodeHealth"),
  applicationHealth: document.querySelector("#applicationHealth"),
  monitoringMessage: document.querySelector("#monitoringMessage"),
  deployForm: document.querySelector("#deployForm"),
  templateSelect: document.querySelector("#templateSelect"),
  imageSelect: document.querySelector("#imageSelect"),
  deployMessage: document.querySelector("#deployMessage"),
  appsList: document.querySelector("#appsList"),
  refreshButton: document.querySelector("#refreshButton"),
  logsTarget: document.querySelector("#logsTarget"),
  logsOutput: document.querySelector("#logsOutput"),
  modePill: document.querySelector("#modePill"),
};

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
      const message = detail
        .map((item) => {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "request";
          return `${field}: ${item.msg}`;
        })
        .join(". ");
      throw new Error(message);
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
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
  elements.refreshButton.disabled = !signedIn;
  elements.deployForm.querySelectorAll("input, textarea, select, button").forEach((field) => {
    field.disabled = !signedIn;
  });
  elements.clusterForm.querySelectorAll("input, button").forEach((field) => {
    field.disabled = !signedIn || state.currentUser?.role !== "admin";
  });
  elements.deployMessage.textContent = signedIn ? "" : "Sign in to deploy and manage apps.";
  if (signedIn && state.currentUser?.role !== "admin") {
    elements.clusterMessage.textContent = "Administrator access is required to provision AWS infrastructure.";
  }
}

function setValue(selector, value) {
  document.querySelector(selector).value = value;
}

function renderCatalog(catalog) {
  state.catalog = catalog;
  elements.templateSelect.innerHTML = [
    '<option value="">Custom app</option>',
    ...catalog.apps.map((app) => `<option value="${app.id}">${app.name}</option>`),
  ].join("");

  elements.imageSelect.innerHTML = [
    '<option value="">Custom image</option>',
    ...catalog.images.map((image) => `<option value="${image.image}">${image.label}</option>`),
  ].join("");
}

async function loadCatalog() {
  const catalog = await api("/catalog", { headers: {} });
  renderCatalog(catalog);
}

function applyTemplate(templateId) {
  const template = state.catalog.apps.find((app) => app.id === templateId);
  state.selectedTemplate = template || null;
  if (!template) return;
  setValue("#appName", template.default_app_name);
  setValue("#image", template.image);
  setValue("#imageSelect", template.image);
  setValue("#port", template.port);
  setValue("#replicas", template.replicas);
  setValue("#minReplicas", template.min_replicas);
  setValue("#maxReplicas", template.max_replicas);
  setValue("#cpuThreshold", template.cpu_threshold);
}

function applyImage(imageRef) {
  const image = state.catalog.images.find((item) => item.image === imageRef);
  if (!image) return;
  setValue("#image", image.image);
  setValue("#port", image.port);
}

function parseEnvVars(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .reduce((acc, line) => {
      const [key, ...rest] = line.split("=");
      if (key && rest.length) {
        acc[key.trim()] = rest.join("=").trim();
      }
      return acc;
    }, {});
}

function statusClass(status) {
  return `pill status-${status}`;
}

function renderApps(apps) {
  const running = apps.filter((app) => app.status === "running").length;
  elements.applicationHealth.textContent = `${running} running / ${apps.length} total`;
  if (!apps.length) {
    elements.appsList.innerHTML = '<p class="meta">No apps yet. Deploy your first image above.</p>';
    return;
  }

  elements.appsList.innerHTML = apps
    .map((app) => `
      <article class="app-card">
        <header>
          <div>
            <h3>${app.name}</h3>
            <p class="meta">${app.image}</p>
          </div>
          <span class="${statusClass(app.status)}">${app.status}</span>
        </header>
        <p class="meta">Namespace: ${app.namespace}</p>
        <p class="meta">Replicas: ${app.replicas} | Port: ${app.port}</p>
        <p class="meta">URL: ${app.url ? `<a href="${app.url}" target="_blank" rel="noreferrer">${app.url}</a>` : "pending"}</p>
        ${app.last_error ? `<p class="meta">Error: ${app.last_error}</p>` : ""}
        <div class="app-actions">
          <button type="button" data-action="status" data-id="${app.id}">Status</button>
          <button type="button" data-action="logs" data-name="${app.name}" data-namespace="${app.namespace}">Logs</button>
          <button class="danger" type="button" data-action="delete" data-id="${app.id}">Delete</button>
        </div>
      </article>
    `)
    .join("");
}

async function loadReadiness() {
  const ready = await api("/readyz", { headers: {} });
  state.kubernetesDryRun = ready.kubernetes_dry_run;
  elements.modePill.textContent = ready.kubernetes_dry_run || ready.terraform_dry_run ? "dry-run" : ready.environment;
  const deployButton = elements.deployForm.querySelector('button[type="submit"]');
  deployButton.disabled = !state.token || ready.kubernetes_dry_run;
  if (ready.kubernetes_dry_run && state.token) {
    elements.deployMessage.textContent = "Kubernetes is in dry-run mode. Provision and connect an EKS cluster first.";
  }
}

async function loadSession() {
  if (!state.token) return;
  state.currentUser = await api("/auth/me");
  setSignedIn(true);
}

function renderInfrastructure(items) {
  const cluster = items[0];
  if (!cluster) {
    elements.clusterStatus.textContent = "not provisioned";
    return;
  }
  elements.clusterStatus.textContent = cluster.status;
  elements.clusterStatus.className = statusClass(cluster.status);
  elements.clusterMessage.textContent = cluster.last_error || `${cluster.name} is ${cluster.status}.`;
}

async function loadInfrastructure() {
  if (!state.token) {
    renderInfrastructure([]);
    return;
  }
  renderInfrastructure(await api("/infrastructure"));
}

function clusterPayload() {
  return {
    name: document.querySelector("#clusterName").value.trim(),
    cloud_provider: "aws",
    config: {
      aws_region: document.querySelector("#awsRegion").value.trim(),
      public_access_cidrs: [document.querySelector("#publicAccessCidr").value.trim()],
      single_nat_gateway: document.querySelector("#singleNatGateway").checked,
    },
  };
}

async function loadMonitoring() {
  const ready = await api("/readyz", { headers: {} });
  elements.apiHealth.textContent = ready.status;
  if (!state.token) {
    elements.clusterHealth.textContent = "sign in required";
    elements.nodeHealth.textContent = "0 / 0";
    return;
  }
  const cluster = await api("/monitoring/cluster/health");
  elements.clusterHealth.textContent = cluster.status.replaceAll("_", " ");
  elements.nodeHealth.textContent = `${cluster.ready_nodes || 0} / ${cluster.nodes || 0}`;
  elements.monitoringMessage.textContent = cluster.mode === "dry-run"
    ? "No Kubernetes cluster is connected yet."
    : "";
}

async function handleAwsPreflight() {
  if (!elements.clusterForm.reportValidity()) return;
  elements.clusterMessage.textContent = "Validating AWS credentials and Terraform backend...";
  try {
    const result = await api("/infrastructure/preflight", {
      method: "POST",
      body: JSON.stringify(clusterPayload()),
    });
    elements.clusterMessage.textContent = result.ready
      ? "AWS setup is ready for EKS provisioning."
      : `AWS setup is incomplete: ${Object.entries(result.checks)
          .filter(([, passed]) => !passed)
          .map(([check]) => check.replaceAll("_", " "))
          .join(", ")}.`;
  } catch (error) {
    elements.clusterMessage.textContent = error.message;
  }
}

async function handleClusterProvision(event) {
  event.preventDefault();
  elements.clusterMessage.textContent = "Submitting EKS provisioning request...";
  try {
    const cluster = await api("/infrastructure/create", {
      method: "POST",
      body: JSON.stringify(clusterPayload()),
    });
    renderInfrastructure([cluster]);
  } catch (error) {
    elements.clusterMessage.textContent = error.message;
  }
}

async function loadApps() {
  if (!state.token) {
    renderApps([]);
    return;
  }
  const apps = await api("/deployments");
  renderApps(apps);
}

async function handleAuth(event) {
  event.preventDefault();
  const username = elements.username.value.trim();
  const password = elements.password.value;

  try {
    if (state.mode === "register") {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      elements.authMessage.textContent = "Account created. Logging you in...";
    }

    const login = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    state.token = login.access_token;
    localStorage.setItem("idp_token", state.token);
    await loadSession();
    setSignedIn(true);
    elements.authMessage.textContent = "Signed in.";
    await loadApps();
    await loadInfrastructure();
  } catch (error) {
    elements.authMessage.textContent = error.message;
  }
}

async function handleDeploy(event) {
  event.preventDefault();
  elements.deployMessage.textContent = "Deploying...";

  const payload = {
    name: document.querySelector("#appName").value.trim(),
    image: document.querySelector("#image").value.trim(),
    port: Number(document.querySelector("#port").value),
    replicas: Number(document.querySelector("#replicas").value),
    min_replicas: Number(document.querySelector("#minReplicas").value),
    max_replicas: Number(document.querySelector("#maxReplicas").value),
    cpu_threshold: Number(document.querySelector("#cpuThreshold").value),
    env: parseEnvVars(document.querySelector("#envVars").value),
  };

  if (state.selectedTemplate?.command) {
    payload.command = state.selectedTemplate.command;
  }

  if (state.selectedTemplate?.args) {
    payload.args = state.selectedTemplate.args;
  }

  const ingressHost = document.querySelector("#ingressHost").value.trim();
  if (ingressHost) {
    payload.ingress_host = ingressHost;
  }

  try {
    const app = await api("/deployments", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.deployMessage.textContent = `${app.name} is ${app.status}.`;
    elements.deployForm.reset();
    document.querySelector("#port").value = 80;
    document.querySelector("#replicas").value = 2;
    document.querySelector("#minReplicas").value = 1;
    document.querySelector("#maxReplicas").value = 5;
    document.querySelector("#cpuThreshold").value = 70;
    elements.templateSelect.value = "";
    elements.imageSelect.value = "";
    state.selectedTemplate = null;
    await loadApps();
  } catch (error) {
    elements.deployMessage.textContent = error.message;
  }
}

async function handleAppAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const action = button.dataset.action;
  try {
    if (action === "status") {
      const app = await api(`/deployments/${button.dataset.id}`);
      elements.logsTarget.textContent = app.name;
      elements.logsOutput.textContent = JSON.stringify(app, null, 2);
    }

    if (action === "logs") {
      elements.logsTarget.textContent = `${button.dataset.namespace}/${button.dataset.name}`;
      const logs = await api(
        `/monitoring/logs/${encodeURIComponent(button.dataset.name)}?namespace=${encodeURIComponent(button.dataset.namespace)}`
      );
      elements.logsOutput.textContent = logs.logs;
    }

    if (action === "delete") {
      await api(`/deployments/${button.dataset.id}`, { method: "DELETE" });
      await loadApps();
    }
  } catch (error) {
    elements.logsOutput.textContent = error.message;
  }
}

elements.loginTab.addEventListener("click", () => setMode("login"));
elements.registerTab.addEventListener("click", () => setMode("register"));
elements.authForm.addEventListener("submit", handleAuth);
elements.clusterForm.addEventListener("submit", handleClusterProvision);
elements.awsPreflightButton.addEventListener("click", handleAwsPreflight);
elements.monitoringRefreshButton.addEventListener("click", () => loadMonitoring().catch(() => {}));
elements.deployForm.addEventListener("submit", handleDeploy);
elements.templateSelect.addEventListener("change", (event) => applyTemplate(event.target.value));
elements.imageSelect.addEventListener("change", (event) => applyImage(event.target.value));
elements.refreshButton.addEventListener("click", loadApps);
elements.appsList.addEventListener("click", handleAppAction);
elements.logoutButton.addEventListener("click", () => {
  state.token = "";
  state.currentUser = null;
  localStorage.removeItem("idp_token");
  setSignedIn(false);
  renderInfrastructure([]);
  renderApps([]);
});

setSignedIn(Boolean(state.token));
loadSession().catch(() => {
  state.token = "";
  state.currentUser = null;
  localStorage.removeItem("idp_token");
  setSignedIn(false);
});
loadCatalog().catch(() => {});
loadReadiness().catch(() => {});
loadInfrastructure().catch(() => {});
loadMonitoring().catch(() => {});
loadApps().catch((error) => {
  elements.appsList.innerHTML = `<p class="meta">${error.message}</p>`;
});
setInterval(() => {
  if (state.token) {
    loadInfrastructure().catch(() => {});
    loadMonitoring().catch(() => {});
  }
}, 10000);
