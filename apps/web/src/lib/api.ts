import type { PublicVote, PublicVoteSummary } from '@stimmig/api-types';

const BASE = process.env.PIPELINE_PUBLIC_URL ?? 'http://localhost:8000';

export class NotFound extends Error {}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(new URL(path, BASE), { headers: { accept: 'application/json' } });
  if (response.status === 404) throw new NotFound(path);
  if (!response.ok) throw new Error(`pipeline ${response.status} for ${path}`);
  return (await response.json()) as T;
}

export const listVotes = () => get<PublicVoteSummary[]>('/public/v1/votes');
export const getVote = (id: string) => get<PublicVote>(`/public/v1/votes/${encodeURIComponent(id)}`);
