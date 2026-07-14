import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { confirmShoppingItem } from "../api/client";
import {
  ChecklistItem,
  loadChecklist,
  loadPendingCrossOffs,
  queueCrossOff,
  removePendingCrossOff,
  saveChecklist,
} from "../storage/checklistCache";

export function ChecklistScreen({ listId }: { listId: string }) {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [pending, setPending] = useState<string[]>([]);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([loadChecklist(), loadPendingCrossOffs()]).then(
      ([cached, queued]) => {
        if (!active) return;
        setItems(cached ?? []);
        setPending(queued);
      },
    );
    return () => {
      active = false;
    };
  }, [listId]);

  const updateItem = useCallback(
    (itemId: string, patch: Partial<ChecklistItem>) => {
      setItems((current) => {
        const next = current.map((item) =>
          item.id === itemId ? { ...item, ...patch } : item,
        );
        void saveChecklist(next);
        return next;
      });
    },
    [],
  );

  const crossOff = useCallback(
    async (item: ChecklistItem) => {
      updateItem(item.id, { checked: true });
      let result: Awaited<ReturnType<typeof confirmShoppingItem>>;
      try {
        result = await confirmShoppingItem(listId, item.id);
      } catch {
        result = { ok: false, message: "offline" };
      }
      if (result.ok) {
        updateItem(item.id, { status: "bought" });
        setAnnouncement(`${item.name} purchase confirmed`);
      } else {
        await queueCrossOff(item.id);
        setPending(await loadPendingCrossOffs());
        setAnnouncement(`${item.name} cross-off saved offline, will sync later`);
      }
    },
    [listId, updateItem],
  );

  const syncPending = useCallback(async () => {
    const queued = await loadPendingCrossOffs();
    for (const itemId of queued) {
      let ok = false;
      try {
        ok = (await confirmShoppingItem(listId, itemId)).ok;
      } catch {
        ok = false;
      }
      if (ok) {
        await removePendingCrossOff(itemId);
        updateItem(itemId, { status: "bought", checked: true });
      }
    }
    const remaining = await loadPendingCrossOffs();
    setPending(remaining);
    setAnnouncement(
      remaining.length === 0
        ? "All pending cross-offs synced"
        : `${remaining.length} cross-offs still pending sync`,
    );
  }, [listId, updateItem]);

  const categories = Array.from(
    new Set(items.map((item) => item.category ?? "other")),
  );

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>
        Shopping checklist
      </Text>
      <Text accessibilityLiveRegion="polite" style={styles.announcement}>
        {announcement}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Sync pending cross-offs"
        onPress={syncPending}
        style={styles.syncButton}
      >
        <Text style={styles.syncButtonText}>
          {`Sync pending cross-offs (${pending.length})`}
        </Text>
      </Pressable>
      {categories.map((category) => (
        <View key={category} style={styles.section}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            {category}
          </Text>
          {items
            .filter((item) => (item.category ?? "other") === category)
            .map((item) => {
              const isPending = pending.includes(item.id);
              return (
                <View key={item.id} style={styles.row}>
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: item.checked }}
                    accessibilityLabel={`Cross off ${item.name}`}
                    onPress={() => void crossOff(item)}
                    style={styles.checkbox}
                  >
                    <Text style={styles.checkboxMark}>
                      {item.checked ? "☑" : "☐"}
                    </Text>
                  </Pressable>
                  <Text
                    style={[styles.name, item.checked && styles.nameCrossed]}
                  >
                    {item.name}
                  </Text>
                  {item.status === "bought" && (
                    <Text style={styles.statusText}>bought</Text>
                  )}
                  {isPending && <Text style={styles.statusText}>pending sync</Text>}
                </View>
              );
            })}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  heading: { fontSize: 24, fontWeight: "700" },
  announcement: { fontSize: 14, color: "#374151" },
  syncButton: {
    minHeight: 44,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#4B5563",
    justifyContent: "center",
    alignSelf: "flex-start",
  },
  syncButtonText: { fontSize: 14, fontWeight: "600", color: "#1F2937" },
  section: { gap: 8 },
  sectionTitle: { fontSize: 18, fontWeight: "600" },
  row: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44 },
  checkbox: {
    minHeight: 44,
    minWidth: 44,
    justifyContent: "center",
    alignItems: "center",
  },
  checkboxMark: { fontSize: 20, color: "#111827" },
  name: { fontSize: 16, color: "#111827" },
  nameCrossed: { textDecorationLine: "line-through" },
  statusText: { fontSize: 13, color: "#374151" },
});
