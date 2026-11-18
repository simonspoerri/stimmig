import type { components, paths } from './pipeline.ts';

export type { components, paths };

type Schemas = components['schemas'];

export type VoteSummary = Schemas['VoteSummary'];
export type VoteDetail = Schemas['VoteDetail'];
export type VoteCreate = Schemas['VoteCreate'];
export type DocumentOut = Schemas['DocumentOut'];
export type DocumentCreate = Schemas['DocumentCreate'];
export type ExtractionRunOut = Schemas['ExtractionRunOut'];
export type ClaimOut = Schemas['ClaimOut'];
export type ClaimReview = Schemas['ClaimReview'];
export type VisualizationOut = Schemas['VisualizationOut'];
export type VisualizationCreate = Schemas['VisualizationCreate'];
export type DataSource = Schemas['DataSource'];
export type Me = Schemas['Me'];
export type AuditEventOut = Schemas['AuditEventOut'];
export type PublicVote = Schemas['PublicVote'];
export type PublicVoteSummary = Schemas['PublicVoteSummary'];
export type PublicFact = Schemas['PublicFact'];
export type PublicForecast = Schemas['PublicForecast'];

export type Side = Schemas['Side'];
export type ClaimClass = Schemas['ClaimClass'];
