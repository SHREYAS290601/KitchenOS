import { useEffect, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { askShoppingAssistant, grantImageConsent, uploadAssistImage, type AssistPayload, type ConsentChoice } from "../api/client";
import { ConsentPrompt } from "./ConsentPrompt";
import { loadCachedConsent, saveCachedConsent, type CachedConsent } from "../storage/consentCache";

type AskResult = { ok: true; data: AssistPayload } | { ok: false; message: string };
type Props = {
  ask?: (question: string, imageId?: string) => Promise<AskResult>;
  onOpenCamera: () => void;
  photoUri?: string | null;
  onRemovePhoto?: () => void;
  shoppingSessionId?: string;
};

export function AssistScreen({ ask = askShoppingAssistant, onOpenCamera, photoUri, onRemovePhoto, shoppingSessionId = "mobile-session" }: Props) {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<"idle" | "consent" | "pending" | "answered" | "error">("idle");
  const [answer, setAnswer] = useState("");
  const [uploadedPhoto, setUploadedPhoto] = useState<{ uri: string; imageId: string } | null>(null);
  const [cachedConsent, setCachedConsent] = useState<CachedConsent | null>(null);

  useEffect(() => {
    let active = true;
    loadCachedConsent().then((value) => {
      if (active) setCachedConsent(value);
    });
    return () => { active = false; };
  }, []);

  const finishAsk = async (imageId?: string) => {
    setStatus("pending");
    const result = await ask(question.trim(), imageId);
    if (result.ok) {
      setAnswer(result.data.answer);
      setStatus("answered");
    } else {
      setAnswer(result.message);
      setStatus("error");
    }
  };

  const uploadAndAsk = async (choice: ConsentChoice) => {
    setStatus("pending");
    const uploaded = await uploadAssistImage(photoUri!, shoppingSessionId, choice);
    if (!uploaded.ok) {
      setAnswer(uploaded.message);
      setStatus("error");
      return;
    }
    setUploadedPhoto({ uri: photoUri!, imageId: uploaded.imageId });
    await finishAsk(uploaded.imageId);
  };

  const submit = () => {
    if (!question.trim()) return;
    if (photoUri && uploadedPhoto?.uri !== photoUri) {
      const reusableChoice = cachedConsent?.choice;
      const canReuse = reusableChoice === "always" ||
        (reusableChoice === "session" && cachedConsent?.shoppingSessionId === shoppingSessionId);
      if (canReuse) void uploadAndAsk(reusableChoice);
      else setStatus("consent");
      return;
    }
    void finishAsk(uploadedPhoto?.imageId);
  };

  const confirmConsent = async (choice: ConsentChoice) => {
    setStatus("pending");
    const consent = await grantImageConsent(choice, shoppingSessionId);
    if (!consent.ok) {
      setAnswer(consent.message);
      setStatus("error");
      return;
    }
    await saveCachedConsent(choice, shoppingSessionId);
    setCachedConsent(choice === "answer_only" ? null : {
      choice,
      shoppingSessionId: choice === "session" ? shoppingSessionId : null,
    });
    await uploadAndAsk(choice);
  };

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Text accessibilityRole="header" style={styles.heading}>Ask while shopping</Text>
      <Text style={styles.intro}>Get evidence-aware guidance without changing your pantry.</Text>
      <TextInput accessibilityLabel="Shopping question" value={question} onChangeText={setQuestion} placeholder="Should I buy this yogurt?" multiline style={styles.input} />
      {photoUri ? (
        <View style={styles.photoCard}>
          <Image source={{ uri: photoUri }} accessibilityLabel="Attached grocery product photo" style={styles.photo} />
          <Pressable accessibilityRole="button" accessibilityLabel="Remove attached photo" onPress={onRemovePhoto} style={styles.secondaryButton}><Text>Remove photo</Text></Pressable>
        </View>
      ) : (
        <Pressable accessibilityRole="button" accessibilityLabel="Attach grocery product photo" onPress={onOpenCamera} style={styles.secondaryButton}><Text>Attach a product photo</Text></Pressable>
      )}
      <Pressable accessibilityRole="button" accessibilityLabel="Ask shopping assistant" accessibilityState={{ disabled: !question.trim() || status === "pending" }} disabled={!question.trim() || status === "pending"} onPress={submit} style={styles.primaryButton}>
        <Text style={styles.primaryText}>Ask</Text>
      </Pressable>
      {status === "consent" && <ConsentPrompt onConfirm={(choice) => void confirmConsent(choice)} />}
      <View testID="assist-answer" accessibilityLiveRegion="polite" style={styles.answerCard}>
        {status === "pending" && <Text>Answer pending</Text>}
        {(status === "answered" || status === "error") && <Text>{answer}</Text>}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 18, gap: 14, backgroundColor: "#F8FAFC", flexGrow: 1 },
  heading: { fontSize: 28, fontWeight: "800", color: "#0F172A" },
  intro: { fontSize: 16, color: "#475569" },
  input: { minHeight: 112, padding: 14, borderWidth: 2, borderColor: "#94A3B8", backgroundColor: "white", borderRadius: 12, fontSize: 17, textAlignVertical: "top" },
  photoCard: { gap: 8 },
  photo: { height: 180, borderRadius: 12, backgroundColor: "#E2E8F0" },
  secondaryButton: { padding: 12, borderWidth: 1, borderColor: "#64748B", borderRadius: 8, alignItems: "center", backgroundColor: "white" },
  primaryButton: { padding: 14, borderRadius: 9, alignItems: "center", backgroundColor: "#0F766E" },
  primaryText: { color: "white", fontSize: 17, fontWeight: "700" },
  answerCard: { minHeight: 64, padding: 14, borderRadius: 10, backgroundColor: "#ECFDF5" },
});
