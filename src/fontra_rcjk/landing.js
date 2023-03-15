import { loaderSpinner } from "/core/loader-spinner.js";
import { getRemoteProxy } from "/core/remote.js";
import { parseCookies, themeSwitchFromLocalStorage } from "/core/utils.js";
import { startupLandingPage } from "/filesystem/landing.js";

export function startupRCJKLandingPage() {
  startupLandingPage(rcjkAuthenticateFunc);
}

function rcjkAuthenticateFunc() {
  const cookies = parseCookies(document.cookie);

  const loginFormContainer = document.querySelector("#login-form-container");
  const logoutForm = document.querySelector("#logout-form-container");
  const logoutButton = document.querySelector("#logout-button");
  const loginFailureMessage = document.querySelector("#login-failure-message");

  const username = decodeURI(cookies["fontra-username"], "UTF-8");
  const haveToken = !!cookies["fontra-authorization-token"];
  const loginFailed = cookies["fontra-authorization-failed"] == "true";

  if (username) {
    const usernameField = document.querySelector("#login-username");
    usernameField.value = username;
  }
  loginFormContainer.classList.toggle("hidden", haveToken);
  logoutForm.classList.toggle("hidden", !haveToken);
  if (haveToken && username) {
    logoutButton.textContent = `Log out ${username}`;
  } else {
    const loginForm = document.querySelector("#login-form");
    const url = new URL(window.location);
    loginForm.action = "/login" + url.search;
  }
  loginFailureMessage.classList.toggle("hidden", !loginFailed);
  return haveToken;
}
