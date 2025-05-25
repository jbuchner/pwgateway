import { HttpClient } from '@angular/common/http';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.less',
  imports: [NgbModule],
})
export class AppComponent implements OnInit {

  title = 'dashboard';
  private httpClient = inject(HttpClient);
  private destroyRef = inject(DestroyRef);

  soc = signal<number>(0);
  batteryPower = signal<number>(0);
  gridPower = signal<number>(0);
  inverterPower = signal<number>(0);

  ngOnInit() {
    this.loadData();
    const iv = setInterval(() => {
     this.loadData();
    }, 10000);
    this.destroyRef.onDestroy(() => {
      clearInterval(iv);
    });
  }

  loadData() {
    const { protocol, hostname, port } = window.location;
    const baseUrl = `${protocol}//${hostname}${port ? `:${port}` : ''}`;

    this.httpClient
      .get<{ raw_soc: number; adjusted_soc: number }>(
      `${baseUrl}/soc`
      )
      .subscribe((data) => {
      this.soc.set(data.adjusted_soc);
      });
      this.httpClient
        .get<{ battery: number; load: number; site: number; solar: number }>(
          `${baseUrl}/aggregates`
        )
        .subscribe((data) => {
          this.batteryPower.set(data.battery);
          this.gridPower.set(data.site);
          this.inverterPower.set(data.solar);
        });
      }
}
