import { Pressable, StyleSheet, Text, View } from "react-native";

export type FieldStatus =
  | "estimated"
  | "user_confirmed"
  | "user_edited"
  | "rejected"
  | "unknown"
  | "conflicting";

export type SourcedFieldValue = {
  value: string | number | null;
  source: string;
  confidence: number;
  status: FieldStatus;
};

export type FieldActionName = "confirm" | "edit" | "reject" | "leave_as_estimate";

const SOURCE_LABELS: Record<string, string> = {
  user_edited: "User edit",
  user_confirmed: "User confirmation",
  checklist_cross_off: "Checklist cross-off",
  barcode: "Barcode",
  receipt_ocr: "Receipt OCR",
  label_ocr: "Label OCR",
  product_detection: "Product detection",
  segmentation: "Segmentation",
  silent_check_in: "Silent check-in",
  api_enrichment: "API enrichment",
  web_enrichment: "Web enrichment",
  llm_inference: "LLM inference",
  none: "No source",
};

const STATUS_LABELS: Record<FieldStatus, string> = {
  estimated: "Estimated",
  user_confirmed: "Confirmed by you",
  user_edited: "Edited by you",
  rejected: "Rejected",
  unknown: "Unknown",
  conflicting: "Needs review: conflicting evidence",
};

function fieldTitle(fieldName: string): string {
  const words = fieldName.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

type Props = {
  fieldName: string;
  field: SourcedFieldValue;
  onAction: (action: FieldActionName) => void;
};

export function EstimatedField({ fieldName, field, onAction }: Props) {
  const value = field.value ?? "unknown";
  const sourceLabel = SOURCE_LABELS[field.source] ?? field.source;
  const confidencePct = `${Math.round(field.confidence * 100)}%`;

  return (
    <View style={styles.card}>
      <Text style={styles.valueLine}>
        {`${fieldTitle(fieldName)}: ${value} — ${sourceLabel}, ${confidencePct}`}
      </Text>
      <Text style={styles.statusLine}>{STATUS_LABELS[field.status]}</Text>
      <View style={styles.actions}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Confirm ${fieldName} ${value}`}
          onPress={() => onAction("confirm")}
          style={styles.button}
        >
          <Text style={styles.buttonText}>Confirm</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Edit ${fieldName}`}
          onPress={() => onAction("edit")}
          style={styles.button}
        >
          <Text style={styles.buttonText}>Edit</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Reject ${fieldName} ${value}`}
          onPress={() => onAction("reject")}
          style={styles.button}
        >
          <Text style={styles.buttonText}>Reject</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Leave ${fieldName} as estimate`}
          onPress={() => onAction("leave_as_estimate")}
          style={styles.button}
        >
          <Text style={styles.buttonText}>Leave as estimate</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#D1D5DB",
    gap: 8,
  },
  valueLine: { fontSize: 16, fontWeight: "600", color: "#111827" },
  statusLine: { fontSize: 14, color: "#374151" },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  button: {
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#4B5563",
    justifyContent: "center",
  },
  buttonText: { fontSize: 14, fontWeight: "600", color: "#1F2937" },
});
