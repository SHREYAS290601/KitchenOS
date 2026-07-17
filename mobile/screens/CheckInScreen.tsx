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
  shoppingSessionId?: string;
  pickPhotos?: () => Promise<string[]>;
  grantConsent?: (choice: "session", sessionId: string) => Promise<ConsentResult>;
  uploadPhoto?: (uri: string, sessionId: string) => Promise<UploadResult>;
  postCheckIn?: (imageIds: string[], sessionId: string) => Promise<CheckInResult>;
  getJobStatus?: (jobId: string) => Promise<CheckInResult>;
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_review"]);

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
  shoppingSessionId,
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
  const fallbackSessionId = shoppingSessionId ?? generatedSessionId;
  const selectionLocked = submitting || jobId !== null;

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async (delayMs: number) => {
      const result = await fetchJobStatus(jobId);
      if (!active) return;
      if (!result.ok) {
        setError(result.message);
        timer = setTimeout(() => void poll(Math.min(delayMs * 2, 10000)), delayMs);
        return;
      }
      setError("");
      setJob(result.data);
      if (TERMINAL_STATUSES.has(result.data.status)) {
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
    setError("");
    const consent = await grantConsent("session", fallbackSessionId);
    if (!consent.ok) {
      setError(consent.message);
      setSubmitting(false);
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
      setSubmitting(false);
      return;
    }
    const imageIds = uploads.map((upload) => upload.ok ? upload.imageId : "");
    const created = await createCheckIn(imageIds, activeSessionId);
    if (!created.ok) {
      setError(created.message);
      setSubmitting(false);
      return;
    }
    setJob(created.data);
    setAnnouncement("Processing in background — you can keep using the app");
    setJobId(created.data.jobId);
    setPhotos([]);
    setSubmitting(false);
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>Check in groceries</Text>
      <Text style={styles.intro}>
        Choose post-shopping photos to process with session-only consent. Estimates stay editable.
      </Text>
      <Pressable testID="add-photos" accessibilityRole="button" accessibilityLabel="Add grocery photos" accessibilityState={{ disabled: selectionLocked }} disabled={selectionLocked} onFocus={() => setFocusedControl("photos")} onBlur={() => setFocusedControl(null)} onPress={() => void addPhotos()} style={[styles.secondaryButton, focusedControl === "photos" && styles.focused]}>
        <Text>Add grocery photos</Text>
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
      <Pressable testID="submit-check-in" accessibilityRole="button" accessibilityLabel="Start grocery check-in" accessibilityState={{ disabled: submitting || jobId !== null }} disabled={submitting || jobId !== null} onFocus={() => setFocusedControl("submit")} onBlur={() => setFocusedControl(null)} onPress={() => void submit()} style={[styles.primaryButton, focusedControl === "submit" && styles.focused]}>
        <Text style={styles.primaryText}>{submitting ? "Starting…" : "Start check-in"}</Text>
      </Pressable>
      <View testID="check-in-status" accessibilityLiveRegion="polite" style={styles.statusCard}>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {announcement ? <Text>{announcement}</Text> : null}
        {job ? <Text>Overall status: {job.status.replaceAll("_", " ")}</Text> : null}
        {job?.status === "failed" ? <Text>Processing stopped. Please start a new check-in.</Text> : null}
        {job?.steps.map((step) => (
          <Text key={step.step}>{step.step.replaceAll("_", " ")}: {step.status.replaceAll("_", " ")}</Text>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 18, gap: 14, backgroundColor: "#F8FAFC", flexGrow: 1 },
  heading: { fontSize: 28, fontWeight: "800", color: "#0F172A" },
  intro: { fontSize: 16, color: "#475569" },
  secondaryButton: { padding: 12, borderWidth: 2, borderColor: "#64748B", borderRadius: 8, alignItems: "center", backgroundColor: "white" },
  primaryButton: { padding: 14, borderRadius: 9, alignItems: "center", backgroundColor: "#0F766E" },
  primaryText: { color: "white", fontSize: 17, fontWeight: "700" },
  photoGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  photoCard: { gap: 4 },
  photo: { width: 96, height: 96, borderRadius: 10, backgroundColor: "#E2E8F0" },
  removeButton: { padding: 8, borderWidth: 1, borderColor: "#64748B", borderRadius: 6, alignItems: "center" },
  focused: { borderColor: "#0F172A", borderWidth: 3 },
  statusCard: { minHeight: 72, padding: 14, gap: 6, borderRadius: 10, backgroundColor: "#ECFDF5" },
  error: { color: "#B91C1C", fontWeight: "600" },
});
