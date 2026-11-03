import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth';

@Component({ selector: 'app-callback', template: '<p>entrando…</p>' })
export class CallbackComponent implements OnInit {
  constructor(private auth: AuthService, private router: Router) {}
  async ngOnInit(): Promise<void> {
    await this.auth.finishSignIn();
    void this.router.navigate(['/']);
  }
}
