import { useEffect, useState } from "react";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getJobStatus,
  grantImageConsent,
  postCheckIn,
  uploadCheckInImage,
  type CheckInJob,
  type CheckInResult,
} from "../api/client";

type UploadResult = { ok: true; imageId: string } | { ok: false; message: string };
type ConsentResult = { ok: true; sessionId?: string | null } | { ok: false; message: string };

type Props = {
  consentSessionId?: string;
  shoppingListLabel?: string;
  pickPhotos?: () => Promise<string[]>;
  grantConsent?: (choice: "session", sessionId: string) => Promise<ConsentResult>;
  uploadPhoto?: (uri: string, sessionId: string) => Promise<UploadResult>;
  postCheckIn?: (imageIds: string[], sessionId: string) => Promise<CheckInResult>;
  getJobStatus?: (jobId: string) => Promise<CheckInResult>;
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_review"]);
type ScreenState =
  | "empty"
  | "ready"
  | "submitting"
  | "processing"
  | "completed"
  | "needs_review"
  | "failed";

function createCheckInSessionId(): string {
  return `check-in-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export async function pickGroceryPhotos(): Promise<string[]> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsMultipleSelection: true,
    selectionLimit: 20,
    quality: 1,
  });
  if (result.canceled) return [];
  const normalized: string[] = [];
  for (const asset of result.assets) {
    const context = ImageManipulator.manipulate(asset.uri);
    let rendered: Awaited<ReturnType<typeof context.renderAsync>> | undefined;
    try {
      if (asset.width > 4096 || asset.height > 4096) {
        const scale = Math.min(4096 / asset.width, 4096 / asset.height);
        context.resize({
          width: Math.round(asset.width * scale),
          height: Math.round(asset.height * scale),
        });
      }
      rendered = await context.renderAsync();
      const saved = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.9 });
      normalized.push(saved.uri);
    } finally {
      rendered?.release();
      context.release();
    }
  }
  return normalized;
}

export function CheckInScreen({
  consentSessionId,
  shoppingListLabel,
  pickPhotos = pickGroceryPhotos,
  grantConsent = grantImageConsent,
  uploadPhoto = uploadCheckInImage,
  postCheckIn: createCheckIn = postCheckIn,
  getJobStatus: fetchJobStatus = getJobStatus,
}: Props) {
  const [photos, setPhotos] = useState<string[]>([]);
  const [job, setJob] = useState<CheckInJob | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [focusedControl, setFocusedControl] = useState<string | null>(null);
  const [generatedSessionId] = useState(createCheckInSessionId);
  const fallbackSessionId = consentSessionId ?? generatedSessionId;
  const selectionLocked = submitting || jobId !== null;
  const screenState: ScreenState = submitting
    ? "submitting"
    : job?.status === "completed"
      ? "completed"
      : job?.status === "needs_review"
        ? "needs_review"
        : job?.status === "failed"
          ? "failed"
          : jobId !== null
            ? "processing"
            : photos.length > 0
              ? "ready"
              : "empty";
  const successfulTerminal = screenState === "completed" || screenState === "needs_review";
  const consentWasRevoked = screenState === "failed" && job?.error === "consent_revoked";

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async (delayMs: number) => {
      let result: CheckInResult;
      try {
        result = await fetchJobStatus(jobId);
      } catch {
        if (!active) return;
        setError("Check-in status is temporarily unavailable");
        timer = setTimeout(() => void poll(Math.min(delayMs * 2, 10000)), delayMs);
        return;
      }
      if (!active) return;
      if (!result.ok) {
        setError(result.message);
        timer = setTimeout(() => void poll(Math.min(delayMs * 2, 10000)), delayMs);
        return;
      }
      setError("");
      setJob(result.data);
      if (TERMINAL_STATUSES.has(result.data.status)) {
        if (result.data.status !== "failed") setPhotos([]);
        setAnnouncement("");
        setJobId(null);
        return;
      }
      timer = setTimeout(() => void poll(Math.min(delayMs * 2, 10000)), delayMs);
    };

    void poll(1000);
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [fetchJobStatus, jobId]);

  const addPhotos = async () => {
    setError("");
    try {
      const selected = await pickPhotos();
      setPhotos((current) => [...current, ...selected].slice(0, 20));
    } catch {
      setError("Grocery photos could not be selected");
    }
  };

  const submit = async () => {
    if (submitting || jobId) return;
    if (photos.length === 0) {
      setError("Grocery photos are required");
      return;
    }
    setSubmitting(true);
    setAnnouncement("");
    setError("");
    try {
      const consent = await grantConsent("session", fallbackSessionId);
      if (!consent.ok) {
        setError(consent.message);
        return;
      }
      const activeSessionId = consent.sessionId ?? fallbackSessionId;
      const uploads: UploadResult[] = [];
      for (const uri of photos) {
        const uploaded = await uploadPhoto(uri, activeSessionId);
        uploads.push(uploaded);
        if (!uploaded.ok) break;
      }
      const failedUpload = uploads.find((upload) => !upload.ok);
      if (failedUpload && !failedUpload.ok) {
        setError(failedUpload.message);
        return;
      }
      const imageIds = uploads.map((upload) => upload.ok ? upload.imageId : "");
      const created = await createCheckIn(imageIds, activeSessionId);
      if (!created.ok) {
        setError(created.message);
        return;
      }
      setJob(created.data);
      setAnnouncement("Processing in background — you can keep using the app");
      setJobId(created.data.jobId);
    } catch {
      setError("Check-in could not start. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setPhotos([]);
    setJob(null);
    setJobId(null);
    setError("");
    setAnnouncement("");
  };

  const primaryLabel = submitting
    ? "Starting…"
    : jobId
      ? "Processing…"
      : "Start check-in";
  const primaryAccessibilityLabel = submitting
    ? "Starting grocery check-in"
    : jobId
      ? "Grocery check-in processing"
      : "Start grocery check-in";
  const isTerminal = screenState === "completed"
    || screenState === "needs_review"
    || screenState === "failed";

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>Check in groceries</Text>
      <Text style={styles.intro}>
        Add post-shopping photos. Estimates stay editable.
      </Text>
      <View style={styles.sessionCard}>
        <Text style={styles.cardTitle}>
          {shoppingListLabel
            ? `${shoppingListLabel} · Shopping list context`
            : "New check-in · Session-only photo consent"}
        </Text>
        <Text style={styles.cardBody}>
          {shoppingListLabel
            ? "Photo consent stays separate and is confirmed when you start."
            : "A private check-in session is created when you start."}
        </Text>
      </View>
      {!successfulTerminal ? (
        <>
          <View style={styles.guidanceCard}>
            <Text style={styles.cardTitle}>For better results</Text>
            <Text style={styles.cardBody}>
              Spread products apart and include visible labels when possible.
            </Text>
          </View>
          <Text accessibilityRole="header" style={styles.sectionHeading}>
            {photos.length > 0 ? "Ready to start" : "No grocery photos yet"}
          </Text>
          <Pressable testID="add-photos" accessibilityRole="button" accessibilityLabel="Add grocery photos" accessibilityState={{ disabled: selectionLocked }} disabled={selectionLocked} onFocus={() => setFocusedControl("photos")} onBlur={() => setFocusedControl(null)} onPress={() => void addPhotos()} style={[styles.secondaryButton, focusedControl === "photos" && styles.focused]}>
            <Text>{photos.length > 0 ? "Add more grocery photos" : "Add grocery photos"}</Text>
          </Pressable>
          <Text>{photos.length} {photos.length === 1 ? "photo" : "photos"} selected</Text>
          <View style={styles.photoGrid}>
            {photos.map((uri, index) => (
              <View key={`${uri}-${index}`} style={styles.photoCard}>
                <Image source={{ uri }} accessibilityLabel={`Selected grocery photo ${index + 1}`} style={styles.photo} />
                <Pressable accessibilityRole="button" accessibilityLabel={`Remove selected grocery photo ${index + 1}`} accessibilityState={{ disabled: selectionLocked }} disabled={selectionLocked} onFocus={() => setFocusedControl(`remove-${index}`)} onBlur={() => setFocusedControl(null)} onPress={() => setPhotos((current) => current.filter((_, photoIndex) => photoIndex !== index))} style={[styles.removeButton, focusedControl === `remove-${index}` && styles.focused]}>
                  <Text>Remove</Text>
                </Pressable>
              </View>
            ))}
          </View>
        </>
      ) : null}
      <View style={styles.privacyCard}>
        <Text style={styles.cardTitle}>Photo privacy</Text>
        <Text style={styles.cardBody}>Photo use: This shopping session</Text>
        <Text style={styles.cardBody}>Retention: Delete photos after enrichment</Text>
        <Text style={styles.cardBody}>
          Confirmed pantry values will not be overwritten.
        </Text>
      </View>
      {!isTerminal ? (
        <Pressable testID="submit-check-in" accessibilityRole="button" accessibilityLabel={primaryAccessibilityLabel} accessibilityState={{ disabled: submitting || jobId !== null }} disabled={submitting || jobId !== null} onFocus={() => setFocusedControl("submit")} onBlur={() => setFocusedControl(null)} onPress={() => void submit()} style={[styles.primaryButton, focusedControl === "submit" && styles.focused]}>
          <Text style={styles.primaryText}>{primaryLabel}</Text>
        </Pressable>
      ) : null}
      {screenState === "failed" && !consentWasRevoked ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Retry grocery check-in" onFocus={() => setFocusedControl("retry")} onBlur={() => setFocusedControl(null)} onPress={() => void submit()} style={[styles.primaryButton, focusedControl === "retry" && styles.focused]}>
          <Text style={styles.primaryText}>Retry grocery check-in</Text>
        </Pressable>
      ) : null}
      {consentWasRevoked ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Allow selected photos for this check-in and retry" onFocus={() => setFocusedControl("renew-consent")} onBlur={() => setFocusedControl(null)} onPress={() => void submit()} style={[styles.primaryButton, focusedControl === "renew-consent" && styles.focused]}>
          <Text style={styles.primaryText}>Allow selected photos and retry</Text>
        </Pressable>
      ) : null}
      {screenState === "completed" || screenState === "needs_review" ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Start another check-in" onFocus={() => setFocusedControl("reset")} onBlur={() => setFocusedControl(null)} onPress={reset} style={[styles.secondaryButton, focusedControl === "reset" && styles.focused]}>
          <Text>Start another check-in</Text>
        </Pressable>
      ) : null}
      {submitting || error || announcement || job ? (
        <View testID="check-in-status" accessibilityLiveRegion="polite" style={styles.statusCard}>
          {submitting ? <Text>Starting grocery check-in</Text> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {announcement ? <Text>{announcement}</Text> : null}
          {job ? <Text>Overall status: {job.status.replaceAll("_", " ")}</Text> : null}
          {screenState === "completed" ? (
            <>
              <Text style={styles.statusTitle}>Check-in complete</Text>
              <Text>Photos are scheduled for deletion after enrichment.</Text>
            </>
          ) : null}
          {screenState === "needs_review" ? (
            <>
              <Text style={styles.statusTitle}>Check-in complete — estimates need review</Text>
              <Text>Review uncertain fields before confirming them.</Text>
            </>
          ) : null}
          {screenState === "failed" ? (
            <>
              <Text style={styles.statusTitle}>Check-in needs attention</Text>
              {consentWasRevoked ? (
                <>
                  <Text>Photo consent changed while processing.</Text>
                  <Text>Only continue if you want to allow these selected photos for this check-in.</Text>
                </>
              ) : (
                <>
                  <Text>
                    Processing stopped safely. Your confirmed pantry values were not changed.
                  </Text>
                  <Text>You can adjust the selected photos before retrying.</Text>
                </>
              )}
            </>
          ) : null}
          {job?.steps.map((step) => (
            <Text key={step.step}>{step.step.replaceAll("_", " ")}: {step.status.replaceAll("_", " ")}</Text>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 18, gap: 14, backgroundColor: "#F8FAFC", flexGrow: 1 },
  heading: { fontSize: 28, fontWeight: "800", color: "#0F172A" },
  intro: { fontSize: 16, color: "#475569" },
  sectionHeading: { fontSize: 18, fontWeight: "700", color: "#0F172A" },
  sessionCard: { padding: 14, gap: 4, borderRadius: 10, backgroundColor: "white", borderWidth: 1, borderColor: "#CBD5E1" },
  guidanceCard: { padding: 14, gap: 4, borderRadius: 10, backgroundColor: "#F0FDFA" },
  privacyCard: { padding: 14, gap: 5, borderRadius: 10, backgroundColor: "#ECFDF5" },
  cardTitle: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  cardBody: { fontSize: 14, lineHeight: 20, color: "#475569" },
  secondaryButton: { padding: 12, borderWidth: 2, borderColor: "#64748B", borderRadius: 8, alignItems: "center", backgroundColor: "white" },
  primaryButton: { padding: 14, borderRadius: 9, alignItems: "center", backgroundColor: "#0F766E" },
  primaryText: { color: "white", fontSize: 17, fontWeight: "700" },
  photoGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  photoCard: { gap: 4 },
  photo: { width: 96, height: 96, borderRadius: 10, backgroundColor: "#E2E8F0" },
  removeButton: { padding: 8, borderWidth: 1, borderColor: "#64748B", borderRadius: 6, alignItems: "center" },
  focused: { borderColor: "#0F172A", borderWidth: 3 },
  statusCard: { minHeight: 72, padding: 14, gap: 6, borderRadius: 10, backgroundColor: "#ECFDF5" },
  statusTitle: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  error: { color: "#B91C1C", fontWeight: "600" },
});
