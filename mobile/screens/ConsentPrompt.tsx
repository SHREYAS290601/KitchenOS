import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { ConsentChoice } from "../api/client";

const OPTIONS: { value: ConsentChoice; label: string; detail: string }[] = [
  { value: "session", label: "Yes, save for this shopping session", detail: "The photo may support later pantry enrichment during this shopping session." },
  { value: "always", label: "Always save grocery images", detail: "Future grocery photos can be retained for pantry memory." },
  { value: "answer_only", label: "Do not save after answering", detail: "Use this photo for the current answer, then delete it." },
];

export function ConsentPrompt({ onConfirm }: { onConfirm: (choice: ConsentChoice) => void }) {
  const [selected, setSelected] = useState<ConsentChoice | null>(null);
  return (
    <View style={styles.card} accessibilityRole="radiogroup">
      <Text accessibilityRole="header" style={styles.heading}>Save uploaded grocery images to improve pantry tracking?</Text>
      {OPTIONS.map((option) => (
        <Pressable
          key={option.value}
          accessibilityRole="radio"
          accessibilityLabel={option.label}
          accessibilityState={{ checked: selected === option.value }}
          onPress={() => setSelected(option.value)}
          style={[styles.option, selected === option.value && styles.selected]}
        >
          <Text style={styles.optionLabel}>{selected === option.value ? "Selected: " : ""}{option.label}</Text>
          <Text style={styles.detail}>{option.detail}</Text>
        </Pressable>
      ))}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Confirm image consent"
        accessibilityState={{ disabled: selected === null }}
        disabled={selected === null}
        onPress={() => selected && onConfirm(selected)}
        style={[styles.confirm, selected === null && styles.disabled]}
      ><Text style={styles.confirmText}>Continue</Text></Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: 12, padding: 16, borderWidth: 1, borderColor: "#94A3B8", borderRadius: 12, backgroundColor: "#F8FAFC" },
  heading: { fontSize: 19, fontWeight: "700", color: "#0F172A" },
  option: { padding: 12, borderWidth: 2, borderColor: "#CBD5E1", borderRadius: 10, gap: 4 },
  selected: { borderColor: "#0F766E", backgroundColor: "#CCFBF1" },
  optionLabel: { fontSize: 16, fontWeight: "600", color: "#0F172A" },
  detail: { color: "#334155" },
  confirm: { alignItems: "center", borderRadius: 8, backgroundColor: "#0F766E", padding: 12 },
  disabled: { opacity: 0.45 },
  confirmText: { color: "white", fontWeight: "700" },
});
