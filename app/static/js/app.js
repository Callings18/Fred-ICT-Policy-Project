document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const message = form.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
    return;
  }
  const status = form.querySelector("[data-employment-status]");
  if (status instanceof HTMLSelectElement && (status.value === "LEFT" || status.value === "TRANSFERRED")) {
    const original = form.getAttribute("data-original-status") || "";
    if (original !== status.value) {
      const agreed = window.confirm("This status change will open an access review if one is not already pending.");
      if (!agreed) event.preventDefault();
    }
  }
});

const toggle = document.querySelector("[data-nav-toggle]");
const sidebar = document.querySelector(".sidebar");
if (toggle instanceof HTMLButtonElement && sidebar) {
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
}

const condition = document.querySelector("[data-condition]");
const conditionHint = document.querySelector("[data-condition-hint]");
const conditionValue = document.querySelector("[data-condition-value]");
if (condition instanceof HTMLSelectElement) {
  const automatic = new Set(["WEEKEND", "EMPLOYEE_NOT_ACTIVE"]);
  const syncCondition = () => {
    const option = condition.selectedOptions[0];
    if (conditionHint) conditionHint.textContent = option ? option.dataset.hint || "" : "";
    if (conditionValue instanceof HTMLInputElement) {
      const lock = automatic.has(condition.value);
      conditionValue.readOnly = lock;
      if (condition.value === "WEEKEND") conditionValue.value = "SAT,SUN";
      if (condition.value === "EMPLOYEE_NOT_ACTIVE") conditionValue.value = "NOT_ACTIVE";
    }
  };
  condition.addEventListener("change", syncCondition);
  syncCondition();
}

const reportType = document.querySelector("[data-report-type]");
if (reportType instanceof HTMLSelectElement) {
  const alertFilters = document.querySelectorAll("[data-alert-filter]");
  const syncReport = () => {
    const show = reportType.value === "alerts";
    alertFilters.forEach((node) => {
      node.hidden = !show;
    });
  };
  reportType.addEventListener("change", syncReport);
  syncReport();
}

document.querySelectorAll("[data-print]").forEach((button) => {
  button.addEventListener("click", () => window.print());
});
