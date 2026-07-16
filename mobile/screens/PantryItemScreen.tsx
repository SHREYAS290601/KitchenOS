import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import {
  FieldActionName,
  PantryItemPayload,
  SourcedFieldPayload,
  getPantryItem,
  postFieldAction,
} from "../api/client";
import { EstimatedField, SourcedFieldValue } from "../components/EstimatedField";

const REVIEWABLE_FIELDS = [
  "canonical_name",
  "display_name",
  "category",
  "brand",
  "product_name",
  "quantity_value",
] as const;

type ReviewableField = (typeof REVIEWABLE_FIELDS)[number];

export function PantryItemScreen({ itemId }: { itemId: string }) {
  const [item, setItem] = useState<PantryItemPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<ReviewableField | null>(null);
  const [draftValue, setDraftValue] = useState("");

  useEffect(() => {
    let active = true;
    getPantryItem(itemId).then((result) => {
      if (!active) return;
      if (result.ok) {
        setItem(result.data);
      } else {
        setLoadError("Could not load this pantry item.");
      }
    });
    return () => {
      active = false;
    };
  }, [itemId]);

  const applyOptimistic = async (
    fieldName: ReviewableField,
    optimistic: SourcedFieldPayload | null,
    action: FieldActionName,
    value?: string | number | null,
  ) => {
    if (!item) return;
    const previous = item[fieldName];
    setActionError(null);
    setItem({ ...item, [fieldName]: optimistic });
    const result = await postFieldAction(itemId, fieldName, action, value);
    if (result.ok) {
      setItem((current) =>
        current ? { ...current, [fieldName]: result.field } : current,
      );
    } else {
      setItem((current) =>
        current ? { ...current, [fieldName]: previous } : current,
      );
      setActionError(result.message);
    }
  };

  const handleAction = (fieldName: ReviewableField, action: FieldActionName) => {
    if (!item) return;
    const stored = item[fieldName];
    if (action === "leave_as_estimate") return;
    if (action === "edit") {
      setEditingField(fieldName);
      setDraftValue(stored?.value != null ? String(stored.value) : "");
      return;
    }
    if (action === "confirm") {
      if (!stored) {
        setActionError(`${fieldName} has no value to confirm — edit it instead`);
        return;
      }
      void applyOptimistic(
        fieldName,
        { ...stored, source: "user_confirmed", confidence: 1, status: "user_confirmed" },
        "confirm",
      );
      return;
    }
    // reject
    void applyOptimistic(
      fieldName,
      { value: null, source: "user_edited", confidence: 1, status: "rejected" },
      "reject",
    );
  };

  const saveEdit = () => {
    if (!editingField) return;
    const fieldName = editingField;
    setEditingField(null);
    void applyOptimistic(
      fieldName,
      { value: draftValue, source: "user_edited", confidence: 1, status: "user_edited" },
      "edit",
      draftValue,
    );
  };

  if (loadError) {
    return (
      <View style={styles.container}>
        <Text accessibilityRole="alert" style={styles.error}>
          {loadError}
        </Text>
      </View>
    );
  }

  if (!item) {
    return (
      <View style={styles.container}>
        <Text accessibilityLiveRegion="polite">Loading pantry item…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>
        Review pantry item
      </Text>
      <Text accessibilityLiveRegion="assertive" accessibilityRole="alert" style={styles.error}>
        {actionError ?? ""}
      </Text>
      {REVIEWABLE_FIELDS.map((fieldName) => {
        const field = item[fieldName];
        if (!field) return null;
        return (
          <View key={fieldName} style={styles.fieldBlock}>
            <EstimatedField
              fieldName={fieldName}
              field={field as SourcedFieldValue}
              onAction={(action) => handleAction(fieldName, action)}
            />
            {editingField === fieldName && (
              <View style={styles.editRow}>
                <TextInput
                  accessibilityLabel={`New value for ${fieldName}`}
                  value={draftValue}
                  onChangeText={setDraftValue}
                  style={styles.input}
                />
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Save ${fieldName}`}
                  onPress={saveEdit}
                  style={styles.saveButton}
                >
                  <Text style={styles.saveButtonText}>Save</Text>
                </Pressable>
              </View>
            )}
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  heading: { fontSize: 24, fontWeight: "700" },
  error: { fontSize: 14, color: "#991B1B" },
  fieldBlock: { gap: 8 },
  editRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  input: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderColor: "#4B5563",
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 16,
    color: "#111827",
  },
  saveButton: {
    minHeight: 44,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#4B5563",
    justifyContent: "center",
  },
  saveButtonText: { fontSize: 14, fontWeight: "600", color: "#1F2937" },
});
