import { Injectable } from "@angular/core";
import { UserManager, User, WebStorageStateStore } from "oidc-client-ts";

/**
 * OIDC Auth Code + PKCE against the realm `atlas`, client `atlas-control`
 * (public browser client). Same realm the storefront uses; operator
 * roles/ABAC still live server-side in control-api.
 */
const AUTHORITY = "http://localhost:8180/realms/atlas";
const CLIENT_ID = "atlas-control";
const REDIRECT_URI = "http://localhost:4200/callback";
const POST_LOGOUT = "http://localhost:4200";

@Injectable({ providedIn: "root" })
export class AuthService {
  private manager = new UserManager({
    authority: AUTHORITY,
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    post_logout_redirect_uri: POST_LOGOUT,
    scope: "openid profile",
    response_type: "code",
    userStore: new WebStorageStateStore({ store: sessionStorage }),
  });

  async user(): Promise<User | null> {
    return this.manager.getUser();
  }

  async username(): Promise<string> {
    const user = await this.user();
    return user?.profile.preferred_username ?? "";
  }

  async signIn(): Promise<void> {
    await this.manager.signinRedirect();
  }

  async finishSignIn(): Promise<User> {
    return this.manager.signinCallback() as Promise<User>;
  }

  async token(): Promise<string | null> {
    const user = await this.manager.getUser();
    return user?.access_token ?? null;
  }

  async signOut(): Promise<void> {
    await this.manager.signoutRedirect();
  }
}
