import { HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { from, switchMap } from "rxjs";
import { AuthService } from "./auth";

const API_BASE = "http://localhost:8102";

/** Bearer auth + control-api base URL rewrite (paths start with /ops). */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  return from(auth.token()).pipe(
    switchMap((token) => {
      const url = req.url.startsWith("/") ? `${API_BASE}${req.url}` : req.url;
      const authed = token
        ? req.clone({ url, setHeaders: { Authorization: `Bearer ${token}` } })
        : req.clone({ url });
      return next(authed);
    }),
  );
};
