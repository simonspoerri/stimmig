/// <reference types="astro/client" />

declare namespace App {
  interface Locals {
    session: import('./lib/session.ts').Session | undefined;
    pipeline: import('./lib/api.ts').PipelineClient;
  }
}
