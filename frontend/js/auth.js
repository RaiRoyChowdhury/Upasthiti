/**
 * Login page controller.
 */

document.addEventListener("DOMContentLoaded", () => {
  // If already logged in, skip straight to the dashboard.
  if (Api.isAuthenticated()) {
    window.location.href = "dashboard.html";
    return;
  }

  const form = document.getElementById("login-form");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const submitBtn = document.getElementById("login-submit");
  const errorAlert = document.getElementById("login-error");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError();

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
      showError("Please enter both email and password.");
      return;
    }

    setLoading(true);
    try {
      const data = await Api.post("/api/auth/login", { email, password }, { auth: false });
      Api.setSession(data.access_token, data.user);
      window.location.href = "dashboard.html";
    } catch (err) {
      showError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  });

  function showError(message) {
    errorAlert.textContent = message;
    errorAlert.classList.remove("hidden");
  }

  function hideError() {
    errorAlert.classList.add("hidden");
    errorAlert.textContent = "";
  }

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    submitBtn.innerHTML = isLoading
      ? '<span class="spinner"></span> Signing in...'
      : "Sign In";
  }
});

function logout() {
  Api.clearSession();
  window.location.href = "login.html";
}
