import { useLocalSearchParams, useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { ChecklistScreen } from "../screens/ChecklistScreen";

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function ShoppingRoute() {
  const router = useRouter();
  const { listId: listIdParam, label: labelParam } = useLocalSearchParams<{
    listId?: string | string[];
    label?: string | string[];
  }>();
  const listId = firstParam(listIdParam);
  const label = firstParam(labelParam) ?? "Shopping run";

  if (!listId) {
    return (
      <View style={styles.empty}>
        <Text accessibilityRole="header" style={styles.heading}>
          Shopping checklist unavailable
        </Text>
        <Text>Open a shopping list before starting the checklist.</Text>
      </View>
    );
  }

  return (
    <ChecklistScreen
      listId={listId}
      onFinishShopping={() => {
        router.push({
          pathname: "/check-in",
          params: { shoppingListLabel: label },
        });
      }}
    />
  );
}

const styles = StyleSheet.create({
  empty: { flex: 1, padding: 18, gap: 10 },
  heading: { fontSize: 24, fontWeight: "700" },
});
