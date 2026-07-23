import type { components } from "../api/schema";

type GeneratedGlobalSearchGroup = components["schemas"]["GlobalSearchGroup"];
type GeneratedGlobalSearchResponse = components["schemas"]["GlobalSearchResponse"];
type GeneratedGlobalSearchError = components["schemas"]["ErrorEnvelope"];

export type GlobalSearchGroupType = components["schemas"]["GlobalSearchGroupTypeEnum"];
export type GlobalSearchItemType = components["schemas"]["GlobalSearchItemTypeEnum"];
export type GlobalSearchItem = Readonly<components["schemas"]["GlobalSearchItem"]>;

export type GlobalSearchGroup = Readonly<Omit<GeneratedGlobalSearchGroup, "items">> & {
  readonly items: readonly GlobalSearchItem[];
};

export type GlobalSearchResponse = Readonly<Omit<GeneratedGlobalSearchResponse, "groups">> & {
  readonly groups: readonly GlobalSearchGroup[];
};

export type GlobalSearchError = Readonly<Omit<GeneratedGlobalSearchError, "fields">> & {
  readonly fields: Readonly<Record<string, readonly string[]>>;
};

export type GlobalSearchApiResult =
  | { readonly ok: true; readonly data: GlobalSearchResponse }
  | { readonly ok: false; readonly error: GlobalSearchError; readonly status: number };
