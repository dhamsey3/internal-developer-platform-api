const state = {
  token: localStorage.getItem("cloudforge_token") || "",
  mode: "login",
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
  elements.sessionStatus.textContent = signedIn ? "Signed in" : "Signed out";
  elements.logoutButton.disabled = !signedIn;
  elements.refreshButton.disabled = !signedIn;
  elements.deployForm.querySelectorAll("input, textarea, select, button").forEach((field) => {
    field.disabled = !signedIn;
  });
  elements.deployMessage.textContent = signedIn ? "" : "Sign in to deploy and manage apps.";
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
  elements.modePill.textContent = ready.kubernetes_dry_run || ready.terraform_dry_run ? "dry-run" : ready.environment;
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
    localStorage.setItem("cloudforge_token", state.token);
    setSignedIn(true);
    elements.authMessage.textContent = "Signed in.";
    await loadApps();
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
elements.deployForm.addEventListener("submit", handleDeploy);
elements.templateSelect.addEventListener("change", (event) => applyTemplate(event.target.value));
elements.imageSelect.addEventListener("change", (event) => applyImage(event.target.value));
elements.refreshButton.addEventListener("click", loadApps);
elements.appsList.addEventListener("click", handleAppAction);
elements.logoutButton.addEventListener("click", () => {
  state.token = "";
  localStorage.removeItem("cloudforge_token");
  setSignedIn(false);
  renderApps([]);
});

setSignedIn(Boolean(state.token));
loadCatalog().catch(() => {});
loadReadiness().catch(() => {});
loadApps().catch((error) => {
  elements.appsList.innerHTML = `<p class="meta">${error.message}</p>`;
});
