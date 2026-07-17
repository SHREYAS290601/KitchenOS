import { File, UploadType } from "expo-file-system";
import * as SecureStore from "expo-secure-store";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
const API_TOKEN_KEY = "pantryops.api-token";

export async function saveApiToken(token: string): Promise<void> {
  const normalized = token.trim();
  if (normalized.length < 32) {
    throw new Error("API token must be at least 32 characters");
  }
  await SecureStore.setItemAsync(API_TOKEN_KEY, normalized);
}

async function authorizedHeaders(extra: Record<string, string> = {}): Promise<Record<string, string>> {
  const token = await SecureStore.getItemAsync(API_TOKEN_KEY);
  return token
    ? { ...extra, Authorization: `Bearer ${token}` }
    : { ...extra };
}

export type Health = { status: string; service: string };

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: "unreachable" | "unhealthy" };

export type SourcedFieldPayload = {
  value: string | number | null;
  source: string;
  confidence: number;
  status: string;
};

export type PantryItemPayload = {
  pantry_item_id: string;
  user_id: string;
  canonical_name: SourcedFieldPayload | null;
  display_name: SourcedFieldPayload | null;
  category: SourcedFieldPayload | null;
  brand: SourcedFieldPayload | null;
  product_name: SourcedFieldPayload | null;
  quantity_value: SourcedFieldPayload | null;
  quantity_type: string;
  unit_label: string | null;
  purchase_date: string | null;
  storage_location: string | null;
  estimated_use_by: string | null;
  status: string;
  needs_user_review: boolean;
};

export type FieldActionName = "confirm" | "edit" | "reject" | "leave_as_estimate";

export type FieldActionResult =
  | { ok: true; outcome: string; field: SourcedFieldPayload | null }
  | { ok: false; message: string };

export async function getPantryItem(
  itemId: string,
): Promise<ApiResult<PantryItemPayload>> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/pantry/items/${itemId}`, {
      headers: await authorizedHeaders(),
    });
  } catch {
    return { ok: false, error: "unreachable" };
  }
  if (!response.ok) {
    return { ok: false, error: "unhealthy" };
  }
  const data = (await response.json()) as PantryItemPayload;
  return { ok: true, data };
}

export type ConfirmResult =
  | { ok: true; pantryItemId: string | null; alreadyConfirmed?: boolean }
  | { ok: false; message: string };

export async function confirmShoppingItem(
  listId: string,
  itemId: string,
): Promise<ConfirmResult> {
  let response: Response;
  try {
    response = await fetch(
      `${BASE_URL}/shopping-lists/${listId}/items/${itemId}/confirm`,
      {
        method: "POST",
        headers: await authorizedHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status: "bought" }),
      },
    );
  } catch {
    return { ok: false, message: "Could not reach the server to cross off this item" };
  }
  if (response.status === 409) {
    return { ok: true, pantryItemId: null, alreadyConfirmed: true };
  }
  const body = (await response.json()) as {
    pantry_item_id?: string;
    detail?: string;
  };
  if (!response.ok) {
    return { ok: false, message: body.detail ?? "Cross-off failed" };
  }
  return { ok: true, pantryItemId: body.pantry_item_id ?? null };
}

export async function postFieldAction(
  itemId: string,
  fieldName: string,
  action: FieldActionName,
  value?: string | number | null,
): Promise<FieldActionResult> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/pantry/items/${itemId}/fields/${fieldName}`, {
      method: "POST",
      headers: await authorizedHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(action === "edit" ? { action, value } : { action }),
    });
  } catch {
    return { ok: false, message: `Could not reach the server to update ${fieldName}` };
  }
  const body = (await response.json()) as {
    outcome?: string;
    field?: SourcedFieldPayload | null;
    detail?: string;
  };
  if (!response.ok) {
    return { ok: false, message: body.detail ?? `Updating ${fieldName} failed` };
  }
  return { ok: true, outcome: body.outcome ?? "applied", field: body.field ?? null };
}

export async function getHealth(): Promise<ApiResult<Health>> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/healthz`);
  } catch {
    return { ok: false, error: "unreachable" };
  }
  if (!response.ok) {
    return { ok: false, error: "unhealthy" };
  }
  const data = (await response.json()) as Health;
  return { ok: true, data };
}

export type ConsentChoice = "session" | "always" | "answer_only";

const CONSENT_PAYLOADS = {
  session: { state: "granted_for_session", retention_policy: "delete_after_enrichment" },
  always: { state: "always_granted", retention_policy: "keep_for_pantry_memory" },
  answer_only: { state: "granted_for_single_image", retention_policy: "delete_after_answer" },
} as const;

export async function grantImageConsent(
  choice: ConsentChoice,
  _shoppingSessionId?: string,
): Promise<{ ok: true; sessionId: string | null } | { ok: false; message: string }> {
  try {
    const response = await fetch(`${BASE_URL}/consent`, {
      method: "POST",
      headers: await authorizedHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        ...CONSENT_PAYLOADS[choice],
      }),
    });
    const body = (await response.json()) as {
      shopping_session_id?: string | null;
      detail?: string;
    };
    if (!response.ok) {
      return { ok: false, message: body.detail ?? "Could not save image consent" };
    }
    if (choice === "session" && !body.shopping_session_id) {
      return { ok: false, message: "The server did not create a shopping session" };
    }
    return { ok: true, sessionId: body.shopping_session_id ?? null };
  } catch {
    return { ok: false, message: "Could not reach the server to save image consent" };
  }
}

export async function uploadAssistImage(
  photoUri: string,
  shoppingSessionId: string,
  choice: ConsentChoice,
): Promise<{ ok: true; imageId: string } | { ok: false; message: string }> {
  try {
    const photo = new File(photoUri);
    if (!photo.exists) {
      return { ok: false, message: "The captured photo is no longer available. Please take it again." };
    }

    const response = await photo.upload(`${BASE_URL}/images`, {
      httpMethod: "POST",
      uploadType: UploadType.MULTIPART,
      fieldName: "image",
      mimeType: photo.type || "image/jpeg",
      parameters: {
        capture_context: "while_shopping_query",
        shopping_session_id: shoppingSessionId,
        retention_policy: CONSENT_PAYLOADS[choice].retention_policy,
      },
      headers: await authorizedHeaders(),
      sessionType: "foreground",
    });
    const body = JSON.parse(response.body) as { image_id?: string; detail?: string };
    if (response.status < 200 || response.status >= 300 || !body.image_id) {
      return { ok: false, message: body.detail ?? "Could not upload the image" };
    }
    return { ok: true, imageId: body.image_id };
  } catch (error) {
    console.warn("Image upload failed", error);
    return { ok: false, message: "Could not reach the server to upload the image" };
  }
}

export type AssistPayload = {
  answer: string;
  applied_preference_ids: string[];
  audit: { verdict: "pass" | "block" | "needs_review"; reasons: string[] };
  degraded: boolean;
};

export async function askShoppingAssistant(
  question: string,
  imageId?: string,
  shoppingSessionId?: string,
): Promise<{ ok: true; data: AssistPayload } | { ok: false; message: string }> {
  try {
    const response = await fetch(`${BASE_URL}/shopping/assist`, {
      method: "POST",
      headers: await authorizedHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ question, image_id: imageId, shopping_session_id: shoppingSessionId }),
    });
    const body = (await response.json()) as AssistPayload & { detail?: string };
    if (!response.ok) {
      return { ok: false, message: body.detail ?? "The shopping assistant could not answer" };
    }
    return { ok: true, data: body };
  } catch {
    return { ok: false, message: "Could not reach the shopping assistant" };
  }
}

export type CheckInStep = { step: string; status: string };
export type CheckInJob = {
  jobId: string;
  status: "queued" | "processing" | "completed" | "failed" | "needs_review";
  steps: CheckInStep[];
  error?: "consent_revoked" | "processing_failed" | null;
};
export type CheckInResult =
  | { ok: true; data: CheckInJob }
  | { ok: false; message: string };

function mapCheckInJob(body: {
  job_id: string;
  status: CheckInJob["status"];
  steps: CheckInStep[];
  error?: CheckInJob["error"];
}): CheckInJob {
  return {
    jobId: body.job_id,
    status: body.status,
    steps: [...body.steps],
    error: body.error ?? null,
  };
}

const CHECK_IN_STATUSES = new Set(["queued", "processing", "completed", "failed", "needs_review"]);

function isCheckInBody(body: {
  job_id?: unknown;
  status?: unknown;
  steps?: unknown;
  error?: unknown;
}): body is {
  job_id: string;
  status: CheckInJob["status"];
  steps: CheckInStep[];
  error?: CheckInJob["error"];
} {
  return typeof body.job_id === "string"
    && typeof body.status === "string"
    && CHECK_IN_STATUSES.has(body.status)
    && Array.isArray(body.steps)
    && body.steps.every((step) => (
      typeof step === "object"
      && step !== null
      && typeof (step as CheckInStep).step === "string"
      && typeof (step as CheckInStep).status === "string"
    ));
}

export async function uploadCheckInImage(
  photoUri: string,
  shoppingSessionId: string,
): Promise<{ ok: true; imageId: string } | { ok: false; message: string }> {
  try {
    const photo = new File(photoUri);
    if (!photo.exists) {
      return { ok: false, message: "A selected grocery photo is no longer available" };
    }
    const response = await photo.upload(`${BASE_URL}/images`, {
      httpMethod: "POST",
      uploadType: UploadType.MULTIPART,
      fieldName: "image",
      mimeType: photo.type || "image/jpeg",
      parameters: {
        capture_context: "post_shopping_check_in",
        shopping_session_id: shoppingSessionId,
        retention_policy: "delete_after_enrichment",
      },
      headers: await authorizedHeaders(),
      sessionType: "foreground",
    });
    const body = JSON.parse(response.body) as { image_id?: string; detail?: string };
    if (response.status < 200 || response.status >= 300 || !body.image_id) {
      return { ok: false, message: body.detail ?? "Could not upload a grocery photo" };
    }
    return { ok: true, imageId: body.image_id };
  } catch {
    return { ok: false, message: "Could not reach the server to upload grocery photos" };
  }
}

export async function postCheckIn(
  imageIds: string[],
  shoppingSessionId: string,
): Promise<CheckInResult> {
  try {
    const response = await fetch(`${BASE_URL}/check-in/groceries`, {
      method: "POST",
      headers: await authorizedHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        shopping_session_id: shoppingSessionId,
        image_ids: [...imageIds],
        processing_mode: "silent_background_enrichment",
      }),
    });
    const body = (await response.json()) as {
      job_id?: string;
      status?: CheckInJob["status"];
      steps?: CheckInStep[];
      detail?: string;
      error?: CheckInJob["error"];
    };
    if (!response.ok || !isCheckInBody(body)) {
      return { ok: false, message: body.detail ?? "Could not start grocery check-in" };
    }
    return {
      ok: true,
      data: mapCheckInJob({
        job_id: body.job_id,
        status: body.status,
        steps: body.steps,
        error: body.error,
      }),
    };
  } catch {
    return { ok: false, message: "Could not reach the server to start grocery check-in" };
  }
}

export async function getJobStatus(jobId: string): Promise<CheckInResult> {
  try {
    const response = await fetch(`${BASE_URL}/jobs/${jobId}`, {
      headers: await authorizedHeaders(),
    });
    const body = (await response.json()) as {
      job_id?: string;
      status?: CheckInJob["status"];
      steps?: CheckInStep[];
      detail?: string;
      error?: CheckInJob["error"];
    };
    if (!response.ok || !isCheckInBody(body)) {
      return { ok: false, message: body.detail ?? "Could not refresh check-in status" };
    }
    return {
      ok: true,
      data: mapCheckInJob({
        job_id: body.job_id,
        status: body.status,
        steps: body.steps,
        error: body.error,
      }),
    };
  } catch {
    return { ok: false, message: "Could not reach the server for check-in status" };
  }
}
