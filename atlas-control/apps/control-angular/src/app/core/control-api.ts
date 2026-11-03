import { Injectable, inject, signal } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { firstValueFrom } from "rxjs";

/** Thin typed client over control-api ops endpoints (all require JWT). */
@Injectable({ providedIn: "root" })
export class ControlApi {
  private http = inject(HttpClient);
  pending = signal<unknown[] | null>(null);

  async list<T>(path: string): Promise<T> {
    return firstValueFrom(this.http.get<T>(path));
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.post<T>(path, body));
  }

  async get<T>(path: string): Promise<T> {
    return firstValueFrom(this.http.get<T>(path));
  }
}
